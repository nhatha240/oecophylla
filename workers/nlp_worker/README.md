# NLP worker multilingual embeddings

The worker keeps keyword topics as the serving-safe fallback and optionally
adds immutable `post-content-features-v1` rows for created and updated posts.
Embedding failures never remove or replace `posts.topics`.

## Pinned model

- Encoder: `intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3`
- License: MIT
- Artifact: `model.safetensors`
- SHA-256: `1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477`
- Output: 384 float32 values, L2-normalized
- Preprocessing: `post-content-normalization-v1`, then the E5 `passage: ` prefix

Runtime model libraries are pinned in `requirements.runtime.txt`. The model is
loaded with `trust_remote_code=False`, the artifact checksum is verified before
load, and only the immutable repository revision above may be downloaded.

For production, build the image with `NLP_MODEL_PREFETCH=true`. This stores the
verified model in `/opt/models/multilingual-e5-small`; leave
`EMBEDDING_ALLOW_DOWNLOAD=false` so pods do not depend on outbound network
access. Local Compose may download the same pinned revision lazily. Set
`EMBEDDING_INFERENCE_ENABLED=false` for rollback; event consumption and keyword
topic inference continue.

## Rebuild

Run from `workers/nlp_worker`:

```bash
uv run --with-requirements requirements.txt \
  python -m app.rebuild --checkpoint /private/state/nlp-rebuild.json
```

The append-only uniqueness key makes a restarted scan idempotent. The private
checkpoint advances only after every item in a batch reaches `created` or
`unchanged`. An exhausted topic fallback is reported as a rebuild failure,
leaves the durable checkpoint behind, and stops the current scan so the next
invocation retries the incomplete range instead of skipping ahead.

Kafka offsets are committed manually only after an event reaches `created`,
`unchanged`, or the deliberate topic `fallback`. A fallback is acknowledged
because keyword topics have already been retained on the post; embedding
catch-up is owned by the rebuild command above. The rebuild exits non-zero and
does not advance its checkpoint when the model or storage remains unavailable.
Unexpected processing failures and shutdown-buffered events stay uncommitted
for Kafka replay, and cleanup never runs the same in-memory batch a second time.
Batch size, concurrency, retry count, backoff, Torch thread count, and CPU/memory
limits are controlled by the `EMBEDDING_*` settings plus container resources.
Progress logs contain aggregate counts only, never post or user identities.

Prometheus exposes inference latency, outcomes/missingness, bounded failure
reasons, encoder version labels, and rebuild lag on port 9109.
