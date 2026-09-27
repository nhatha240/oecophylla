# MINDlarge training and recommendation check — 2026-09-27

The supplied `data _train ` directory was used to run real article encoding,
attention-head fine-tuning, held-out evaluation, artifact loading, and a Vietnamese
text recommendation example. **The fine-tuned candidate is not approved for
production.** It does not demonstrate a gain over the semantic baseline and fails
the small Vietnamese relevance example. The separately exported semantic baseline
is available for local experiments; it is not a production release either.

## Data and training

- Input: 2,232,748 official training requests and 376,471 dev requests, counted
  by streaming the supplied files. Original files were not changed.
- Deterministic sample: 10,000 train-file requests and 2,000 dev-file requests,
  selected by canonical request hash with seed `20260927`, independent of labels.
- Chronological split: 8,497 training, 1,503 validation, 2,000 test requests.
  Equal-timestamp requests remain together. Validation starts at
  `2019-11-14T07:36:45+00:00`; official dev supplies the sealed labeled holdout.
- Candidates: 317,209 training, 59,535 validation, 76,815 test. Every candidate
  from each sampled impression is retained for evaluation.
- 25,757 distinct articles; last 20 supplied history entries per request.
  Compact requests plus shared float32 embeddings occupy about 58 MB.
- Frozen `intfloat/multilingual-e5-small`, revision
  `614241f622f53c4eeff9890bdc4f31cfecc418b3`, 384 dimensions. Its pinned weights
  were verified before local GPU encoding. Text uses the existing normalization
  and `passage: ` prefix, matching the content worker.
- Fine-tuning: AdamW over the attention head, four negatives from the same
  impression per positive, 64 examples per batch, gradient clipping, validation
  early stopping. Learning rates `0.0001` and `0.001`, up to ten epochs each.
  The selected checkpoint is learning rate `0.001`, epoch 3. In total the search
  ran 3,152 optimizer steps over 12,596 eligible positive examples per epoch.
- Value projections start in the pretrained semantic space; positional scale is
  explicitly `0.02`. Existing artifacts retain their original default scale `1`.
- Selection uses validation nDCG@10 only. Probability calibration uses validation
  and a positive temperature, so it cannot reverse the ranking.

This is a sampled benchmark, not full MINDlarge training. Official test is
unlabeled and was not evaluated or assigned fabricated labels. MIND supplies
English news clicks, not Oecophylla friends, Vietnamese preference labels,
qualified-read labels, or publication timestamps. See the
[MIND dataset](https://msnews.github.io/) and
[E5 model card](https://huggingface.co/intfloat/multilingual-e5-small).

## Held-out results

All rows below use the same 2,000 held-out requests and 76,815 candidates.

| Model | Impression AUC | MIND MRR | nDCG@5 | nDCG@10 | Coverage@5 |
|---|---:|---:|---:|---:|---:|
| Logged order | 0.497103 | 0.214063 | 0.218680 | 0.279895 | 0.371840 |
| Frozen semantic mean pool | **0.592151** | **0.277764** | **0.295326** | **0.350794** | 0.290323 |
| Fine-tuned attention | 0.583291 | 0.266448 | 0.287862 | 0.349816 | 0.248038 |

Fine-tuned minus semantic nDCG@10: `-0.000979`, paired request-bootstrap 95%
interval `[-0.015377, 0.014465]`. There is no demonstrated improvement. Coverage
also regresses. Logged MIND order is not the Oecophylla heuristic, and this report
does not replace the existing release gate or serving-policy comparison.

MRR here averages reciprocal ranks of every clicked candidate, following the
MIND convention. `first_click_mrr` is also reported in JSON to distinguish it
from the existing evaluator's first-click metric. The original evaluator is
unchanged.

The test population includes only 65 cold users and 74 requests with one or two
history items. Segment metrics are in the JSON report; these small populations
cannot establish production cold-start quality. No artifact was promoted.

## Artifacts

Generated data and models remain under the Git-ignored `artifacts/models/`:

- `mind-large-20260927/report.json`: search history, metrics, segment breakdowns,
  bootstrap interval, source checksums, and non-release status.
- `mind-large-20260927/dataset.json`: compact hashed requests and article text.
- `mind-large-20260927/embeddings.npz`: content/encoder-bound embedding cache.
- `mind-large-20260927/identity-salt`: private HMAC salt, permissions `0600`.
  Keep it private; preserve it locally to reproduce the same exported identities.
- `mind-large-20260927-nrms-e3/`: evaluated fine-tuned artifact. Model checksum
  `e42e833a279cb1e3dd00b0177cfcf0e33a1f3857f20a7dd25df8be0e998c2e7e`.
- `mind-large-20260927-semantic-baseline/`: frozen mean-pool comparison model with
  validation-only calibration. It is not mislabeled as a fine-tuned model.
- `mind-large-20260927/serving-check.json`: actual fine-tuned artifact passed
  the API loader and shadow scorer, with zero offline/serving score difference.
  On this Mac, 300 candidates and 20 history items took about 2.64 ms p95 over
  30 local predictor calls. This excludes database, network, and embedding time.
- `mind-large-20260927/recommendation-demo.json`: rejected fine-tuned Vietnamese
  smoke result; it placed unrelated food and football ahead of programming/AI.
- `mind-large-20260927/semantic-demo.json`: baseline placed the Python friend
  post and AI news first for the same programming/AI history.

The Vietnamese example is synthetic, never used for training, and is only a
smoke check. It is not a Vietnamese quality benchmark. Scores are ranking
signals calibrated on English MIND clicks, not validated Vietnamese CTR estimates.

## Run recommendations locally

From the repository root, using the cached encoder already present on this Mac:

```bash
MODEL_DIR="$HOME/.cache/huggingface/hub/models--intfloat--multilingual-e5-small/snapshots/614241f622f53c4eeff9890bdc4f31cfecc418b3"

uv run --with-requirements ai_pipeline/requirements.training.txt \
  python -m ai_pipeline.recommend \
  --artifact artifacts/models/mind-large-20260927-semantic-baseline \
  --model-dir "$MODEL_DIR" \
  --input docs/examples/recommendation-input.json \
  --device mps
```

Use `--device cpu` on a machine without Apple GPU support. Replace the example
with prior `history` text, optional declared `interests`, and `candidates` with
unique `id`, `text`, and optional `source`. Reading history takes precedence;
empty-history users fall back to declared interests, then training-derived popular
content. The interface creates no fake clicks.

The application must supply candidates the user may see. Friend/follow retrieval,
blocked-author exclusions, moderation, and access control belong upstream. The
model scores content relevance for both friend posts and news. A `following`
source label is preserved in output; it is not evidence of learned relationship
affinity.

The artifact uses the existing `NRMSArtifactPredictor` interface and pinned
encoder. Production remains `RANKER_MODE=heuristic`. Even shadow deployment needs
valid post embeddings, prior history snapshots, and an operational environment;
this work did not deploy or restart services.

## Repeat the experiment

Use a new output directory; completed artifacts are immutable:

```bash
uv run --with-requirements ai_pipeline/requirements.training.txt \
  python -m ai_pipeline.mind_large \
  --data-dir 'data _train ' \
  --output artifacts/models/mind-large-next \
  --model-dir "$MODEL_DIR" \
  --train-requests 10000 --test-requests 2000 \
  --epochs 10 --learning-rates 0.0001 0.001 \
  --batch-size 64 --device mps
```

Stages are `prepare`, `encode`, and `train`; use `--stage encode` or `--stage train`
to continue after a completed preparation. Training restarts its search if
interrupted before export; optimizer-state resume is not implemented. Embeddings
are reused only when their text, encoder, dimensions, and normalization match.
The compact JSON/NPZ format has its own runner; do not pass it to the existing
Parquet-only `make train-ai` / `make evaluate-ai` commands.

Once a holdout has been inspected, it is not fresh evidence for further tuning.
Subsequent model development needs a new untouched holdout and a production-domain
evaluation, not repeated attempts to improve this test score.

## Verification and remaining work

Tests cover deterministic bounded sampling, intact candidate groups, chronological
boundaries, private identifiers, invalid inputs, embedding cache binding, padded
Torch/NumPy parity, cold start, validation-only selection, immutable artifacts,
report checksum binding, and the recommendation CLI. New module test coverage is
about 90%. All **138 AI tests passed** in a temporary worktree with the committed
fixtures, preserving the user's four staged fixture deletions. **87 API tests passed**
with one opt-in PostgreSQL integration test skipped and two existing deprecation
warnings. Local artifact shadow checks preserved displayed heuristic scores.

The original checkout's full AI suite initially had 71 passes and 45 failures
caused by the deleted fixtures. Those deletions and all unrelated frontend edits
remain untouched. OrbStack's Docker socket was unavailable, so local production
interactions and live database-to-feed behavior could not be verified.

Real social-feed fine-tuning still requires Oecophylla's follow graph, eligible
served/visible impressions, clicks/qualified reads, negative feedback, timestamps,
and content snapshots under the existing label/dataset contracts. Vietnamese
holdout quality, diversity/coverage gates, live tracing, shadow observation, and
canary/rollback checks remain open.
