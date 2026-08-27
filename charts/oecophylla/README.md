# Oecophylla Helm chart

This chart deploys all Oecophylla application services, workers, Envoy and the
frontend. PostgreSQL, Redis and Kafka can be external (recommended for
production) or installed as single-node StatefulSets for a sandbox.

## Prerequisites

- Kubernetes 1.27+
- Helm 3.12+
- An ingress controller when `ingress.enabled=true`
- Images for every repository under `components` and the migration image

The eight Rust services share one `cargo-chef` dependency layer. Build them from
the repository root with the resource-limited BuildKit builder:

```bash
docker buildx inspect oecophylla-limited >/dev/null 2>&1 || \
  docker buildx create --name oecophylla-limited \
    --driver docker-container --buildkitd-config buildkitd.toml --use
IMAGE_TAG=TAG docker buildx bake \
  --builder oecophylla-limited -f docker-bake.hcl --load backend
```

Build the migration image and the non-Rust application images:

```bash
docker build -f migrations/Dockerfile -t REGISTRY/oecophylla/migrate:TAG migrations
docker compose --env-file .env.example build \
  recommendation-api analytics-service feature-store-worker nlp-worker frontend
```

Tag and push every image to the target registry, then replace all
`ghcr.io/your-org/...` repositories and tags (or immutable digests) in an
environment-specific values file.

## Production install

Create a secret with the exact connection strings and JWT secret:

```bash
kubectl -n oecophylla create secret generic oecophylla-runtime \
  --from-literal=DATABASE_URL='postgres://USER:PASSWORD@HOST:5432/oecophylla?sslmode=require' \
  --from-literal=REDIS_URL='redis://:PASSWORD@HOST:6379/0' \
  --from-literal=JWT_SECRET='REPLACE_WITH_AT_LEAST_32_RANDOM_CHARACTERS'

helm upgrade --install oecophylla ./charts/oecophylla \
  --namespace oecophylla --create-namespace \
  -f charts/oecophylla/values.production.example.yaml \
  --set secrets.existingSecret=oecophylla-runtime \
  --wait --wait-for-jobs --timeout 15m
```

When using `secrets.existingSecret`, bundled infrastructure is not appropriate
unless that Secret also contains `POSTGRES_PASSWORD` and `REDIS_PASSWORD`.

## Sandbox install

```bash
helm upgrade --install oecophylla ./charts/oecophylla \
  --namespace oecophylla --create-namespace \
  -f charts/oecophylla/values.orbstack.yaml \
  --set-string secrets.databasePassword='local-db-password' \
  --set-string secrets.redisPassword='local-redis-password' \
  --set-string secrets.jwtSecret='local-only-jwt-secret-at-least-32-chars' \
  --wait --wait-for-jobs --timeout 15m
```

The bundled data services are intentionally single-node and are meant for
development only.

Keep the original sandbox credentials when upgrading a release whose database
PVC already exists. Resetting the Helm values does not change PostgreSQL's
persisted password:

```bash
helm upgrade oecophylla ./charts/oecophylla \
  --namespace oecophylla --reuse-values \
  --wait --wait-for-jobs --timeout 15m
```

Every application pod runs the idempotent SQLx migrator as an init container,
so no service becomes ready against an old schema. The chart also creates a
revisioned migration Job for operational visibility.

## Validation

```bash
helm lint ./charts/oecophylla
helm template oecophylla ./charts/oecophylla > /tmp/oecophylla.yaml
helm template oecophylla ./charts/oecophylla --set infrastructure.enabled=true > /tmp/oecophylla-sandbox.yaml
docker run --rm --entrypoint ldd oecophylla-auth-service:TAG /usr/local/bin/auth-service
docker run --rm --entrypoint sh oecophylla-auth-service:TAG -c \
  'id && ! command -v cargo && ! command -v rustc'
```

Run the `ldd` check for every Rust image. Install `libssl3t64` or `libpq5` in
the Trixie runtime only if the corresponding `libssl.so.3` or `libpq.so.5`
entry appears. The current Rust binaries use rustls/native Rust PostgreSQL and
need neither library.

`notification-service` defaults to one replica because its SSE fan-out state is
in-process. Do not scale it until fan-out is backed by a shared service.
