"""Unit tests for :class:`scafad.gui.backend.store.DetectionStore`.

The store is exercised directly (no FastAPI involvement) so failures pinpoint
the persistence layer rather than the surrounding HTTP plumbing.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("fastapi")  # GUI deps gate (architecture R-G5)

from scafad.gui.backend.store import (  # noqa: E402
    DetectionRow,
    DetectionStore,
    detection_to_detail_dict,
    detection_to_summary_dict,
)


@pytest.fixture
def store(tmp_path: Path) -> DetectionStore:
    return DetectionStore(tmp_path / "detections.db")


def _insert(store: DetectionStore, **overrides) -> DetectionRow:
    defaults = {
        "event_id": "evt-x",
        "function_id": "fn-x",
        "anomaly_type": "memory_spike",
        "severity": "review",
        "trust_score": 0.42,
        "mitre_techniques": ["T1059.009"],
        "layer_payload": {"layer0_record": {"event_id": "evt-x"}},
        "decision": "review",
        "risk_band": "medium",
        "duration_ms": 12.3,
        "correlation_id": "trace-1",
    }
    defaults.update(overrides)
    return store.insert_detection(**defaults)


def test_store_creates_schema(store: DetectionStore) -> None:
    assert store.db_path.exists()
    assert store.total_count() == 0


def test_store_inserts_and_round_trips(store: DetectionStore) -> None:
    row = _insert(store)
    fetched = store.get_detection(row.id)
    assert fetched is not None
    assert fetched.id == row.id
    assert fetched.severity == "review"
    assert fetched.mitre_techniques == ["T1059.009"]
    assert fetched.layer_payload["layer0_record"]["event_id"] == "evt-x"


def test_store_get_returns_none_for_unknown(store: DetectionStore) -> None:
    assert store.get_detection("does-not-exist") is None


def test_store_lists_in_descending_order(store: DetectionStore) -> None:
    older = _insert(store, event_id="evt-old", ingested_at=datetime(2026, 4, 25, tzinfo=timezone.utc))
    newer = _insert(store, event_id="evt-new", ingested_at=datetime(2026, 4, 26, tzinfo=timezone.utc))
    rows, total = store.list_detections()
    assert total == 2
    assert [r.id for r in rows] == [newer.id, older.id]


def test_store_filters_by_severity(store: DetectionStore) -> None:
    _insert(store, severity="observe")
    _insert(store, severity="escalate")
    rows, total = store.list_detections(severity="escalate")
    assert total == 1
    assert rows[0].severity == "escalate"


def test_store_filters_by_anomaly_type(store: DetectionStore) -> None:
    _insert(store, anomaly_type="memory_spike")
    _insert(store, anomaly_type="economic_abuse")
    rows, total = store.list_detections(anomaly_type="economic_abuse")
    assert total == 1
    assert rows[0].anomaly_type == "economic_abuse"


def test_store_filters_by_function(store: DetectionStore) -> None:
    _insert(store, function_id="fn-a")
    _insert(store, function_id="fn-b")
    rows, total = store.list_detections(function_id="fn-a")
    assert total == 1
    assert rows[0].function_id == "fn-a"


def test_store_filters_by_since(store: DetectionStore) -> None:
    cutoff = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    _insert(store, event_id="early", ingested_at=cutoff - timedelta(hours=2))
    _insert(store, event_id="late", ingested_at=cutoff + timedelta(hours=1))
    rows, total = store.list_detections(since=cutoff)
    assert total == 1
    assert rows[0].event_id == "late"


def test_store_paginates_results(store: DetectionStore) -> None:
    for i in range(5):
        _insert(store, event_id=f"evt-{i}", ingested_at=datetime(2026, 4, i + 1, tzinfo=timezone.utc))
    rows, total = store.list_detections(limit=2, offset=2)
    assert total == 5
    assert len(rows) == 2


def test_store_aggregates_severity_mix(store: DetectionStore) -> None:
    _insert(store, severity="observe")
    _insert(store, severity="observe")
    _insert(store, severity="review")
    _insert(store, severity="escalate")
    mix = store.severity_mix()
    assert mix == {"observe": 2, "review": 1, "escalate": 1}


def test_store_ingest_rate_last_hour(store: DetectionStore) -> None:
    now = datetime.now(timezone.utc)
    _insert(store, ingested_at=now - timedelta(minutes=10))
    _insert(store, ingested_at=now - timedelta(hours=2))
    assert store.ingest_rate_last_hour() == 1


def test_store_histogram_24h_returns_24_buckets(store: DetectionStore) -> None:
    buckets = store.histogram_24h()
    assert len(buckets) == 24
    for b in buckets:
        assert set(b.keys()) >= {"hour", "observe", "review", "escalate"}


def test_store_truncate_clears_rows(store: DetectionStore) -> None:
    _insert(store)
    _insert(store)
    assert store.total_count() == 2
    store.truncate()
    assert store.total_count() == 0


def test_store_payload_is_json_serialisable(store: DetectionStore) -> None:
    payload = {"layer0_record": {"event_id": "x"}, "multilayer_result": {"layer2": {"signals": []}}}
    row = _insert(store, layer_payload=payload)
    fetched = store.get_detection(row.id)
    assert fetched is not None
    assert json.dumps(fetched.layer_payload)  # round trip


def test_store_summary_dict_strips_payload(store: DetectionStore) -> None:
    row = _insert(store)
    summary = detection_to_summary_dict(row)
    assert "layer_payload" not in summary
    assert summary["mitre_techniques"] == ["T1059.009"]


def test_store_detail_dict_includes_payload(store: DetectionStore) -> None:
    row = _insert(store)
    detail = detection_to_detail_dict(row)
    assert "layer_payload" in detail
    assert detail["layer_payload"] == {"layer0_record": {"event_id": "evt-x"}}


def test_store_db_size_bytes_grows_after_insert(store: DetectionStore) -> None:
    initial = store.db_size_bytes()
    _insert(store)
    assert store.db_size_bytes() >= initial
