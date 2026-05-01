"""End-to-end integration test for the Phase-2 Inbox → Case flow.

Scenario:

1. Ingest several events through ``POST /api/ingest`` (driving the real runtime).
2. List detections via ``GET /api/detections``.
3. Bulk-attach a slice via ``POST /api/inbox/bulk_action {action: open_case}``.
4. Transition the new case through ``triage`` then ``contained``.
5. Add a comment.
6. List the case events and assert the audit trail is correct.
7. Export the inbox as CSV and assert the row count matches the active filter.

A second scenario re-runs the bulk-action with an already-closed case to
exercise the per-item error path (ADR-11 partial-failure semantics).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, List

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from scafad.gui.backend.config import GUISettings  # noqa: E402
from scafad.gui.backend.main import create_app  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture
def app_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = GUISettings(db_path=tmp_path / "e2e.db", env="test")
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


def _ingest_batch(client: TestClient, n: int = 5) -> List[str]:
    ids: List[str] = []
    for i in range(n):
        body = client.post(
            "/api/ingest",
            json={
                "event_id": f"e2e-{i}",
                "function_id": f"fn-{i % 2}",
                "anomaly": "memory_spike" if i % 2 == 0 else "cpu_burst",
                "duration": 0.3 + 0.2 * i,
                "memory_spike_kb": 200_000 + i * 1000,
                "cpu_utilization": 70.0 + i * 2,
            },
        )
        assert body.status_code == 201, body.text
        ids.append(body.json()["id"])
    return ids


def test_full_triage_flow(app_client: TestClient) -> None:
    detection_ids = _ingest_batch(app_client, n=5)
    list_body = app_client.get("/api/detections").json()
    assert list_body["total"] == 5

    # Bulk-action: open a new case from the first 3 detections.
    bulk = app_client.post(
        "/api/inbox/bulk_action",
        json={
            "action": "open_case",
            "detection_ids": detection_ids[:3],
            "payload": {"title": "E2E case"},
        },
    ).json()
    assert bulk["succeeded"] == 3
    case_id = bulk["case_id"]

    # Refetch and confirm 3 attached.
    case = app_client.get(f"/api/cases/{case_id}").json()
    assert case["detection_count"] == 3
    assert case["status"] == "open"

    # Transition open → triage → contained.
    case = app_client.patch(
        f"/api/cases/{case_id}",
        json={"expected_version": case["version"], "status": "triage"},
    ).json()
    assert case["status"] == "triage"
    case = app_client.patch(
        f"/api/cases/{case_id}",
        json={"expected_version": case["version"], "status": "contained"},
    ).json()
    assert case["status"] == "contained"

    # Add a comment.
    comment = app_client.post(
        f"/api/cases/{case_id}/comments", json={"body_md": "Looks like rev 9af2."}
    ).json()
    assert comment["body_md"].startswith("Looks like")

    # Inspect lifecycle events.
    events = app_client.get(f"/api/cases/{case_id}/events").json()["items"]
    kinds = [e["kind"] for e in events]
    assert "created" in kinds
    assert kinds.count("state_changed") == 2
    assert "commented" in kinds

    # CSV export with no filter ⇒ 5 rows + header.
    csv = app_client.get("/api/inbox/export.csv").text
    rows = [l for l in csv.splitlines() if l]
    assert len(rows) == 1 + 5

    # Detection detail surfaces the linked case.
    detail = app_client.get(f"/api/detections/{detection_ids[0]}").json()
    assert detail["case"] is not None
    assert detail["case"]["id"] == case_id


def test_inbox_summary_after_open_case(app_client: TestClient) -> None:
    ids = _ingest_batch(app_client, n=4)
    app_client.post(
        "/api/inbox/bulk_action",
        json={
            "action": "open_case",
            "detection_ids": ids[:2],
            "payload": {"title": "Linked"},
        },
    )
    summary = app_client.get("/api/inbox/summary").json()
    assert summary["case_status_counts"]["open"] == 2
    assert summary["case_status_counts"]["none"] == 2


def test_attach_already_attached_returns_partial_failure(app_client: TestClient) -> None:
    ids = _ingest_batch(app_client, n=3)
    case_a = app_client.post("/api/cases", json={"title": "A"}).json()
    case_b = app_client.post("/api/cases", json={"title": "B"}).json()

    # Attach all 3 to case A.
    first = app_client.post(
        f"/api/cases/{case_a['id']}/attach", json={"detection_ids": ids}
    ).json()
    assert first["succeeded"] == 3

    # Now try to attach the same 3 to case B — should all fail per-item.
    second = app_client.post(
        f"/api/cases/{case_b['id']}/attach", json={"detection_ids": ids}
    ).json()
    assert second["failed"] == 3
    assert all(not r["ok"] for r in second["results"])


def test_filter_by_case_status_open_lists_only_attached(app_client: TestClient) -> None:
    ids = _ingest_batch(app_client, n=4)
    app_client.post(
        "/api/inbox/bulk_action",
        json={
            "action": "open_case",
            "detection_ids": ids[:2],
            "payload": {"title": "Linked"},
        },
    )
    body = app_client.get(
        "/api/detections", params={"case_status": "open"}
    ).json()
    assert body["total"] == 2
    body = app_client.get(
        "/api/detections", params={"case_status": "none"}
    ).json()
    assert body["total"] == 2


def test_saved_view_persists_across_requests(app_client: TestClient) -> None:
    app_client.post(
        "/api/views",
        json={
            "name": "Critical only",
            "filter_json": {"severity": ["escalate"]},
            "pinned": True,
        },
    )
    body = app_client.get("/api/views").json()
    assert body["total"] == 1
    assert body["items"][0]["pinned"] is True
    assert body["items"][0]["filter_json"] == {"severity": ["escalate"]}
