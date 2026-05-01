"""HTTP-level tests for the Phase-2 ``/api/inbox`` routes."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, List

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from scafad.gui.backend.config import GUISettings  # noqa: E402
from scafad.gui.backend.main import create_app  # noqa: E402
from scafad.gui.backend.store import DetectionStore  # noqa: E402


@pytest.fixture
def app_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = GUISettings(db_path=tmp_path / "inbox-routes.db", env="test")
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


def _seed(app, n: int = 5) -> List[str]:
    store: DetectionStore = app.state.store
    ids: List[str] = []
    sevs = ["observe", "review", "escalate"]
    for i in range(n):
        row = store.insert_detection(
            event_id=f"ev-{i}",
            function_id=f"fn-{i % 2}",
            anomaly_type="memory_spike" if i % 2 == 0 else "cpu_burst",
            severity=sevs[i % 3],
            trust_score=0.5,
            mitre_techniques=["T1059"] if i % 2 == 0 else ["T1071"],
            layer_payload={"layer0_record": {"event_id": f"ev-{i}"}},
        )
        ids.append(row.id)
    return ids


def test_inbox_summary_aggregates(app_client: TestClient) -> None:
    _seed(app_client.app, n=6)
    body = app_client.get("/api/inbox/summary").json()
    assert body["total"] == 6
    assert sum(body["severity_counts"].values()) == 6
    assert isinstance(body["top_mitre"], list)
    assert body["case_status_counts"]["none"] == 6


def test_inbox_summary_filtered_by_severity(app_client: TestClient) -> None:
    _seed(app_client.app, n=6)
    body = app_client.get("/api/inbox/summary", params={"severity": "escalate"}).json()
    assert body["total"] == 2


def test_bulk_open_case_creates_a_case(app_client: TestClient) -> None:
    ids = _seed(app_client.app, n=3)
    body = app_client.post(
        "/api/inbox/bulk_action",
        json={
            "action": "open_case",
            "detection_ids": ids,
            "payload": {"title": "Auto-opened"},
        },
    ).json()
    assert body["succeeded"] == 3
    assert body["case_id"]
    case_resp = app_client.get(f"/api/cases/{body['case_id']}").json()
    assert case_resp["title"] == "Auto-opened"
    assert case_resp["detection_count"] == 3


def test_bulk_attach_attaches_to_existing_case(app_client: TestClient) -> None:
    ids = _seed(app_client.app, n=3)
    case = app_client.post("/api/cases", json={"title": "Existing"}).json()
    body = app_client.post(
        "/api/inbox/bulk_action",
        json={
            "action": "attach",
            "detection_ids": ids,
            "payload": {"case_id": case["id"]},
        },
    ).json()
    assert body["succeeded"] == 3
    assert body["case_id"] == case["id"]


def test_bulk_assign_no_case_attached_records_no_case_error(app_client: TestClient) -> None:
    ids = _seed(app_client.app, n=2)
    body = app_client.post(
        "/api/inbox/bulk_action",
        json={
            "action": "assign",
            "detection_ids": ids,
            "payload": {"assignee_id": "alice"},
        },
    ).json()
    assert body["failed"] == 2
    assert all(r["error"] == "no_case_attached" for r in body["results"])


def test_bulk_action_requires_detection_ids(app_client: TestClient) -> None:
    resp = app_client.post(
        "/api/inbox/bulk_action",
        json={"action": "open_case", "detection_ids": [], "payload": {"title": "X"}},
    )
    assert resp.status_code == 422


def test_export_csv_returns_csv(app_client: TestClient) -> None:
    _seed(app_client.app, n=3)
    resp = app_client.get("/api/inbox/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    body = resp.text
    lines = [line for line in body.splitlines() if line]
    # header + 3 rows
    assert len(lines) == 4
    assert lines[0].startswith("id,ingested_at,event_id")


def test_export_csv_respects_filter(app_client: TestClient) -> None:
    _seed(app_client.app, n=6)
    resp = app_client.get(
        "/api/inbox/export.csv", params={"severity": "escalate"}
    )
    rows = [line for line in resp.text.splitlines() if line]
    # header + N (each severity has 2)
    assert len(rows) == 1 + 2
