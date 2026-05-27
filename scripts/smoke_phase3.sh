#!/usr/bin/env bash
# Phase 3 integration smoke. Walks moderation (report -> admin resolve -> audit),
# notifications (liked + post_hidden -> unread count), and NLP topic enrichment.
# Requires `docker compose -f compose.yaml -f compose.dev.yaml up -d`.
set -euo pipefail

ENVOY="${ENVOY:-http://localhost:8080}"
CK_A="${CK_A:-/tmp/oec_p3_a.txt}"   # reporter
CK_B="${CK_B:-/tmp/oec_p3_b.txt}"   # author
CK_C="${CK_C:-/tmp/oec_p3_c.txt}"   # admin
PSQL=(docker compose exec -T postgres psql -U "${POSTGRES_USER:-oecophylla}" -d "${POSTGRES_DB:-oecophylla}" -tAc)

cleanup() { rm -f "$CK_A" "$CK_B" "$CK_C"; }
trap cleanup EXIT

wait_for_envoy() {
  local status
  for _ in $(seq 1 30); do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$ENVOY/api/v1/feed?limit=1" || true)
    if [[ "$status" == "401" ]]; then
      return 0
    fi
    sleep 1
  done
  echo "FAIL: envoy/feed stack not ready at $ENVOY"
  return 1
}

rand_user_suffix() {
  uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c23-32
}

register() {
  # $1 = cookie jar, $2 = username
  curl -fsS -c "$1" -b "$1" -X POST "$ENVOY/api/v1/auth/register" \
    -H 'content-type: application/json' \
    -d "{\"username\":\"$2\",\"email\":\"$2@e.com\",\"password\":\"Password!123\"}" >/dev/null
}

login() {
  # $1 = cookie jar, $2 = email_or_username
  curl -fsS -c "$1" -b "$1" -X POST "$ENVOY/api/v1/auth/login" \
    -H 'content-type: application/json' \
    -d "{\"email_or_username\":\"$2\",\"password\":\"Password!123\"}" >/dev/null
}

wait_for_envoy

UA="a$(rand_user_suffix)"
UB="b$(rand_user_suffix)"
UC="c$(rand_user_suffix)"

echo "1. Register reporter ($UA), author ($UB), admin ($UC)."
register "$CK_A" "$UA"
register "$CK_B" "$UB"
register "$CK_C" "$UC"
echo "   ok"

echo "2. Promote $UC to admin and re-login for an admin-role token."
"${PSQL[@]}" "UPDATE users SET role='admin' WHERE username='$UC'" >/dev/null
login "$CK_C" "$UC"
echo "   ok"

echo "3. Author publishes a post."
post_id=$(curl -fsS -c "$CK_B" -b "$CK_B" -X POST "$ENVOY/api/v1/posts" \
  -H 'content-type: application/json' -d '{"content":"phase 3 smoke post"}' | jq -r '.id')
echo "   post_id=$post_id"

echo "4. Reporter likes the post (baseline 'liked' notification for author)."
curl -fsS -c "$CK_A" -b "$CK_A" -X POST "$ENVOY/api/v1/posts/$post_id/like" >/dev/null
echo "   ok"

echo "5. Reporter reports the post."
curl -fsS -c "$CK_A" -b "$CK_A" -X POST "$ENVOY/api/v1/posts/$post_id/report" \
  -H 'content-type: application/json' -d '{"reason":"spam","detail":"smoke report"}' >/dev/null
echo "   ok"

echo "6. Admin GET /admin/reports shows the pending report."
reports=$(curl -fsS -c "$CK_C" -b "$CK_C" "$ENVOY/admin/reports?status=pending&limit=50")
report_id=$(echo "$reports" | jq -r --arg pid "$post_id" '.items[] | select(.post_id==$pid) | .id' | head -n1)
if [[ -z "$report_id" || "$report_id" == "null" ]]; then
  echo "   FAIL: pending report for $post_id not found"
  exit 1
fi
echo "   report_id=$report_id"

echo "7. Admin resolves report with hide_post."
curl -fsS -c "$CK_C" -b "$CK_C" -X POST "$ENVOY/admin/reports/$report_id/resolve" \
  -H 'content-type: application/json' -d '{"action":"hide_post","note":"smoke hide"}' >/dev/null
echo "   ok"

echo "8. Post status should now be 'hidden'."
status=$("${PSQL[@]}" "SELECT status FROM posts WHERE id='$post_id'")
if [[ "$status" != "hidden" ]]; then
  echo "   FAIL: expected hidden, got '$status'"
  exit 1
fi
echo "   ok"

echo "9. Audit log should have a post_hidden row for this report."
audit_n=$("${PSQL[@]}" "SELECT count(*) FROM audit_logs WHERE report_id='$report_id' AND action='post_hidden'")
if [[ "$audit_n" -lt 1 ]]; then
  echo "   FAIL: expected >=1 audit row, got $audit_n"
  exit 1
fi
echo "   ok (audit rows=$audit_n)"

echo "10. Author's unread notification count should be >=1 (liked + post_hidden)."
unread=0
for _ in $(seq 1 10); do
  unread=$(curl -fsS -c "$CK_B" -b "$CK_B" "$ENVOY/api/v1/notifications/unread-count" | jq -r '.count // .unread_count // 0')
  [[ "$unread" -ge 1 ]] && break
  sleep 0.5
done
if [[ "$unread" -lt 1 ]]; then
  echo "   FAIL: expected unread>=1, got $unread"
  exit 1
fi
echo "   ok (unread=$unread)"

echo "11. Author should have a post_hidden notification."
have_hidden=""
for _ in $(seq 1 10); do
  have_hidden=$(curl -fsS -c "$CK_B" -b "$CK_B" "$ENVOY/api/v1/notifications?limit=20" \
    | jq -r '.items[] | select(.kind=="post_hidden") | .id' | head -n1)
  [[ -n "$have_hidden" && "$have_hidden" != "null" ]] && break
  sleep 0.5
done
if [[ -z "$have_hidden" || "$have_hidden" == "null" ]]; then
  echo "   FAIL: no post_hidden notification for author"
  exit 1
fi
echo "   ok"

echo "12. NLP worker enriches topics: post with 'trí tuệ nhân tạo' should get 'ai'."
nlp_post=$(curl -fsS -c "$CK_B" -b "$CK_B" -X POST "$ENVOY/api/v1/posts" \
  -H 'content-type: application/json' -d '{"content":"Bài viết về trí tuệ nhân tạo"}' | jq -r '.id')
got_ai=""
for _ in $(seq 1 10); do
  got_ai=$("${PSQL[@]}" "SELECT 1 FROM posts WHERE id='$nlp_post' AND topics @> ARRAY['ai']::text[]")
  [[ "$got_ai" == "1" ]] && break
  sleep 0.5
done
if [[ "$got_ai" != "1" ]]; then
  topics=$("${PSQL[@]}" "SELECT topics FROM posts WHERE id='$nlp_post'")
  echo "   FAIL: expected topics to contain 'ai', got '$topics'"
  exit 1
fi
echo "   ok"

echo "Phase 3 smoke OK."
