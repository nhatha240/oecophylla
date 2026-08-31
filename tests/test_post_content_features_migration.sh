#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target_migration="20260831000019_post_content_features.sql"
container_name="oecophylla-t4a-contract-$$"

cleanup() {
  docker rm -f "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for the PostgreSQL migration contract test" >&2
  exit 77
fi

docker run --name "$container_name" \
  -e POSTGRES_DB=oecophylla_contract \
  -e POSTGRES_USER=oecophylla_contract \
  -e POSTGRES_PASSWORD=contract-local-only \
  -d postgres:18-trixie >/dev/null

ready=false
for _attempt in {1..30}; do
  if docker exec "$container_name" \
    psql -v ON_ERROR_STOP=1 -At \
      -U oecophylla_contract -d oecophylla_contract \
      -c "SELECT 1" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  echo "PostgreSQL test container did not become ready" >&2
  exit 1
fi

for migration_path in "$repo_root"/migrations/*.sql; do
  migration_name="${migration_path##*/}"
  if [[ "$migration_name" == "$target_migration" ]]; then
    break
  fi
  docker exec -i "$container_name" \
    psql -v ON_ERROR_STOP=1 \
      -U oecophylla_contract -d oecophylla_contract \
      < "$migration_path" >/dev/null
done

docker exec "$container_name" \
  psql -v ON_ERROR_STOP=1 \
    -U oecophylla_contract -d oecophylla_contract \
    -c "INSERT INTO users (id, username, email, password_hash) VALUES ('10000000-0000-4000-8000-000000000099','pre_t4a_user','pre-t4a@example.invalid','fixture'); INSERT INTO posts (id, author_id, content, topics, status) VALUES ('20000000-0000-4000-8000-000000000099','10000000-0000-4000-8000-000000000099','Bài viết tồn tại trước migration.',ARRAY['thời sự'],'published');" \
    >/dev/null

docker exec -i "$container_name" \
  psql -v ON_ERROR_STOP=1 \
    -U oecophylla_contract -d oecophylla_contract \
    < "$repo_root/migrations/$target_migration" >/dev/null

preserved_count="$({
  docker exec "$container_name" \
    psql -v ON_ERROR_STOP=1 -At \
      -U oecophylla_contract -d oecophylla_contract \
      -c "SELECT count(*) FROM posts p LEFT JOIN post_content_features f ON f.post_id=p.id WHERE p.id='20000000-0000-4000-8000-000000000099' AND f.id IS NULL;"
})"
if [[ "$preserved_count" != "1" ]]; then
  echo "existing post was not preserved without a feature row" >&2
  exit 1
fi

docker exec -i "$container_name" \
  psql -v ON_ERROR_STOP=1 \
    -U oecophylla_contract -d oecophylla_contract \
    < "$repo_root/tests/fixtures/post_content_features/migration_contract.sql" \
    >/dev/null

echo "post content feature PostgreSQL migration contract passed"
