# MINDlarge round 2 — semantic preservation

The new model **improves over the semantic baseline on a fresh 10,000-request
holdout** and passes the Vietnamese example that failed in round 1. It is usable
for local content-ranking experiments and loads through the existing API shadow
predictor. Production release remains **INCONCLUSIVE**: no production-domain
social/Vietnamese holdout or live operational evidence is available.

## What changed

Fine-tuning now learns attention weights over reading history while keeping the
value projections fixed at identity. Position noise is disabled, and half of the
output remains the original semantic mean-pool vector. This limits the learned
head's ability to distort the frozen multilingual content embeddings. The
constrained model is permutation-invariant within the last 20 history entries;
it does not learn fine-grained order or recency effects within those entries.

The plain semantic baseline is an explicit validation candidate, so a failed
search can retain it rather than exporting a weaker trained head. Old models
keep their previous defaults and loading behavior. The residual value is bound
to the artifact manifest and checked against the model payload.

`--exclude-holdout` removes previously evaluated requests before deterministic
sampling. The prior run's private identity salt is reused with `0600` permissions.
Exclusion fails if identities cannot be matched, including a wrong salt. Both
the prior dataset checksum and exclusion counts are recorded.

## Experiment

- 50,000 sampled official training requests: **42,401 train + 7,599 validation**.
- **10,000 new dev requests** for final evaluation, with **zero overlap** with
  the previous 2,000 test requests.
- 1,570,466 training candidates, 298,907 validation candidates, and 374,285 test
  candidates. All candidates in each sampled request remain available to metrics.
- 45,749 articles encoded with the same pinned multilingual E5-small revision.
- Seed `20260928`; batch size 128; learning rates `0.001`, `0.01`; at most 12
  epochs each with validation early stopping. The search stopped after four epochs
  for each rate. It used 62,536 positive training examples and 3,912 optimizer steps.
- Selected using validation alone: **learning rate 0.001, epoch 1**. Validation
  nDCG@10 was 0.342215 versus baseline 0.337315. Calibration uses validation only
  and cannot reverse the ranking.
- The protocol was saved before final evaluation. No holdout-directed retraining
  or model selection was performed after inspecting round 2 results.

| Model, same new holdout | AUC | MIND MRR | nDCG@5 | nDCG@10 | Coverage@5 |
|---|---:|---:|---:|---:|---:|
| Logged order | 0.505963 | 0.224107 | 0.227335 | 0.292901 | 0.441472 |
| Semantic baseline | 0.593952 | 0.276956 | 0.295825 | 0.356622 | 0.337235 |
| Constrained fine-tuned model | **0.601871** | **0.287142** | **0.313775** | **0.372102** | **0.363991** |

nDCG@10 improves by **0.015480 absolute / 4.34% relative** over the semantic
baseline. The paired request-bootstrap 95% interval is **[0.011952, 0.019108]**.
Coverage improves relative to the semantic baseline, but remains below logged
order. Logged order is not the Oecophylla heuristic.

Cold-start scores are unchanged. For the 406 requests with one or two history
items, nDCG@10 increases from 0.405201 to 0.409323, while AUC decreases slightly
from 0.575531 to 0.572594. Aggregate improvement does not establish improvement
for every segment. Diversity, explicit negative feedback, and full serving-policy
effects have not been validated by this benchmark.

## Use the new model locally

From the repository root:

```bash
MODEL_DIR="$HOME/.cache/huggingface/hub/models--intfloat--multilingual-e5-small/snapshots/614241f622f53c4eeff9890bdc4f31cfecc418b3"

uv run --with-requirements ai_pipeline/requirements.training.txt \
  python -m ai_pipeline.recommend \
  --artifact artifacts/models/mind-large-20260927-r2/model \
  --model-dir "$MODEL_DIR" \
  --input docs/examples/recommendation-input.json \
  --device mps
```

Use `--device cpu` when Apple GPU is unavailable. Input and eligibility rules
remain documented in [round 1](MIND_LARGE_RUN_20260927.md#run-recommendations-locally).
Supply the user's prior reading history or declared interests and authorized
candidate posts. Friends/follow relationships and safety filtering belong to the
application's candidate retrieval. MIND does not provide those relationships;
the model ranks the supplied posts by content relevance.

For the programming/AI example, this model returns the Python friend post, AI
news, food post, then football news. All **7 synthetic smoke cases** in
`docs/examples/recommendation-smoke-cases.json` pass: four Vietnamese cases
including cold interests, and three English cases. These are examples, not a
Vietnamese quality benchmark or real-user outcome measurement.

## Evidence and verification

Local artifacts under `artifacts/models/mind-large-20260927-r2/`:

- `model/`: version **mind-large-20260927-r2-nrms**; model SHA-256
  `e771b05f65e5eff69607d73c74921485f047606127e9f940310522766f5f5123`.
- `protocol.json`: declared parameters and source commit before final scoring.
- `dataset.json`, `embeddings.npz`, private `identity-salt`: reproducible local
  data with article vectors stored once. Keep the salt private.
- `report.json`: training trace, full held-out metrics, segments and confidence
  interval. Aggregate evidence is also committed in
  `docs/reports/mind-large-20260927-r2.json`.
- `multilingual-smoke.json`, `recommendation-demo.json`: synthetic relevance results.
- `serving-check.json`: actual API artifact loader and shadow scorer passed,
  offline/serving maximum score difference **0**, displayed heuristic scores
  preserved. Local 300-candidate inference p95 was **2.64 ms** over 30 calls,
  excluding database, network and text embedding time.

**151 AI tests and 87 API tests passed** on the isolated branch using the committed
fixtures; one opt-in PostgreSQL test was skipped. Coverage for the updated training/data modules is **92.29%**. The user's
staged fixture deletions and frontend changes were preserved. The opt-in live
PostgreSQL test remains skipped; OrbStack's Docker socket is unavailable.

## Continue training with an untouched holdout

Use a new output directory and exclude **both** evaluated datasets:

```bash
uv run --with-requirements ai_pipeline/requirements.training.txt \
  python -m ai_pipeline.mind_large \
  --data-dir 'data _train ' \
  --output artifacts/models/mind-large-next \
  --model-dir "$MODEL_DIR" --device mps \
  --train-requests 50000 --test-requests 10000 --seed 20260929 \
  --exclude-holdout artifacts/models/mind-large-20260927/dataset.json \
  --exclude-holdout artifacts/models/mind-large-20260927-r2/dataset.json \
  --epochs 12 --learning-rates 0.001 0.01 --batch-size 128 \
  --preserve-semantics
```

Further social-feed fine-tuning requires real follows, visible impressions,
clicks/qualified reads, negative feedback, timestamps and content snapshots.
No production configuration, deployment, or service restart was performed.
