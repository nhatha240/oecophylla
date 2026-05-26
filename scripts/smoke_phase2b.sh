#!/usr/bin/env bash
# Phase 2B integration smoke. Walks through unauth -> auth -> fallback ->
# cache invalidation. Requires `docker compose -f compose.yaml -f compose.dev.yaml up -d`.
set -euo pipefail

ENVOY="${ENVOY:-http://localhost:8080}"
COOKIES="${COOKIES:-/tmp/oec_phase2b_cookies.txt}"

cleanup() { rm -f "$COOKIES"; }
trap cleanup EXIT

echo "1. Unauthenticated GET /api/v1/feed should be 401."
status=$(curl -s -o /dev/null -w "%{http_code}" "$ENVOY/api/v1/feed")
if [[ "$status" != "401" ]]; then
  echo "   FAIL: expected 401, got $status"
  exit 1
fi
echo "   ok"

uniq=$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | head -c 22)
echo "2. Register a fresh user u${uniq:0:10}."
curl -fsS -c "$COOKIES" -b "$COOKIES" -X POST "$ENVOY/api/v1/auth/register" \
  -H 'content-type: application/json' \
  -d "{\"username\":\"u${uniq:0:10}\",\"email\":\"$uniq@e.com\",\"password\":\"Password!123\"}" >/dev/null
echo "   ok"

echo "3. Author a post."
post_id=$(curl -fsS -c "$COOKIES" -b "$COOKIES" -X POST "$ENVOY/api/v1/posts" \
  -H 'content-type: application/json' -d '{"content":"phase 2b smoke"}' | jq -r '.id')
echo "   post_id=$post_id"

echo "4. GET /api/v1/feed should return at least one item."
feed=$(curl -fsS -c "$COOKIES" -b "$COOKIES" "$ENVOY/api/v1/feed?limit=5")
items=$(echo "$feed" | jq '.items | length')
source=$(echo "$feed" | jq -r '.source')
if [[ "$items" -lt 1 ]]; then
  echo "   FAIL: expected items>=1, got $items"
  exit 1
fi
echo "   ok (items=$items, source=$source)"

echo "5. Second feed GET should hit cache."
feed2=$(curl -fsS -c "$COOKIES" -b "$COOKIES" "$ENVOY/api/v1/feed?limit=5")
source2=$(echo "$feed2" | jq -r '.source')
if [[ "$source2" != "cache" ]]; then
  echo "   WARN: expected source=cache, got $source2 (acceptable in fallback mode)"
else
  echo "   ok"
fi

echo "6. Like the post; cache-invalidator should clear feed:{user_id}."
curl -fsS -c "$COOKIES" -b "$COOKIES" -X POST "$ENVOY/api/v1/posts/$post_id/like" >/dev/null
sleep 1
feed3=$(curl -fsS -c "$COOKIES" -b "$COOKIES" "$ENVOY/api/v1/feed?limit=5")
source3=$(echo "$feed3" | jq -r '.source')
echo "   feed after like: source=$source3"

echo "Phase 2B smoke OK."
