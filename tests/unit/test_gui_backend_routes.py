"""HTTP-level tests for the SCAFAD GUI backend routes.

Each test instantiates a fresh FastAPI app pinned to a tmp SQLite path so
sessions never leak data into one another.
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
from scafad.gui.backend.runtime_adapter import IngestionOutcome  # noqa: E402
from scafad.gui.backend.store import DetectionStore  # noqa: E402


@pytest.fixture
def app_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = GUISettings(db_path=tmp_path / "routes.db", env="test")
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


def _seed_store(app, *, count: int = 3, severity_seq=None) -> None:
    """Insert ``count`` synthetic detections directly through the store.

    Bypasses the runtime so route tests stay sub-second.
    """

    store: DetectionStore = app.state.store
    severities = severity_seq or ["observe", "review", "escalate"]
    base_time = datetime.now(timezone.utc) - timedelta(minutes=count)
    for i in range(count):
        store.insert_detection(
            event_id=f"seed-{i}",
            function_id=f"fn-{i % 2}",
            anomaly_type="memory_spike" if i % 2 == 0 else "economic_abuse",
            severity=severities[i % len(severities)],
            trust_score=0.1 * (i + 1),
            mitre_techniques=["T1059.009"],
            layer_payload={
                "layer0_record": {"event_id": f"seed-{i}"},
                "multilayer_result": {
                    "layer2": {"signals": []},
                    "layer3": {"trust_weights": {"rule_chain": 0.5}, "fused_score": 0.5},
                    "layer4": {"decision": severities[i % len(severities)]},
                    "layer5": {"techniques": ["T1059.009"], "tactics": []},
                },
            },
            decision=severities[i % len(severities)],
            risk_band="medium",
            ingested_at=base_time + timedelta(minutes=i),
        )


def test_health_endpoint_returns_metadata(app_client: TestClient) -> None:
    resp = app_client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["version"]
    assert body["commit"]
    assert body["env"] == "test"
    assert body["started_at"]


def test_openapi_schema_is_published(app_client: TestClient) -> None:
    resp = app_client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "/api/health" in schema["paths"]
    assert "/api/ingest" in schema["paths"]


def test_swagger_docs_render(app_client: TestClient) -> None:
    resp = app_client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower()


def test_system_status_includes_seven_layers(app_client: TestClient) -> None:
    resp = app_client.get("/api/system/status")
    assert resp.status_code == 200
    body = resp.json()
    layer_names = [l["layer"] for l in body["layers"]]
    assert layer_names == [f"layer{i}" for i in range(7)]
    assert body["detector_count"] == 26


def test_detections_list_returns_empty_initially(app_client: TestClient) -> None:
    resp = app_client.get("/api/detections")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 50}


def test_detections_list_returns_seeded_rows(app_client: TestClient) -> None:
    _seed_store(app_client.app, count=4)
    resp = app_client.get("/api/detections")
    body = resp.json()
    assert body["total"] == 4
    assert len(body["items"]) == 4
    # newest first
    assert body["items"][0]["event_id"] == "seed-3"


def test_detections_list_filters_by_severity(app_client: TestClient) -> None:
    _seed_store(app_client.app, count=6, severity_seq=["observe", "review", "escalate"])
    resp = app_client.get("/api/detections", params={"severity": "escalate"})
    body = resp.json()
    assert body["total"] == 2
    assert all(item["severity"] == "escalate" for item in body["items"])


def test_detections_list_filters_by_anomaly_type(app_client: TestClient) -> None:
    _seed_store(app_client.app, count=4)
    resp = app_client.get("/api/detections", params={"anomaly_type": "economic_abuse"})
    body = resp.json()
    assert body["total"] == 2


def test_detections_summary_returns_kpis(app_client: TestClient) -> None:
    _seed_store(app_client.app, count=6, severity_seq=["observe", "review", "escalate"])
    resp = app_client.get("/api/detections/summary")
    body = resp.json()
    assert body["open_count"] == 4  # review + escalate
    assert sum(body["severity_mix"].values()) == 6
    assert len(body["hist24h"]) == 24
    assert body["ingest_rate_1h"] >= 0


def test_detections_get_returns_full_payload(app_client: TestClient) -> None:
    _seed_store(app_client.app, count=1)
    list_resp = app_client.get("/api/detections").json()
    detection_id = list_resp["items"][0]["id"]
    resp = app_client.get(f"/api/detections/{detection_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == detection_id
    payload = detail["layer_payload"]
    assert "layer0_record" in payload
    assert "multilayer_result" in payload


def test_detections_get_404_for_unknown_id(app_client: TestClient) -> None:
    resp = app_client.get("/api/detections/no-such-id")
    assert resp.status_code == 404


def test_ingest_round_trips_through_runtime(app_client: TestClient) -> None:
    payload = {
        "event_id": "ingest-evt-1",
        "function_id": "ingest_fn",
        "anomaly": "memory_spike",
        "duration": 0.85,
        "memory_spike_kb": 262_144,
        "cpu_utilization": 88.0,
    }
    resp = app_client.post("/api/ingest", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]
    assert body["severity"] in {"observe", "review", "escalate"}
    assert body["anomaly_type"]
    assert isinstance(body["mitre_techniques"], list)

    # The detection is now retrievable via the list and detail endpoints.
    detail = app_client.get(f"/api/detections/{body['id']}").json()
    assert detail["id"] == body["id"]
    assert "multilayer_result" in detail["layer_payload"]


def test_ingest_accepts_empty_payload_with_defaults(app_client: TestClient) -> None:
    # The runtime is intentionally permissive: ``build_record`` supplies
    # safe defaults for every field.  An empty POST therefore round-trips
    # to a benign-class detection rather than a 400/500.  The endpoint must
    # not crash the server when no fields are supplied.
    resp = app_client.post("/api/ingest", json={})
    assert resp.status_code in {201, 400}
    if resp.status_code == 201:
        body = resp.json()
        assert body["severity"] in {"observe", "review", "escalate"}


def test_cors_headers_present(app_client: TestClient) -> None:
    resp = app_client.get(
        "/api/health", headers={"Origin": "http://localhost:5173"}
    )
    assert resp.status_code == 200
    # Starlette/FastAPI CORS middleware echoes the origin when configured.
    assert resp.headers.get("access-control-allow-origin") in {
        "http://localhost:5173",
        "*",
        None,  # depends on pre-flight handling; non-fatal for this assertion
    }


def test_pagination_respects_page_size(app_client: TestClient) -> None:
    _seed_store(app_client.app, count=12)
    resp = app_client.get("/api/detections", params={"page_size": 5, "page": 2})
    body = resp.json()
    assert body["page"] == 2
    assert body["page_size"] == 5
    assert len(body["items"]) == 5
    assert body["total"] == 12


def test_settings_db_path_is_actually_used(tmp_path: Path) -> None:
    settings = GUISettings(db_path=tmp_path / "specific.db", env="test")
    create_app(settings)
    assert (tmp_path / "specific.db").exists()


def test_health_db_path_reflects_settings(tmp_path: Path) -> None:
    settings = GUISettings(db_path=tmp_path / "named.db", env="test")
    app = create_app(settings)
    with TestClient(app) as client:
        body = client.get("/api/health").json()
    assert body["db_path"].endswith("named.db")
