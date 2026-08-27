# Docker build for the Rust workspace

All Rust services use `backend/Dockerfile`. The expensive dependency graph is
cooked once by `shared-dependencies`; each final target then compiles only its
own application crate.

```text
chef -> planner -> shared-dependencies -> source
                                             |-> auth-builder -> auth-service
                                             |-> user-builder -> user-service
                                             |-> interaction-builder -> interaction-service
                                             `-> other service builders and runtimes
```

## Create the limited builder

Compose/Bake target parallelism alone does not cap the number of BuildKit
vertices or Cargo compiler processes. Use the dedicated builder configuration
to enforce at most two active BuildKit vertices, and let each service build use
at most four Cargo jobs. On the 10 CPU / 8 GB build host this permits at most
about eight service compiler jobs at once, leaving memory and CPU headroom.

```sh
docker buildx create \
  --name oecophylla-limited \
  --driver docker-container \
  --buildkitd-config ./buildkitd.toml
docker buildx inspect --builder oecophylla-limited --bootstrap
```

If `buildkitd.toml` changes, remove and recreate only this named builder; an
existing builder does not reload the file automatically.

`CARGO_DEPS_JOBS` defaults to 8 because the dependency cook is a single shared
vertex. `CARGO_SERVICE_JOBS` defaults to 4 because two service builders may run
together. For tighter RAM limits, pass `--set '*.args.CARGO_SERVICE_JOBS=3'`.

## Normal build commands

Build and load one service into the local Docker image store:

```sh
docker buildx bake --builder oecophylla-limited \
  -f docker-bake.hcl --load auth-service
```

Other individual targets include `user-service`, `interaction-service`, and
`cache-invalidator`. Compose also knows each final target:

```sh
BUILDX_BUILDER=oecophylla-limited docker compose build auth-service
```

Build all backend targets and populate the shared builder cache:

```sh
docker buildx bake --builder oecophylla-limited \
  -f docker-bake.hcl --progress=plain backend
```

The command intentionally has no `--load`. With a `docker-container` builder,
loading many images makes BuildKit create and import several OCI tar streams at
once. For local use, populate the cache first and load images sequentially:

```sh
for target in \
  auth-service user-service content-service interaction-service \
  feed-service moderation-service notification-service cache-invalidator
do
  docker buildx bake --builder oecophylla-limited \
    -f docker-bake.hcl --load "$target"
done
```

In CI, use a registry output instead of local loading. Set registry-qualified
tags for the targets, then run:

```sh
IMAGE_TAG="$GIT_SHA" docker buildx bake --builder oecophylla-limited \
  -f docker-bake.hcl --push backend
```

## Repeatable benchmarks

A cold benchmark should use a new disposable builder. This avoids deleting the
developer's useful cache or the global Docker image store:

```sh
docker buildx create \
  --name oecophylla-cold \
  --driver docker-container \
  --buildkitd-config ./buildkitd.toml
docker buildx inspect --builder oecophylla-cold --bootstrap

/usr/bin/time -p docker buildx bake --builder oecophylla-cold \
  -f docker-bake.hcl --progress=plain backend
```

Repeat the same timed command for a warm full-workspace measurement:

```sh
/usr/bin/time -p docker buildx bake --builder oecophylla-cold \
  -f docker-bake.hcl --progress=plain backend
```

Benchmark an individual service, including loading its runtime image:

```sh
/usr/bin/time -p docker buildx bake --builder oecophylla-cold \
  -f docker-bake.hcl --load --progress=plain auth-service
```

When finished, `docker buildx rm oecophylla-cold` removes only that disposable
builder and its cache.

## Cache behavior

- `chef` changes when the Rust/Debian/cargo-chef versions or build tool install
  changes.
- `planner` sees the complete workspace source. Any source edit may rerun
  `cargo chef prepare`, but if manifests and `Cargo.lock` are unchanged its
  resulting `recipe.json` is identical, so `shared-dependencies` remains a hit.
- `shared-dependencies` cooks the whole workspace without `--package`. It is
  invalidated by a dependency manifest, lockfile, toolchain, profile, or cook
  argument change and is shared by every service target.
- `source` copies the workspace manifests and `crates/common`. A common-crate
  edit correctly invalidates all application builders.
- Each builder copies its own service directory. Editing only auth source
  invalidates `auth-builder` and the auth runtime copy, not the other service
  builders.
- Registry and git cache mounts reduce downloads, but are local to the BuildKit
  builder unless cache export/import is configured in CI.

The Dockerfile deliberately does not mount `/app/target`. The cooked target
tree is part of the `shared-dependencies` image layer and is inherited by every
builder, which is deterministic and exportable. A target cache mount can speed
some incremental builds, but it hides `/app/target` from the committed layer,
is builder-local, grows quickly, and can introduce contention when builders
share it. If one is added later, give it a deliberate cache ID and sharing
policy, mount it in both cook and build steps, and copy the final binary to
`/out` inside the same `RUN` before the mount disappears.

## Trade-offs and operational risks

Cooking the whole workspace means the first build of one small service pays for
all workspace dependencies and consumes a larger cache layer. That cost grows
with the workspace graph. It is a strong trade for this repository because all
services are commonly built together and subsequent individual builds reuse
the exact same dependency layer.

Keep both limits in place: BuildKit's `max-parallelism = 2` limits scheduler
vertices, while `CARGO_BUILD_JOBS` limits compiler processes inside each
vertex. A CLI target limit by itself does not guarantee either. Increasing
either limit on an 8 GB host can cause RAM contention, swapping, or OOM kills.
Also separate network time from compile time when interpreting cold results;
an empty registry/git cache makes a cold measurement sensitive to crates.io
latency.
