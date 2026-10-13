"""API surface tests."""

from __future__ import annotations

from apps.api.main import create_app
from fastapi.testclient import TestClient


def test_version_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["name"] == "CloudCostLens"


def test_meta_endpoint_marks_demo_mode_and_flags() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["demo_mode"] is True
    assert body["feature_flags"]["execution_enabled"] is False
    assert body["feature_flags"]["auth_enabled"] is False


def test_openapi_schema_available() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"].startswith("CloudCostLens")
