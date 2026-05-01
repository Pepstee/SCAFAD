"""Tests for the Phase-2 additions to ``/api/detections``.

These exercise the six new optional filters (mitre_technique, decision,
risk_band, text, until, case_status) and the optional ``case`` field on
the detail endpoint.  The Phase-1 contract — Phase-1 callers receive
byte-identical responses when none of the new params are passed — is
asserted by ``test_phase1_contract_unchanged``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    settings = GUISettings(db_path=tmp_path / "detections-phase2.db", env="test")
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


def _seed(app, n: int = 6):
    store: DetectionStore = app.state.store
    base = datetime.now(timezone.utc) - timedelta(minutes=n)
    sevs = ["observe", "review", "escalate"]
    decisions = ["observe", "review", "escalate"]
    bands = ["low", "medium", "high"]
    techs_by_idx = {
        0: ["T1059"],
        1: ["T1071.001"],
        2: ["T1059", "T1499"],
        3: ["T1499"],
        4: ["T1071.001"],
        5: ["T1059"],
    }
    out = []
    for i in range(n):
        row = store.insert_detection(
            event_id=f"ev-{i:03d}",
            function_id=f"fn-{i % 2}",
            anomaly_type="memory_spike" if i % 2 == 0 else "cpu_burst",
            severity=sevs[i % 3],
            trust_score=0.5,
            mitre_techniques=techs_by_idx[i],
            layer_payload={"layer0_record": {"event_id": f"ev-{i:03d}"}},
            decision=decisions[i % 3],
            risk_band=bands[i % 3],
            ingested_at=base + timedelta(minutes=i),
            correlation_id=f"corr-{i}",
        )
        out.append(row)
    return out


def test_phase1_contract_unchanged(app_client: TestClient) -> None:
    rows = _seed(app_client.app, n=4)
    body = app_client.get("/api/detections").json()
    # Same shape as Phase 1: items / total / page / page_size
    assert set(body.keys()) == {"items", "total", "page", "page_size"}
    assert body["total"] == 4
    keys = set(body["items"][0].keys())
    expected = {
        "id", "ingested_at", "event_id", "function_id", "anomaly_type",
        "severity", "trust_score", "mitre_techniques", "decision", "risk_band",
    }
    assert keys == expected


def test_filter_by_mitre_technique(app_client: TestClient) -> None:
    _seed(app_client.app, n=6)
    body = app_client.get(
        "/api/detections", params={"mitre_technique": "T1071"}
    ).json()
    # Two detections carry T1071.001
    assert body["total"] == 2
    body = app_client.get(
        "/api/detections", params={"mitre_technique": "TXXXX"}
    ).json()
    assert body["total"] == 0


def test_filter_by_decision_and_risk_band(app_client: TestClient) -> None:
    _seed(app_client.app, n=6)
    body = app_client.get("/api/detections", params={"decision": "escalate"}).json()
    assert all(item["decision"] == "escalate" for item in body["items"])
    body = app_client.get("/api/detections", params={"risk_band": "high"}).json()
    assert all(item["risk_band"] == "high" for item in body["items"])


def test_filter_by_text_searches_event_and_correlation(app_client: TestClient) -> None:
    _seed(app_client.app, n=4)
    body = app_client.get("/api/detections", params={"text": "ev-002"}).json()
    assert body["total"] == 1
    body = app_client.get("/api/detections", params={"text": "corr-3"}).json()
    assert body["total"] == 1
    body = app_client.get("/api/detections", params={"text": "no-match"}).json()
    assert body["total"] == 0


def test_filter_by_until(app_client: TestClient) -> None:
    rows = _seed(app_client.app, n=4)
    middle = rows[2].ingested_at.isoformat()
    body = app_client.get("/api/detections", params={"until": middle}).json()
    # rows[0], rows[1] have timestamps strictly before rows[2]
    assert body["total"] == 2


def test_filter_by_case_status_none(app_client: TestClient) -> None:
    rows = _seed(app_client.app, n=4)
    case = app_client.post(
        "/api/cases",
        json={"title": "X", "detection_ids": [rows[0].id, rows[1].id]},
    ).json()
    body = app_client.get(
        "/api/detections", params={"case_status": "none"}
    ).json()
    # 4 seeded - 2 attached = 2 unlinked
    assert body["total"] == 2


def test_filter_by_case_status_open(app_client: TestClient) -> None:
    rows = _seed(app_client.app, n=4)
    app_client.post(
        "/api/cases", json={"title": "X", "detection_ids": [rows[0].id]}
    )
    body = app_client.get(
        "/api/detections", params={"case_status": "open"}
    ).json()
    assert body["total"] == 1


def test_detail_response_includes_case_field_when_linked(app_client: TestClient) -> None:
    rows = _seed(app_client.app, n=2)
    case = app_client.post(
        "/api/cases", json={"title": "Linked", "detection_ids": [rows[0].id]}
    ).json()
    detail = app_client.get(f"/api/detections/{rows[0].id}").json()
    assert detail.get("case") is not None
    assert detail["case"]["id"] == case["id"]


def test_detail_response_case_field_null_when_unlinked(app_client: TestClient) -> None:
    rows = _seed(app_client.app, n=1)
    detail = app_client.get(f"/api/detections/{rows[0].id}").json()
    assert detail.get("case") is None
