# Recommendation dataset v2

Status: training-data contract. Producing this dataset does not enable an online
ranker.

Schema version: `recommendation-dataset-v2`

Dataset scope: `served-impression-reranking`

## Scope and unit of observation

The exported unit is one candidate row. Rows are grouped by `request_group`, an
HMAC-SHA256 identity derived from the protected `(user_id, request_id)` tuple.
Every request group is assigned atomically to exactly one chronological split.
The schema can evaluate ranking within the candidate set that was actually
served. It cannot evaluate retrieval recall because current telemetry does not
contain the complete pre-ranking retrieval pool. `retrieval_recall_supported`
is therefore always `false`; retrieval evaluation is deferred to T8b.

Only candidates with both a stored recommendation impression (`served=true`)
and a proven visibility event (`visible=true`) are exported. A served candidate
without visibility is counted in exclusions, not converted into a negative.
An item that was retrieved but never logged as served is outside this dataset
and is never synthesized as a candidate or negative.

## Candidate row

Each Parquet row has these logical fields:

| Field | Contract |
| --- | --- |
| `sample_id` | Private 64-character hash; unique candidate observation. |
| `request_group` | Private 64-character HMAC; split and ranking group. |
| `candidate_group` | Private 64-character article hash. |
| `split` | `train`, `validation`, or `test`. |
| `served_at`, `visible_at` | Timezone-aware event timestamps. |
| `position` | Unique served position within the request. |
| `served`, `visible` | Both must be `true`; retained separately for audit. |
| `click_label` | `1` only when a click occurred in the closed label window, otherwise `0`. |
| `utility_label` | Binary target from `engagement-label-v2`, independent of click. |
| `utility_label_name` | Resolved v2 semantic used to derive `utility_label`. |
| `article` | Versioned candidate representation. |
| `history` | Ordered click-only snapshot strictly before `served_at`. |
| `feed_source`, `model_version` | Logged serving envelope. |
| `source_format` | Versioned source adapter identity. |
| `dataset_scope` | Always `served-impression-reranking`. |

`click_label` and `utility_label` must not be collapsed. For example, a
qualified read can have `(click_label=0, utility_label=1)`, while a clicked item
that is subsequently reported can have `(click_label=1, utility_label=0)`.

## Local article and history representations

Oecophylla rows use `post-content-embedding-v1`. The candidate feature revision
must use the dataset's pinned encoder and must have `source_updated_at <=
served_at` and `computed_at <= served_at`. A history feature revision must meet
the same conditions at that click's `engaged_at`, not merely at extraction
time. Embeddings are never backfilled with zeros: a missing, non-finite,
wrong-dimensional, or differently encoded candidate/history representation
invalidates the dataset.

History contains only persisted v2 click events. For each request, entries:

1. have contiguous zero-based ordinals;
2. are nondecreasing by `(engaged_at, event_id)` construction order;
3. satisfy `engaged_at < served_at` and `ingested_at <= served_at`; and
4. carry the immutable article content hash and encoder version available at
   the click time.

An empty history is valid for a cold-start user and is counted in metadata. All
candidates in one request must carry exactly the same history snapshot.

## Official MIND adapter

`python -m ai_pipeline.mind_adapter` accepts the official eight-column
`news.tsv` and five-column `behaviors.tsv` formats. MIND source user,
impression, and news IDs are used only while parsing and are replaced by
namespace-scoped HMAC identities before export. Production storage is not
keyed by, or coupled to, MIND IDs.

MIND history is the ordered, pre-impression snapshot supplied in the behavior
row. Since the public file contains no per-click timestamps, entries preserve
TSV order using contiguous ordinals and the explicit
`mind-pre-impression-snapshot` provenance. MIND articles use the versioned
`mind-text-v1` title/abstract representation. The adapter does not fabricate or
claim a multilingual embedding; downstream benchmark preparation must encode
that text under a separately pinned model artifact.

MIND impression labels populate `click_label`; `utility_label` is equal to the
click label because the official files do not contain Oecophylla product
utility events. Both the MIND and local adapters emit the same row dataclass,
Parquet logical shape, split names, private group identities, and run through
the same dataset validator.

## Required metadata

Local artifacts pin:

- `dataset_schema_version=recommendation-dataset-v2`;
- `dataset_scope=served-impression-reranking`;
- source format, `post-content-features-v1`, and
  `user-history-snapshot-v1`;
- `engagement-label-v2` and `QUALIFIED_READ_MS` through build configuration;
- the complete immutable encoder repository revision and dimension;
- code revision and `event-time-window-v1` query-window version;
- exact start, end, and extraction timestamps;
- split/request/candidate distributions, empty-history count, and separate
  click/utility class balance; and
- visibility exclusions and explicit privacy/retrieval-recall declarations.

The writer rejects metadata encoder or dimension values that were not verified
against every embedded candidate and history article.

## Validation and privacy

A dataset is rejected when it has fewer than two candidates in any request,
only one click or utility class, duplicate candidate positions/articles,
non-private identity fields, missing article representations, malformed or
future history, inconsistent histories inside a request, conflicting request
envelopes, or a request in multiple splits.

Raw user, request, impression, post, and MIND identifiers are forbidden from
candidate records, history entries, metadata, reports, and model features.
Internal raw identities may exist only in process memory long enough to prove
request atomicity and detect hash collisions.

## Rollback

`recommendation-dataset-v1` may continue to be produced for historical audit.
Training and promotion of the MIND-aligned ranker remain blocked unless a valid
v2 artifact is available. Rollback never relabels v2 data as v1 and never mixes
label versions in one run.
