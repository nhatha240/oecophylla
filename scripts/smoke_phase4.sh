#!/usr/bin/env bash
# Phase 4 smoke test — observability + analytics + evaluation
set -euo pipefail

# Load DATABASE_URL from .env if not already set
if [ -z "${DATABASE_URL:-}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [ -f "$SCRIPT_DIR/../.env" ]; then
    export $(grep -E '^DATABASE_URL=' "$SCRIPT_DIR/../.env" | xargs)
  fi
fi

BASE="http://localhost:8080"
ADMIN_SVC="http://localhost:8006"
METRICS_ENDPOINTS=(
  "http://localhost:8001/metrics"
  "http://localhost:8002/metrics"
  "http://localhost:8003/metrics"
  "http://localhost:8004/metrics"
  "http://localhost:8005/metrics"
  "http://localhost:8006/metrics"
  "http://localhost:8007/metrics"
)
# Python services use prometheus_client which has different metric names
PYTHON_METRICS_ENDPOINTS=(
  "http://localhost:8091/metrics"
)
PASS=0
FAIL=0

check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo "  ✓ $label"
    ((PASS++))
  else
    echo "  ✗ $label"
    ((FAIL++))
  fi
}

echo "=== Phase 4 Smoke Test ==="

# --- 1. Metrics endpoints return real Prometheus data ---
echo ""
echo "--- 1. Service /metrics endpoints ---"
for ep in "${METRICS_ENDPOINTS[@]}"; do
  svc=$(echo "$ep" | sed 's|http://localhost:||;s|/metrics||')
  body=$(curl -sf "$ep" 2>/dev/null || true)
  if echo "$body" | grep -q "http_requests_total"; then
    echo "  ✓ :$svc/metrics has http_requests_total"
    ((PASS++))
  else
    echo "  ✗ :$svc/metrics missing http_requests_total"
    ((FAIL++))
  fi
done
for ep in "${PYTHON_METRICS_ENDPOINTS[@]}"; do
  svc=$(echo "$ep" | sed 's|http://localhost:||;s|/metrics||')
  body=$(curl -sf "$ep" 2>/dev/null || true)
  if echo "$body" | grep -q "python_info\|process_"; then
    echo "  ✓ :$svc/metrics has prometheus_client metrics"
    ((PASS++))
  else
    echo "  ✗ :$svc/metrics missing prometheus_client metrics"
    ((FAIL++))
  fi
done

# --- 2. Analytics service dashboard endpoint ---
echo ""
echo "--- 2. Analytics service ---"
check "analytics /health" curl -sf http://localhost:8091/health
dashboard=$(curl -sf http://localhost:8091/admin/dashboard 2>/dev/null || echo "{}")
for field in total_users total_posts total_interactions pending_reports; do
  if echo "$dashboard" | grep -q "\"$field\""; then
    echo "  ✓ dashboard has $field"
    ((PASS++))
  else
    echo "  ✗ dashboard missing $field"
    ((FAIL++))
  fi
done

# --- 3. Admin /metrics on moderation-service ---
echo ""
echo "--- 3. Moderation /admin/metrics ---"
# Register a user, promote to admin, get cookie
SUFIX=$(python3 -c "import uuid; print(uuid.uuid4().hex[:8])")
REG=$(curl -sf -c /tmp/p4jar "$BASE/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"adm_${SUFIX}\",\"email\":\"adm_${SUFIX}@t.local\",\"password\":\"Pass!1234\"}" 2>/dev/null || echo "{}")
if echo "$REG" | grep -q '"username"'; then
  echo "  ✓ registered admin user"
  ((PASS++))
else
  echo "  ✗ registration failed"
  ((FAIL++))
fi

# Promote to admin via SQL (through postgres container)
PGUSER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
PGDB=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')
docker compose exec -T postgres psql -U "$PGUSER" -d "$PGDB" -c \
  "UPDATE users SET role='admin' WHERE username='adm_${SUFIX}'" >/dev/null 2>&1 || true

# Re-login to get admin cookie
curl -sf -c /tmp/p4jar "$BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email_or_username\":\"adm_${SUFIX}\",\"password\":\"Pass!1234\"}" >/dev/null 2>&1 || true

# Test /admin/metrics
admin_metrics=$(curl -sf -b /tmp/p4jar "$ADMIN_SVC/admin/metrics" 2>/dev/null || echo "{}")
for field in total_users total_posts total_interactions pending_reports; do
  if echo "$admin_metrics" | grep -q "\"$field\""; then
    echo "  ✓ /admin/metrics has $field"
    ((PASS++))
  else
    echo "  ✗ /admin/metrics missing $field"
    ((FAIL++))
  fi
done

# --- 4. Prometheus targets ---
echo ""
echo "--- 4. Prometheus scrape targets ---"
prom_targets=$(curl -sf "http://localhost:9090/api/v1/targets" 2>/dev/null || echo "{}")
for job in oecophylla-services recommendation-api analytics-service envoy; do
  if echo "$prom_targets" | grep -q "\"$job\""; then
    echo "  ✓ prometheus has job: $job"
    ((PASS++))
  else
    echo "  ✗ prometheus missing job: $job"
    ((FAIL++))
  fi
done

# --- 5. Grafana dashboard ---
echo ""
echo "--- 5. Grafana ---"
check "grafana /api/health" curl -sf http://localhost:3001/api/health

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -gt 0 ]; then
  echo "SOME CHECKS FAILED"
  exit 1
fi
echo "ALL CHECKS PASSED"
