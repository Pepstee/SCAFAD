"""Unit tests for the case_events append-only audit log."""

from __future__ import annotations

from pathlib import Path

from scafad.gui.backend.store import DetectionStore


def _store(tmp_path: Path) -> DetectionStore:
    return DetectionStore(tmp_path / "events.db")


def test_create_case_writes_created_event(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    events = store.list_case_events(case.id)
    assert events
    assert events[0].kind == "created"
    assert events[0].actor_id == "u"


def test_state_change_emits_state_changed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    store.update_case(
        case.id, expected_version=case.version, status="triage", actor_id="u"
    )
    events = store.list_case_events(case.id)
    kinds = [e.kind for e in events]
    assert "state_changed" in kinds


def test_attach_emits_attached_event(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    row = store.insert_detection(
        event_id="e",
        function_id="fn",
        anomaly_type="memory_spike",
        severity="review",
        trust_score=0.5,
        mitre_techniques=[],
        layer_payload={},
    )
    store.attach_detection(case.id, row.id, actor_id="u")
    events = store.list_case_events(case.id)
    assert any(e.kind == "detection_attached" for e in events)


def test_detach_emits_detached_event(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    row = store.insert_detection(
        event_id="e", function_id="fn",
        anomaly_type="memory_spike", severity="observe",
        trust_score=0.1, mitre_techniques=[], layer_payload={},
    )
    store.attach_detection(case.id, row.id, actor_id="u")
    store.detach_detection(case.id, row.id, actor_id="u")
    events = store.list_case_events(case.id)
    assert any(e.kind == "detection_detached" for e in events)


def test_assign_change_emits_assigned_event(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    store.update_case(
        case.id, expected_version=case.version, assignee_id="alice", actor_id="u"
    )
    events = store.list_case_events(case.id)
    assert any(e.kind == "assigned" for e in events)


def test_events_listed_in_creation_order(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    store.update_case(
        case.id, expected_version=case.version, status="triage", actor_id="u"
    )
    store.add_comment(case.id, "alice", "hi")
    events = store.list_case_events(case.id)
    kinds = [e.kind for e in events]
    # created first, then state_changed, then commented
    assert kinds[0] == "created"
    assert "state_changed" in kinds
    assert kinds[-1] == "commented"


def test_record_case_event_explicitly(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    rec = store.record_case_event(
        case.id, "dismissed", {"reason": "false positive"}, actor_id="u"
    )
    assert rec.kind == "dismissed"
    events = store.list_case_events(case.id)
    assert any(e.kind == "dismissed" for e in events)
