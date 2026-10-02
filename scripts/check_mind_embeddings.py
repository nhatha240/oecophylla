from pathlib import Path

import numpy as np
import pandas as pd


DATASET = Path(
    r"D:\UIT\DATN\mind-small\pilot-embedded.parquet"
)

EXPECTED_DIM = 384


df = pd.read_parquet(DATASET)

print("=" * 60)
print("MIND EMBEDDING VALIDATION")
print("=" * 60)

print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")

print("\nSplit counts:")
print(df["split"].value_counts())

print("\nClick label counts:")
print(df["click_label"].value_counts())


# ------------------------------------------------------------
# Candidate article embeddings
# ------------------------------------------------------------

article_empty = 0
article_bad = 0
article_dims = {}

for article in df["article"]:
    if article is None:
        article_empty += 1
        continue

    embedding = article.get("embedding")

    if embedding is None:
        article_empty += 1
        continue

    vector = np.asarray(
        embedding,
        dtype=float,
    )

    dim = len(vector)

    article_dims[dim] = (
        article_dims.get(dim, 0) + 1
    )

    if (
        dim != EXPECTED_DIM
        or not np.isfinite(vector).all()
    ):
        article_bad += 1


print("\nCandidate embedding dimensions:")
for dim, count in sorted(article_dims.items()):
    print(f"{dim}: {count}")

print(f"Candidate empty embeddings: {article_empty}")
print(f"Candidate bad embeddings:   {article_bad}")


# ------------------------------------------------------------
# History embeddings
# ------------------------------------------------------------

history_items = 0
history_empty = 0
history_bad = 0
history_dims = {}

for history in df["history"]:
    if history is None:
        continue

    for item in history:
        history_items += 1

        if item is None:
            history_empty += 1
            continue

        article = item.get("article")

        if article is None:
            history_empty += 1
            continue

        embedding = article.get("embedding")

        if embedding is None:
            history_empty += 1
            continue

        vector = np.asarray(
            embedding,
            dtype=float,
        )

        dim = len(vector)

        history_dims[dim] = (
            history_dims.get(dim, 0) + 1
        )

        if (
            dim != EXPECTED_DIM
            or not np.isfinite(vector).all()
        ):
            history_bad += 1


print("\nHistory embedding dimensions:")
for dim, count in sorted(history_dims.items()):
    print(f"{dim}: {count}")

print(f"History items checked:  {history_items}")
print(f"History empty vectors:  {history_empty}")
print(f"History bad vectors:    {history_bad}")


# ------------------------------------------------------------
# Encoder version
# ------------------------------------------------------------

encoder_versions = (
    df["article"]
    .apply(
        lambda article:
        article.get("encoder_version")
        if article is not None
        else None
    )
    .value_counts(dropna=False)
)

print("\nEncoder versions:")
print(encoder_versions)


# ------------------------------------------------------------
# Final result
# ------------------------------------------------------------

candidate_ok = (
    len(df) == 26958
    and article_empty == 0
    and article_bad == 0
    and article_dims == {EXPECTED_DIM: len(df)}
)

history_ok = (
    history_empty == 0
    and history_bad == 0
)

print("\n" + "=" * 60)

if candidate_ok and history_ok:
    print("RESULT: PASS")
    print(
        "All candidate/history embeddings "
        "are valid."
    )
else:
    print("RESULT: CHECK REQUIRED")

print("=" * 60)