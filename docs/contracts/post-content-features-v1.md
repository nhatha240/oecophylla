# Post content features v1

Status: storage and producer contract; no producer is enabled by T4A.

Schema version: `post-content-features-v1`  
Normalization version: `post-content-normalization-v1`

## Encoder selection and provenance

The selected encoder is
`intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3`.
The complete repository revision, rather than a mutable branch name, is the
`encoder_version` written to storage and payloads.

| Property | Pinned value |
| --- | --- |
| Repository | `intfloat/multilingual-e5-small` |
| Revision | `614241f622f53c4eeff9890bdc4f31cfecc418b3` |
| Artifact | `model.safetensors` (470,641,600 bytes) |
| Artifact SHA-256 | `1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477` |
| License | MIT |
| Output | 384 float32 coordinates, L2-normalized |
| Maximum input | 512 tokenizer tokens |

Primary provenance is the pinned
[model card](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3),
which documents multilingual training, Vietnamese support, the 384 dimension,
MIT license, 512-token truncation, mean pooling, L2 normalization, and the
required `query: ` / `passage: ` prefixes. The artifact digest is the
SHA-256 returned for the pinned
[`model.safetensors`](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/model.safetensors).

The small, checked-in Vietnamese semantic-retrieval benchmark contains 8
queries and 10 short news passages across economics, sport, weather, health,
education, transport, tourism, finance, and agriculture. With the pinned model
and `sentence-transformers==5.1.0`, it produced Recall@1 = 0.875 and MRR@10 =
0.9375; all 18 embeddings were finite and 384-dimensional. One agriculture
query ranked the storm passage first and its relevant salt-tolerant-rice
passage second. This fixture is a smoke benchmark for encoder selection, not a
claim of production quality or a substitute for the T7 temporal evaluation.
The exact inputs, relevance judgments, per-query ranks, and method are in
`tests/fixtures/post_content_features/vietnamese-retrieval-v1.json`.

## Deterministic text preprocessing

Given the post body as Unicode text, a conforming producer performs these
steps in order:

1. Decode as valid UTF-8 and normalize to Unicode NFC.
2. Convert CRLF and CR line endings to LF.
3. Replace each non-empty run of Unicode whitespace with one ASCII space.
4. Trim leading and trailing whitespace. Reject an empty result.
5. Preserve case, Vietnamese diacritics, and punctuation.

`content_hash` is the lowercase hexadecimal SHA-256 of the UTF-8 bytes of
`post-content-normalization-v1`, one LF byte, and the normalized text. The E5
document input is `passage: ` followed by that normalized text. Retrieval
queries use `query: ` followed by identically normalized query text. The
pinned tokenizer truncates at 512 tokens. The producer mean-pools non-padding
token states using the attention mask, casts to float32, and L2-normalizes the
384 coordinates. NaN, infinity, zero, wrong-dimensional, or non-unit vectors
are invalid.

Topic labels are normalized independently: Unicode NFC, collapsed whitespace,
trimmed, lowercased, deduplicated, then sorted by UTF-8 byte order. A payload
contains at most 32 labels of at most 64 Unicode characters each. The database
also rejects empty, padded, uppercase, duplicate, out-of-order, or repeated-
whitespace labels.

## Versioned payload

The worker-to-storage payload is:

```json
{
  "schema_version": "post-content-features-v1",
  "post_id": "operational UUID",
  "encoder_version": "intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3",
  "normalization_version": "post-content-normalization-v1",
  "content_hash": "64 lowercase hex characters",
  "embedding": "exactly 384 finite, L2-normalized float32 values",
  "normalized_topics": ["kinh tế", "thời sự"],
  "source_updated_at": "RFC 3339 timestamp from the source post",
  "computed_at": "RFC 3339 timestamp"
}
```

Unknown schema, normalization, or encoder versions are rejected. Payload
timestamps must satisfy `source_updated_at <= computed_at`. Retries with the
same `(post_id, encoder_version, content_hash)` are idempotent; conflicting
data for that identity are rejected. A changed content hash or encoder version
creates a new immutable row. Rows are never updated in place. This preserves
content and encoder revisions and permits multiple supported encoder versions;
a new supported encoder is registered only by a forward migration.

## Temporal use and fallback

Online use requires a row whose hash matches the normalized current post. For
an impression at `served_at`, offline feature selection must also enforce both
`source_updated_at <= served_at` and `computed_at <= served_at`, then choose the
latest eligible immutable revision. It must not reconstruct an old impression
from the post's current content or from a feature computed in the future. If a
historical content snapshot and matching feature cannot be proven, the
embedding is missing for that sample.

When no valid embedding exists, existing keyword topics on `posts.topics`
remain authoritative. Serving and dataset code must record embedding
missingness and use those keyword topics; it must not silently substitute a
zero vector. An encoder download, checksum, inference, validation, or storage
failure must therefore leave the post servable through the keyword-topic
fallback.

## Identity and data handling

The operational table and worker payload contain raw `post_id` only to join the
feature to the protected source post. Raw `post_id` must not appear in training
datasets, reports, logs, benchmark fixtures, or model artifacts. Offline data
uses the repository's version-scoped HMAC identity when an article identity is
needed for auditing. `post_id` and any user identity are forbidden model
features. The table contains no user identity or behavior observed after an
impression.

## Rollback

T4A does not enable a producer. To roll back operationally, leave the additive
tables empty and continue serving keyword topics. Any schema correction uses a
new forward migration; deployed migrations and stored feature revisions are
not edited or deleted.
