from pathlib import Path
import hashlib
import json
import argparse
from dataclasses import replace

from ai_pipeline.mind_adapter import (
    adapt_mind,
    write_mind_artifact,
    _parse_timestamp,
)


parser = argparse.ArgumentParser(
    description="Build a bounded reproducible MIND-small pilot using official train/dev splits."
)

parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--train-requests", type=int, default=500)
parser.add_argument("--test-requests", type=int, default=200)
parser.add_argument("--seed", type=int, default=20260909)

args = parser.parse_args()


# ------------------------------------------------------------
# Validate arguments
# ------------------------------------------------------------
if args.train_requests < 20 or args.test_requests < 10:
    parser.error(
        "at least 20 training requests and 10 test requests are required"
    )


root = args.data_dir

selected = []
counts = {}


# ------------------------------------------------------------
# Read and sample official MIND behaviors
#
# IMPORTANT:
# Explicitly use UTF-8 so this script works consistently on
# Windows, Linux and macOS.
# ------------------------------------------------------------
for source, limit in [
    ("train", args.train_requests),
    ("dev", args.test_requests),
]:
    behavior_path = root / source / "behaviors.tsv"

    lines = behavior_path.read_text(
        encoding="utf-8"
    ).splitlines()

    counts[source] = len(lines)

    if limit > len(lines):
        parser.error(
            f"requested {limit} {source} impressions, "
            f"but only {len(lines)} exist"
        )

    # Uniform deterministic request sample independent of
    # labels or article text.
    lines = sorted(
        lines,
        key=lambda s: hashlib.sha256(
            (
                str(args.seed)
                + ":"
                + s.split("\t")[0]
            ).encode("utf-8")
        ).digest(),
    )[:limit]

    for line in lines:
        fields = line.split("\t")

        # Prefix the original impression ID with its official
        # split so train/dev identities cannot collide.
        fields[0] = source + ":" + fields[0]

        selected.append(fields)


# ------------------------------------------------------------
# Build chronological train / validation / test split
# ------------------------------------------------------------
train_times = sorted(
    {
        _parse_timestamp(f[2])
        for f in selected
        if f[0].startswith("train:")
    }
)

dev_times = [
    _parse_timestamp(f[2])
    for f in selected
    if f[0].startswith("dev:")
]


# Official MIND train precedes official dev.
assert max(train_times) < min(dev_times)


# First 85% of sampled training times -> train
# Last 15% -> validation
cutoff = train_times[
    int(len(train_times) * 0.85)
]


# ------------------------------------------------------------
# Write sampled behavior file using UTF-8
# ------------------------------------------------------------
pilot_behaviors_path = root / "pilot-behaviors.tsv"

pilot_behaviors_path.write_text(
    "\n".join(
        "\t".join(fields)
        for fields in selected
    )
    + "\n",
    encoding="utf-8",
)


# ------------------------------------------------------------
# Merge train/dev news
#
# A news ID may exist in both official splits. If the same ID
# has different content, stop rather than silently overwrite it.
# ------------------------------------------------------------
news = {}

for source in ["train", "dev"]:
    news_path = root / source / "news.tsv"

    for line in news_path.read_text(
        encoding="utf-8"
    ).splitlines():
        key = line.split("\t")[0]

        if key in news and news[key] != line:
            raise ValueError(
                "conflicting news revision"
            )

        news[key] = line


# ------------------------------------------------------------
# Write merged pilot news using UTF-8
# ------------------------------------------------------------
pilot_news_path = root / "pilot-news.tsv"

pilot_news_path.write_text(
    "\n".join(news.values()) + "\n",
    encoding="utf-8",
)


# ------------------------------------------------------------
# Stable identity salt
#
# Used by the adapter to pseudonymize raw MIND identifiers.
# Keep the same salt between reruns so generated identities are
# reproducible on this machine.
# ------------------------------------------------------------
salt_path = root / "identity-salt"

if not salt_path.exists():
    import secrets

    salt_path.write_text(
        secrets.token_hex(32),
        encoding="utf-8",
    )

    salt_path.chmod(0o600)


salt = salt_path.read_text(
    encoding="utf-8"
).strip()


# ------------------------------------------------------------
# Convert raw MIND files into the Oecophylla dataset format
# ------------------------------------------------------------
result = adapt_mind(
    pilot_news_path,
    pilot_behaviors_path,
    hash_salt=salt,
)


# ------------------------------------------------------------
# Assign final split labels
#
# Official dev -> test
#
# Official train:
#   before cutoff -> train
#   from cutoff   -> validation
# ------------------------------------------------------------
rows = tuple(
    replace(
        row,
        split=(
            "test"
            if ":dev:" in row.audit_request_identity
            else (
                "train"
                if row.served_at < cutoff
                else "validation"
            )
        ),
    )
    for row in result.rows
)


result = replace(
    result,
    rows=rows,
)


# ------------------------------------------------------------
# Write Parquet artifact + metadata
# ------------------------------------------------------------
metadata_path = write_mind_artifact(
    result,
    root / "pilot-text.parquet",
)


metadata = json.loads(
    metadata_path.read_text(
        encoding="utf-8"
    )
)


# ------------------------------------------------------------
# Record reproducibility information
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# Record hashes of the original downloaded archives
# ------------------------------------------------------------
metadata["source_archives"] = {
    source: hashlib.sha256(
        (
            root
            / f"MINDsmall_{source}.zip"
        ).read_bytes()
    ).hexdigest()
    for source in ["train", "dev"]
}


# ------------------------------------------------------------
# Write metadata using UTF-8
# ------------------------------------------------------------
metadata_path.write_text(
    json.dumps(
        metadata,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)


# ------------------------------------------------------------
# Final summary
# ------------------------------------------------------------
print(
    json.dumps(
        {
            "rows": len(rows),
            "requests": len(selected),
            "metadata": str(metadata_path),
        }
    )
)