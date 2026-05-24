"""Smoke tests for the FastAPI composition root.

The construction test runs anywhere (no lifespan, no DB). The healthz test enters
the TestClient context, which runs the lifespan — that needs a reachable
``PG_DSN`` (``docker compose up``), so it is opt-in via ``--integration``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sdf_api.app import create_app


def test_app_exposes_health_routes() -> None:
    app = create_app()
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/healthz" in paths
    assert "/readyz" in paths


@pytest.mark.integration
def test_healthz_ok() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
