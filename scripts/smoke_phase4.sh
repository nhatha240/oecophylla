#!/usr/bin/env bash
# Smoke test for Phase 4 deliverables: analytics, Prometheus metrics on every
# service, the recommendations impression log, seed + offline evaluation.
#
# Assumes the stack is up with the dev port overlay:
#   docker compose -f compose.yaml -f compose.dev.yaml up -d --build
#   bash scripts/smoke_phase4.sh
set -u

PASS=0
FAIL=0
green() { printf '\033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS + 1)); }
red()   { printf '\033[31m✗\033[0m %s\n' "$1"; FAIL=$((FAIL + 1)); }

# Load PG creds for psql checks (best-effort).
[ -f .env ] && set -a && . ./.env && set +a

http_code() { curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$1" 2>/dev/null; }
metric_present() { curl -s --max-time 5 "$1/metrics" 2>/dev/null | grep -q "$2"; }

echo "== Prometheus metrics on Rust services =="
declare -A RUST=(
  [auth-service]=8001 [user-service]=8002 [content-service]=8003
  [interaction-service]=8004 [feed-service]=8005 [moderation-service]=8006
  [notification-service]=8007
)
for svc in "${!RUST[@]}"; do
  port=${RUST[$svc]}
  if metric_present "http://localhost:$port" "http_requests_total"; then
    green "$svc exports http_requests_total"
  else
    red "$svc missing /metrics http_requests_total (port $port)"
  fi
done

echo "== Python services =="
if [ "$(http_code http://localhost:8090/health)" = "200" ]; then
  green "recommendation-api /health 200"
else
  red "recommendation-api /health not 200"
fi
if [ "$(http_code http://localhost:8091/health)" = "200" ]; then
  green "analytics-service /health 200"
else
  red "analytics-service /health not 200"
fi
if metric_present "http://localhost:8091" "python_info\|process_"; then
  green "analytics-service exports Prometheus metrics"
else
  red "analytics-service /metrics empty"
fi

echo "== Analytics admin guard =="
code=$(http_code http://localhost:8091/admin/dashboard)
if [ "$code" = "401" ] || [ "$code" = "403" ]; then
  green "/admin/dashboard rejects unauthenticated ($code)"
else
  red "/admin/dashboard NOT guarded (got $code, expected 401/403)"
fi

echo "== Prometheus =="
if [ "$(http_code http://localhost:9090/-/healthy)" = "200" ]; then
  green "prometheus healthy"
else
  red "prometheus not healthy on :9090"
fi

echo "== Grafana dashboard JSON =="
if [ -f infra/grafana/dashboards/oecophylla-overview.json ]; then
  panels=$(grep -o '"type"' infra/grafana/dashboards/oecophylla-overview.json | wc -l | tr -d ' ')
  green "grafana dashboard present (~$panels panel entries)"
else
  red "grafana dashboard JSON missing"
fi

echo "== recommendations table + seed data (psql) =="
psql_q() { docker compose exec -T postgres psql -U "${POSTGRES_USER:-oecophylla}" -d "${POSTGRES_DB:-oecophylla}" -tAc "$1" 2>/dev/null; }
if [ "$(psql_q "SELECT to_regclass('public.recommendations') IS NOT NULL")" = "t" ]; then
  green "recommendations table exists"
else
  red "recommendations table missing (run migrate)"
fi
users=$(psql_q "SELECT count(*) FROM users WHERE username LIKE 'seed_user_%'")
if [ "${users:-0}" -ge 1 ] 2>/dev/null; then
  green "seed users present ($users)"
else
  red "no seed users — run: make seed"
fi

echo "== Offline evaluation =="
if docker compose --profile tools run --rm scripts evaluate.py --k 10 2>/dev/null | grep -q "Precision@10"; then
  green "scripts/evaluate.py produced metrics"
else
  red "scripts/evaluate.py did not produce metrics (seed first?)"
fi

echo
echo "== Summary: $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ]
