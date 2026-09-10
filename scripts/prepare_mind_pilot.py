from pathlib import Path
import hashlib, json
from dataclasses import replace
from ai_pipeline.mind_adapter import adapt_mind, write_mind_artifact, _parse_timestamp
import argparse

parser = argparse.ArgumentParser(
    description="Build a bounded reproducible MIND-small pilot using official train/dev splits."
)
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--train-requests", type=int, default=500)
parser.add_argument("--test-requests", type=int, default=200)
parser.add_argument("--seed", type=int, default=20260909)
args = parser.parse_args()
if args.train_requests < 20 or args.test_requests < 10:
    parser.error("at least 20 training requests and 10 test requests are required")
root = args.data_dir
selected = []
counts = {}
for source, limit in [("train", args.train_requests), ("dev", args.test_requests)]:
    lines = (root / source / "behaviors.tsv").read_text().splitlines()
    counts[source] = len(lines)
    if limit > len(lines):
        parser.error(
            f"requested {limit} {source} impressions, but only {len(lines)} exist"
        )
    # Uniform deterministic request sample independent of labels or article text.
    lines = sorted(
        lines,
        key=lambda s: hashlib.sha256(
            (str(args.seed) + ":" + s.split("\t")[0]).encode()
        ).digest(),
    )[:limit]
    for line in lines:
        fields = line.split("\t")
        fields[0] = source + ":" + fields[0]
        selected.append(fields)
train_times = sorted(
    {_parse_timestamp(f[2]) for f in selected if f[0].startswith("train:")}
)
dev_times = [_parse_timestamp(f[2]) for f in selected if f[0].startswith("dev:")]
assert max(train_times) < min(dev_times)
cutoff = train_times[int(len(train_times) * 0.85)]
(root / "pilot-behaviors.tsv").write_text(
    "\n".join("\t".join(f) for f in selected) + "\n"
)
news = {}
for source in ["train", "dev"]:
    for line in (root / source / "news.tsv").read_text().splitlines():
        key = line.split("\t")[0]
        if key in news and news[key] != line:
            raise ValueError("conflicting news revision")
        news[key] = line
(root / "pilot-news.tsv").write_text("\n".join(news.values()) + "\n")
salt_path = root / "identity-salt"
if not salt_path.exists():
    import secrets

    salt_path.write_text(secrets.token_hex(32))
    salt_path.chmod(0o600)
salt = salt_path.read_text().strip()
result = adapt_mind(
    root / "pilot-news.tsv", root / "pilot-behaviors.tsv", hash_salt=salt
)
rows = tuple(
    replace(
        r,
        split="test"
        if ":dev:" in r.audit_request_identity
        else ("train" if r.served_at < cutoff else "validation"),
    )
    for r in result.rows
)
result = replace(result, rows=rows)
metadata_path = write_mind_artifact(result, root / "pilot-text.parquet")
metadata = json.loads(metadata_path.read_text())
metadata["benchmark_sampling"] = {
    "method": "sha256-request-sample-v1",
    "seed": args.seed,
    "official_counts": counts,
    "selected_train": args.train_requests,
    "selected_dev": args.test_requests,
    "scope": "pipeline-pilot-not-full-MIND-small",
    "validation_cutoff": cutoff.isoformat(),
    "official_dev_is_test": True,
}
metadata["source_archives"] = {
    s: hashlib.sha256((root / f"MINDsmall_{s}.zip").read_bytes()).hexdigest()
    for s in ["train", "dev"]
}
metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
print(
    json.dumps(
        {"rows": len(rows), "requests": len(selected), "metadata": str(metadata_path)}
    )
)
