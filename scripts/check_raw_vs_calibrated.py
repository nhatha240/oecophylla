from pathlib import Path
from collections import defaultdict

import joblib
import numpy as np
import pandas as pd


DATASET = Path(r"D:\UIT\DATN\mind-small\pilot-embedded.parquet")
MODEL = Path(r"D:\UIT\DATN\mind-small\nrms-pilot-v1\model.joblib")


def impression_auc(items):
    """
    items = [(label, score), ...]
    AUC trong phạm vi một impression/request.
    """
    positives = [score for label, score in items if int(label) > 0]
    negatives = [score for label, score in items if int(label) <= 0]

    if not positives or not negatives:
        return None

    credit = 0.0

    for positive in positives:
        for negative in negatives:
            if positive > negative:
                credit += 1.0
            elif positive == negative:
                credit += 0.5

    return credit / (len(positives) * len(negatives))


def reciprocal_rank(items):
    """
    items = [(label, score), ...]
    """
    ranked = sorted(items, key=lambda x: -x[1])

    for rank, (label, _) in enumerate(ranked, start=1):
        if int(label) > 0:
            return 1.0 / rank

    return 0.0


def ndcg(items, k):
    ranked = sorted(items, key=lambda x: -x[1])

    dcg = 0.0
    for i, (label, _) in enumerate(ranked[:k]):
        if int(label) > 0:
            dcg += 1.0 / np.log2(i + 2)

    positives = sum(1 for label, _ in items if int(label) > 0)

    ideal = sum(
        1.0 / np.log2(i + 2)
        for i in range(min(k, positives))
    )

    if ideal == 0:
        return 0.0

    return dcg / ideal


def get_history_embeddings(row):
    history = row.get("history")

    if history is None:
        return []

    history = sorted(
        history,
        key=lambda entry: int(entry["ordinal"])
    )

    result = []

    for entry in history:
        article = entry.get("article") or {}
        embedding = article.get("embedding")

        if embedding is not None:
            result.append(embedding)

    return result


def get_raw_score(model, row):
    article = row.get("article") or {}
    candidate_embedding = article.get("embedding")

    if candidate_embedding is None:
        raise ValueError("Candidate article has no embedding")

    history_embeddings = get_history_embeddings(row)

    if not history_embeddings:
        # Giữ cách fallback gần với model hiện tại.
        if getattr(model, "popular_embedding", None) is not None:
            history_embeddings = [model.popular_embedding]
        else:
            return 0.0

    context = model.prepare_user_context(
        history_embeddings=history_embeddings,
        declared_topic_embedding=row.get("declared_topic_embedding"),
    )

    return float(
        model.raw_score(
            context.vector,
            candidate_embedding,
        )
    )


def get_calibrated_score(model, row):
    article = row.get("article") or {}
    candidate_embedding = article.get("embedding")

    if candidate_embedding is None:
        raise ValueError("Candidate article has no embedding")

    history_embeddings = get_history_embeddings(row)

    if not history_embeddings:
        if getattr(model, "popular_embedding", None) is not None:
            history_embeddings = [model.popular_embedding]
        else:
            return 0.0

    context = model.prepare_user_context(
        history_embeddings=history_embeddings,
        declared_topic_embedding=row.get("declared_topic_embedding"),
    )

    return float(
        model.score(
            context.vector,
            candidate_embedding,
        )
    )


def evaluate(grouped):
    aucs = []
    mrrs = []
    ndcg5 = []
    ndcg10 = []

    for request_group, items in grouped.items():
        auc = impression_auc(items)

        if auc is not None:
            aucs.append(auc)

        mrrs.append(reciprocal_rank(items))
        ndcg5.append(ndcg(items, 5))
        ndcg10.append(ndcg(items, 10))

    return {
        "requests": len(grouped),
        "auc_requests": len(aucs),
        "impression_auc": float(np.mean(aucs)) if aucs else None,
        "mrr": float(np.mean(mrrs)) if mrrs else None,
        "ndcg_at_5": float(np.mean(ndcg5)) if ndcg5 else None,
        "ndcg_at_10": float(np.mean(ndcg10)) if ndcg10 else None,
    }


def main():
    print("=" * 70)
    print("RAW SCORE vs CALIBRATED SCORE CHECK")
    print("=" * 70)

    if not DATASET.exists():
        raise FileNotFoundError(DATASET)

    if not MODEL.exists():
        raise FileNotFoundError(MODEL)

    print()
    print("Dataset:", DATASET)
    print("Model  :", MODEL)

    df = pd.read_parquet(DATASET)

    print()
    print("Dataset rows:", len(df))

    test = df[df["split"] == "test"].copy()

    print("Test rows   :", len(test))
    print(
        "Test requests:",
        test["request_group"].astype(str).nunique(),
    )

    model = joblib.load(MODEL)

    print()
    print("Model type:")
    print(type(model))

    print()
    print("Calibration:")
    print(
        "  scale =",
        getattr(model, "calibration_scale", None),
    )
    print(
        "  bias  =",
        getattr(model, "calibration_bias", None),
    )

    raw_groups = defaultdict(list)
    calibrated_groups = defaultdict(list)

    raw_scores_all = []
    calibrated_scores_all = []

    total = len(test)

    print()
    print("Computing scores...")

    for index, (_, row_series) in enumerate(test.iterrows(), start=1):
        row = row_series.to_dict()

        raw_score = get_raw_score(model, row)
        calibrated_score = get_calibrated_score(model, row)

        request_group = str(row["request_group"])
        label = int(row["click_label"])

        raw_groups[request_group].append(
            (label, raw_score)
        )

        calibrated_groups[request_group].append(
            (label, calibrated_score)
        )

        raw_scores_all.append(raw_score)
        calibrated_scores_all.append(calibrated_score)

        if index % 1000 == 0 or index == total:
            print(f"  {index}/{total}")

    raw_metrics = evaluate(raw_groups)
    calibrated_metrics = evaluate(calibrated_groups)

    print()
    print("=" * 70)
    print("RAW SCORE RESULTS")
    print("=" * 70)

    for key, value in raw_metrics.items():
        print(f"{key:20s}: {value}")

    print()
    print("=" * 70)
    print("CALIBRATED SCORE RESULTS")
    print("=" * 70)

    for key, value in calibrated_metrics.items():
        print(f"{key:20s}: {value}")

    raw = np.asarray(raw_scores_all, dtype=float)
    calibrated = np.asarray(calibrated_scores_all, dtype=float)

    correlation = np.corrcoef(raw, calibrated)[0, 1]

    print()
    print("=" * 70)
    print("DIAGNOSTICS")
    print("=" * 70)

    print("Raw score min       :", raw.min())
    print("Raw score max       :", raw.max())
    print("Calibrated min      :", calibrated.min())
    print("Calibrated max      :", calibrated.max())
    print("Raw/calibrated corr :", correlation)

    print()

    scale = getattr(model, "calibration_scale", None)

    if scale is not None and scale < 0:
        print("WARNING: calibration_scale is NEGATIVE.")
        print("This reverses raw ranking when model.score() is used.")
    else:
        print("Calibration scale is not negative.")

    print()

    raw_auc = raw_metrics["impression_auc"]
    calibrated_auc = calibrated_metrics["impression_auc"]

    if raw_auc is not None and calibrated_auc is not None:
        print(
            "AUC difference "
            "(raw - calibrated):",
            raw_auc - calibrated_auc,
        )

        if raw_auc > calibrated_auc:
            print()
            print(
                "RESULT: RAW ranking is better than "
                "CALIBRATED ranking."
            )
        elif raw_auc < calibrated_auc:
            print()
            print(
                "RESULT: CALIBRATED ranking is better "
                "than RAW ranking."
            )
        else:
            print()
            print("RESULT: Both rankings have the same AUC.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()