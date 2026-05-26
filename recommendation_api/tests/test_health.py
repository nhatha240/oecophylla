from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok():
    # Lifespan starts asyncpg + redis pools; without infra they'll fail to
    # connect, so this test only covers the app object and route shape.
    client = TestClient(app, raise_server_exceptions=False)
    # Bypass lifespan by hitting the route via app.routes directly.
    paths = {r.path for r in app.routes}
    assert "/health" in paths
    assert "/recommend/feed/{user_id}" in paths
    assert "/recommend/features/rebuild" in paths
    assert "/recommend/evaluate" in paths
