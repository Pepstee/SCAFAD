"""Unit tests for the Phase-2 case-management methods on :class:`DetectionStore`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scafad.gui.backend.store import (
    AlreadyAttached,
    DetectionStore,
    DuplicateAttachment,
    NotFound,
    StoreError,
    VersionConflict,
)


def _store(tmp_path: Path) -> DetectionStore:
    return DetectionStore(tmp_path / "cases.db")


def _seed_detection(store: DetectionStore, idx: int, severity: str = "review") -> str:
    row = store.insert_detection(
        event_id=f"evt-{idx:03d}",
        function_id=f"fn-{idx % 3}",
        anomaly_type="memory_spike",
        severity=severity,
        trust_score=0.5,
        mitre_techniques=[f"T{1000 + idx:04d}"],
        layer_payload={"layer0_record": {"event_id": f"evt-{idx:03d}"}},
    )
    return row.id


def test_create_case_with_no_detections(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="Triage", created_by="analyst@scafad.local")
    assert case.id
    assert case.status == "open"
    assert case.severity_rollup == "observe"
    assert case.detection_count == 0
    assert case.version == 1


def test_create_case_with_initial_detections_rollups_severity(tmp_path: Path) -> None:
    store = _store(tmp_path)
    obs = _seed_detection(store, 1, severity="observe")
    rev = _seed_detection(store, 2, severity="review")
    esc = _seed_detection(store, 3, severity="escalate")
    case = store.create_case(
        title="Mixed", created_by="analyst@scafad.local",
        detection_ids=[obs, rev, esc],
    )
    assert case.severity_rollup == "escalate"
    assert case.detection_count == 3


def test_get_case_returns_none_for_unknown(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.get_case("does-not-exist") is None


def test_list_cases_filters_by_status(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_case(title="A", created_by="u")
    store.create_case(title="B", created_by="u")
    rows, total = store.list_cases(status="open")
    assert total == 2
    rows, total = store.list_cases(status="closed")
    assert total == 0


def test_list_cases_filters_by_assignee(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_case(title="A", created_by="u", assignee_id="alice")
    store.create_case(title="B", created_by="u", assignee_id="bob")
    store.create_case(title="C", created_by="u")
    rows, total = store.list_cases(assignee_id="alice")
    assert total == 1
    rows, total = store.list_cases(assignee_id="")  # explicit unassigned
    assert total == 1


def test_update_case_transitions_state(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    updated = store.update_case(
        case.id, expected_version=case.version, status="triage", actor_id="u"
    )
    assert updated.status == "triage"
    assert updated.version == case.version + 1


def test_update_case_version_conflict_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    with pytest.raises(VersionConflict):
        store.update_case(
            case.id, expected_version=case.version + 99, status="triage", actor_id="u"
        )


def test_update_case_close_sets_closed_at(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    closed = store.update_case(
        case.id, expected_version=case.version, status="closed", actor_id="u"
    )
    assert closed.status == "closed"
    assert closed.closed_at is not None


def test_reopen_clears_closed_at_and_emits_reopened_event(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    case = store.update_case(
        case.id, expected_version=case.version, status="closed", actor_id="u"
    )
    reopened = store.update_case(
        case.id, expected_version=case.version, status="open", actor_id="u"
    )
    assert reopened.status == "open"
    assert reopened.closed_at is None
    events = store.list_case_events(case.id)
    kinds = [e.kind for e in events]
    assert "reopened" in kinds


def test_update_case_assignee_change_emits_assigned_event(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    store.update_case(
        case.id, expected_version=case.version, assignee_id="alice", actor_id="u"
    )
    events = store.list_case_events(case.id)
    assert any(e.kind == "assigned" for e in events)


def test_attach_detection_to_case(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    did = _seed_detection(store, 1, severity="escalate")
    store.attach_detection(case.id, did, actor_id="u")
    refreshed = store.get_case(case.id)
    assert refreshed is not None
    assert refreshed.detection_count == 1
    assert refreshed.severity_rollup == "escalate"


def test_attach_detection_duplicates_raise(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    did = _seed_detection(store, 1)
    store.attach_detection(case.id, did, actor_id="u")
    with pytest.raises(DuplicateAttachment):
        store.attach_detection(case.id, did, actor_id="u")


def test_attach_to_second_case_raises_already_attached(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case1 = store.create_case(title="One", created_by="u")
    case2 = store.create_case(title="Two", created_by="u")
    did = _seed_detection(store, 1)
    store.attach_detection(case1.id, did, actor_id="u")
    with pytest.raises(AlreadyAttached):
        store.attach_detection(case2.id, did, actor_id="u")


def test_detach_detection(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    did = _seed_detection(store, 1, severity="escalate")
    store.attach_detection(case.id, did, actor_id="u")
    store.detach_detection(case.id, did, actor_id="u")
    refreshed = store.get_case(case.id)
    assert refreshed is not None
    assert refreshed.detection_count == 0
    assert refreshed.severity_rollup == "observe"


def test_detach_unknown_raises_not_found(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    did = _seed_detection(store, 1)
    with pytest.raises(NotFound):
        store.detach_detection(case.id, did, actor_id="u")


def test_case_for_detection(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    did = _seed_detection(store, 1)
    assert store.case_for_detection(did) is None
    store.attach_detection(case.id, did, actor_id="u")
    found = store.case_for_detection(did)
    assert found is not None
    assert found.id == case.id


def test_delete_case_cascades(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    did = _seed_detection(store, 1)
    store.attach_detection(case.id, did, actor_id="u")
    store.add_comment(case.id, "u", "hello")
    store.delete_case(case.id, actor_id="u")
    assert store.get_case(case.id) is None
    assert store.case_for_detection(did) is None


def test_delete_unknown_case_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(NotFound):
        store.delete_case("nope", actor_id="u")


def test_create_case_rejects_duplicate_initial_attachment(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case1 = store.create_case(title="One", created_by="u")
    did = _seed_detection(store, 1)
    store.attach_detection(case1.id, did, actor_id="u")
    with pytest.raises(AlreadyAttached):
        store.create_case(
            title="Two", created_by="u", detection_ids=[did]
        )


def test_pragma_integrity_check_after_full_lifecycle(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    did = _seed_detection(store, 1)
    store.attach_detection(case.id, did, actor_id="u")
    store.update_case(case.id, expected_version=case.version, status="closed", actor_id="u")
    with store._connect() as conn:  # noqa: SLF001
        result = conn.execute("PRAGMA integrity_check").fetchone()
    assert result[0] == "ok"
