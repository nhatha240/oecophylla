"""Join protected retrieval pools to served snapshots without inventing labels."""

from __future__ import annotations

import hashlib
import hmac
import json


def analyze_retrieval(candidates, impressions, *, hash_salt: str):
    if not hash_salt:
        raise ValueError("a private hashing salt is required")
    pools = {}
    for row in candidates:
        if row["stage"] != "eligible":
            raise ValueError("unsupported candidate stage")
        pools.setdefault(str(row["retrieval_request_id"]), set()).add(
            str(row["post_id"])
        )
    counts = dict(served=0, matched=0, unmatched=0)
    exported = []
    for impression in impressions:
        snapshot = impression["feature_snapshot"]
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)
        retrieval_id = str(snapshot.get("retrieval_request_id", ""))
        if retrieval_id not in pools:
            continue  # Unsampled generations are not missing-candidate failures.
        post_id = str(impression["post_id"])
        included = post_id in pools[retrieval_id]
        counts["served"] += 1
        counts["matched" if included else "unmatched"] += 1
        private_post = hmac.new(
            hash_salt.encode(), ("post:" + post_id).encode(), hashlib.sha256
        ).hexdigest()
        exported.append(dict(post_group=private_post, in_retrieval_pool=included))
    return dict(
        report_schema_version="retrieval-membership-v1",
        sampled_pools=len(pools),
        counts=counts,
        served_pool_membership=(
            counts["matched"] / counts["served"] if counts["served"] else None
        ),
        engagement_labels_derived=False,
        counterfactual_recall_supported=False,
        served_membership=exported,
    )
