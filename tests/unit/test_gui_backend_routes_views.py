"""HTTP-level tests for the Phase-2 ``/api/views`` routes."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from scafad.gui.backend.config import GUISettings  # noqa: E402
from scafad.gui.backend.main import create_app  # noqa: E402


@pytest.fixture
def app_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = GUISettings(db_path=tmp_path / "views-routes.db", env="test")
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


def test_create_and_list_view(app_client: TestClient) -> None:
    resp = app_client.post(
        "/api/views",
        json={
            "name": "Critical only",
            "filter_json": {"severity": ["escalate"]},
            "pinned": True,
        },
    )
    assert resp.status_code == 201
    view = resp.json()
    assert view["pinned"] is True

    list_resp = app_client.get("/api/views").json()
    assert list_resp["total"] == 1
    assert list_resp["items"][0]["name"] == "Critical only"


def test_duplicate_view_name_returns_409(app_client: TestClient) -> None:
    payload = {"name": "A", "filter_json": {}}
    app_client.post("/api/views", json=payload)
    resp = app_client.post("/api/views", json=payload)
    assert resp.status_code == 409


def test_patch_view_changes_pinned(app_client: TestClient) -> None:
    view = app_client.post("/api/views", json={"name": "A", "filter_json": {}}).json()
    resp = app_client.patch(
        f"/api/views/{view['id']}", json={"pinned": True}
    )
    assert resp.status_code == 200
    assert resp.json()["pinned"] is True


def test_delete_view_returns_204(app_client: TestClient) -> None:
    view = app_client.post("/api/views", json={"name": "A", "filter_json": {}}).json()
    resp = app_client.delete(f"/api/views/{view['id']}")
    assert resp.status_code == 204
    assert app_client.get("/api/views").json()["total"] == 0


def test_patch_unknown_view_returns_404(app_client: TestClient) -> None:
    resp = app_client.patch("/api/views/no-such", json={"pinned": True})
    assert resp.status_code == 404


def test_list_views_isolated_per_owner(app_client: TestClient) -> None:
    # Create one view as the primary analyst.
    app_client.post("/api/views", json={"name": "A", "filter_json": {}})
    # Switch to the secondary analyst via X-Test-User; should see no views.
    resp = app_client.get(
        "/api/views", headers={"X-Test-User": "analyst-2@scafad.local"}
    )
    assert resp.json()["total"] == 0
