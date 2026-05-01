"""HTTP-level tests for the Phase-2 ``/api/cases`` routes."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from scafad.gui.backend.config import GUISettings  # noqa: E402
from scafad.gui.backend.main import create_app  # noqa: E402
from scafad.gui.backend.store import DetectionStore  # noqa: E402


@pytest.fixture
def app_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = GUISettings(db_path=tmp_path / "cases-routes.db", env="test")
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


def _seed_detections(app, n: int = 3) -> list[str]:
    store: DetectionStore = app.state.store
    ids: list[str] = []
    for i in range(n):
        row = store.insert_detection(
            event_id=f"ev-{i}",
            function_id=f"fn-{i % 2}",
            anomaly_type="memory_spike",
            severity="review" if i % 2 == 0 else "escalate",
            trust_score=0.5,
            mitre_techniques=[f"T100{i}"],
            layer_payload={"layer0_record": {"event_id": f"ev-{i}"}},
        )
        ids.append(row.id)
    return ids


def test_create_and_list_case(app_client: TestClient) -> None:
    payload = {"title": "First case"}
    resp = app_client.post("/api/cases", json=payload)
    assert resp.status_code == 201
    case = resp.json()
    assert case["title"] == "First case"
    assert case["status"] == "open"
    assert case["version"] == 1

    list_resp = app_client.get("/api/cases")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == case["id"]


def test_get_case_404(app_client: TestClient) -> None:
    assert app_client.get("/api/cases/no-such").status_code == 404


def test_patch_case_state_transition(app_client: TestClient) -> None:
    case = app_client.post("/api/cases", json={"title": "X"}).json()
    resp = app_client.patch(
        f"/api/cases/{case['id']}",
        json={"expected_version": case["version"], "status": "triage"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "triage"
    assert resp.json()["version"] == 2


def test_patch_case_409_on_version_conflict(app_client: TestClient) -> None:
    case = app_client.post("/api/cases", json={"title": "X"}).json()
    resp = app_client.patch(
        f"/api/cases/{case['id']}",
        json={"expected_version": 999, "status": "triage"},
    )
    assert resp.status_code == 409


def test_patch_case_404_when_missing(app_client: TestClient) -> None:
    resp = app_client.patch(
        "/api/cases/missing",
        json={"expected_version": 1, "status": "triage"},
    )
    assert resp.status_code == 404


def test_delete_case_returns_204(app_client: TestClient) -> None:
    case = app_client.post("/api/cases", json={"title": "X"}).json()
    resp = app_client.delete(f"/api/cases/{case['id']}")
    assert resp.status_code == 204
    assert app_client.get(f"/api/cases/{case['id']}").status_code == 404


def test_attach_and_detach_detections(app_client: TestClient) -> None:
    ids = _seed_detections(app_client.app, n=3)
    case = app_client.post("/api/cases", json={"title": "X"}).json()
    attach = app_client.post(
        f"/api/cases/{case['id']}/attach",
        json={"detection_ids": ids},
    ).json()
    assert attach["succeeded"] == 3
    assert attach["failed"] == 0
    detach = app_client.post(
        f"/api/cases/{case['id']}/detach",
        json={"detection_ids": [ids[0]]},
    ).json()
    assert detach["succeeded"] == 1


def test_attach_to_unknown_case_404(app_client: TestClient) -> None:
    ids = _seed_detections(app_client.app, n=1)
    resp = app_client.post(
        "/api/cases/no-such/attach",
        json={"detection_ids": ids},
    )
    assert resp.status_code == 404


def test_attach_empty_list_422(app_client: TestClient) -> None:
    case = app_client.post("/api/cases", json={"title": "X"}).json()
    resp = app_client.post(
        f"/api/cases/{case['id']}/attach", json={"detection_ids": []}
    )
    assert resp.status_code == 422


def test_attach_already_attached_returns_per_item_error(app_client: TestClient) -> None:
    ids = _seed_detections(app_client.app, n=1)
    case = app_client.post("/api/cases", json={"title": "X"}).json()
    app_client.post(
        f"/api/cases/{case['id']}/attach", json={"detection_ids": ids}
    )
    second = app_client.post(
        f"/api/cases/{case['id']}/attach", json={"detection_ids": ids}
    ).json()
    assert second["succeeded"] == 0
    assert second["failed"] == 1


def test_list_case_events_returns_created_event(app_client: TestClient) -> None:
    case = app_client.post("/api/cases", json={"title": "X"}).json()
    body = app_client.get(f"/api/cases/{case['id']}/events").json()
    assert body["total"] >= 1
    assert any(e["kind"] == "created" for e in body["items"])


def test_post_and_list_comments(app_client: TestClient) -> None:
    case = app_client.post("/api/cases", json={"title": "X"}).json()
    add = app_client.post(
        f"/api/cases/{case['id']}/comments", json={"body_md": "**hello**"}
    )
    assert add.status_code == 201
    comments = app_client.get(f"/api/cases/{case['id']}/comments").json()
    assert comments["total"] == 1
    assert comments["items"][0]["body_md"] == "**hello**"


def test_list_linked_detections(app_client: TestClient) -> None:
    ids = _seed_detections(app_client.app, n=2)
    case = app_client.post(
        "/api/cases", json={"title": "X", "detection_ids": ids}
    ).json()
    body = app_client.get(f"/api/cases/{case['id']}/detections").json()
    assert body["total"] == 2


def test_create_case_with_already_attached_detection_409(app_client: TestClient) -> None:
    ids = _seed_detections(app_client.app, n=1)
    app_client.post("/api/cases", json={"title": "X", "detection_ids": ids})
    resp = app_client.post("/api/cases", json={"title": "Y", "detection_ids": ids})
    assert resp.status_code == 409


def test_filter_cases_by_status(app_client: TestClient) -> None:
    a = app_client.post("/api/cases", json={"title": "A"}).json()
    app_client.post("/api/cases", json={"title": "B"})
    app_client.patch(
        f"/api/cases/{a['id']}",
        json={"expected_version": a["version"], "status": "closed"},
    )
    body = app_client.get("/api/cases", params={"status": "open"}).json()
    assert body["total"] == 1
    body = app_client.get("/api/cases", params={"status": "closed"}).json()
    assert body["total"] == 1
