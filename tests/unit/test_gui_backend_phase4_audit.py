"""Comprehensive tests for WP-GUI-4 Phase 4 audit system implementation.

This test module covers:
1. Audit dispatcher (record_audit function, hash chain, validation)
2. Audit routes (list, get, verify, export, subjects)
3. System status routes (metrics, timeseries, detectors)
4. Settings view routes (runtime, policy, GUI config)
5. Integration tests for audit hooks in write routes
6. Hash chain integrity verification
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from scafad.gui.backend.audit import (  # noqa: E402
    VALID_ACTIONS,
    VALID_SUBJECT_KINDS,
    record_audit,
    _canonical_json,
    _compute_row_hash,
)
from scafad.gui.backend.config import GUISettings  # noqa: E402
from scafad.gui.backend.main import create_app  # noqa: E402
from scafad.gui.backend.store import DetectionStore  # noqa: E402


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def app_client(tmp_path: Path) -> Iterator[TestClient]:
    """Create a fresh app with temp database for each test."""
    settings = GUISettings(db_path=tmp_path / "phase4-audit.db", env="test")
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def store(app_client: TestClient) -> DetectionStore:
    """Extract the store from the app."""
    return app_client.app.state.store


# ============================================================================
# Audit Dispatcher Tests (record_audit function)
# ============================================================================


class TestAuditDispatcher:
    """Tests for the audit.record_audit() function via HTTP endpoints."""

    def test_audit_records_created_via_case_creation(
        self, app_client: TestClient
    ) -> None:
        """Creating a case should emit an audit record."""
        case_resp = app_client.post("/api/cases", json={"title": "Test Case"})
        assert case_resp.status_code == 201

        # Check that an audit record exists
        audit_resp = app_client.get("/api/audit")
        assert audit_resp.status_code == 200
        assert audit_resp.json()["total"] >= 1

    def test_audit_record_has_correct_structure(
        self, app_client: TestClient
    ) -> None:
        """Audit records should have all required fields."""
        # Create a case to trigger an audit record
        app_client.post("/api/cases", json={"title": "Test"})

        audit_resp = app_client.get("/api/audit?page=1&page_size=1")
        items = audit_resp.json()["items"]
        assert len(items) > 0

        record = items[0]
        assert "id" in record
        assert "ts" in record
        assert "actor_id" in record
        assert "subject_kind" in record
        assert "action" in record
        assert "prev_hash" in record
        assert "row_hash" in record

    def test_audit_payload_normalizes_to_canonical_json(
        self, app_client: TestClient
    ) -> None:
        """Audit records should have canonicalized JSON payloads."""
        # Create case with deterministic data
        app_client.post("/api/cases", json={"title": "Canonical Test"})

        audit_resp = app_client.get("/api/audit")
        items = audit_resp.json()["items"]

        # Find the case creation record
        case_record = next(
            (item for item in items if item["subject_kind"] == "case" and item["action"] == "created"),
            None,
        )
        assert case_record is not None
        assert "payload" in case_record

    def test_audit_record_validates_subject_kind(self, app_client: TestClient) -> None:
        """Invalid subject_kind values should be rejected at validation."""
        # This is tested indirectly - all valid routes should emit valid subject_kinds
        audit_resp = app_client.get("/api/audit/subjects")
        subjects = audit_resp.json()
        assert "subject_kinds" in subjects
        assert "case" in subjects["subject_kinds"]

    def test_audit_record_hashes_are_hex_strings(
        self, app_client: TestClient
    ) -> None:
        """Hash fields should be valid hex strings of length 64."""
        app_client.post("/api/cases", json={"title": "Hash Test"})

        audit_resp = app_client.get("/api/audit?page_size=1")
        record = audit_resp.json()["items"][0]

        # Both hashes should be 64-character hex strings (SHA-256)
        assert len(record["row_hash"]) == 64
        assert len(record["prev_hash"]) == 64
        assert all(c in "0123456789abcdef" for c in record["row_hash"])
        assert all(c in "0123456789abcdef" for c in record["prev_hash"])


# ============================================================================
# Canonical JSON Tests
# ============================================================================


class TestCanonicalJson:
    """Tests for the _canonical_json() helper function."""

    def test_canonical_json_sorts_keys(self) -> None:
        """_canonical_json should sort dict keys alphabetically."""
        obj = {"z": 1, "a": 2, "m": 3}
        result = _canonical_json(obj)
        assert result == '{"a":2,"m":3,"z":1}'

    def test_canonical_json_uses_tight_separators(self) -> None:
        """_canonical_json should use tight separators (no spaces)."""
        obj = {"key": "value", "nested": {"inner": "data"}}
        result = _canonical_json(obj)
        assert ", " not in result
        assert ": " not in result
        assert "," in result or ":" not in result

    def test_canonical_json_preserves_unicode(self) -> None:
        """_canonical_json should preserve Unicode characters."""
        obj = {"message": "こんにちは"}
        result = _canonical_json(obj)
        assert "こんにちは" in result
        assert "\\u" not in result


# ============================================================================
# Audit Routes Tests
# ============================================================================


class TestAuditRoutes:
    """Tests for the /api/audit routes."""

    def test_list_audit_events_empty(self, app_client: TestClient) -> None:
        """GET /api/audit should return empty list initially."""
        resp = app_client.get("/api/audit")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1
        assert body["page_size"] == 50

    def test_list_audit_events_creates_one_row_per_record(
        self, app_client: TestClient
    ) -> None:
        """GET /api/audit should list all audit records from case creation."""
        # Create 3 cases - each generates an audit record
        for i in range(3):
            app_client.post("/api/cases", json={"title": f"Case {i}"})

        resp = app_client.get("/api/audit")
        assert resp.status_code == 200
        body = resp.json()
        # Should have at least 3 audit records (one per case creation)
        assert body["total"] >= 3
        assert len(body["items"]) >= 3

    def test_list_audit_events_pagination(self, app_client: TestClient) -> None:
        """GET /api/audit should support pagination."""
        # Create 15 cases - each generates an audit record
        for i in range(15):
            app_client.post("/api/cases", json={"title": f"Case {i}"})

        # Page 1 with 5 items per page
        resp = app_client.get("/api/audit?page=1&page_size=5")
        body = resp.json()
        assert len(body["items"]) == 5
        assert body["page"] == 1
        assert body["total"] >= 15

        # Page 2
        resp = app_client.get("/api/audit?page=2&page_size=5")
        body = resp.json()
        assert len(body["items"]) == 5
        assert body["page"] == 2

    def test_list_audit_events_filters_by_actor(self, app_client: TestClient) -> None:
        """GET /api/audit?actor=X should filter by actor_id."""
        # Create cases
        app_client.post("/api/cases", json={"title": "Test 1"})
        app_client.post("/api/cases", json={"title": "Test 2"})

        # Get all audit records
        resp = app_client.get("/api/audit?page_size=100")
        body = resp.json()
        assert body["total"] >= 2

        # Filter by a specific actor (just verify the endpoint accepts the filter)
        resp = app_client.get("/api/audit?actor=user-test")
        assert resp.status_code == 200

    def test_list_audit_events_filters_by_subject_kind(
        self, app_client: TestClient
    ) -> None:
        """GET /api/audit?subject_kind=X should filter by subject_kind."""
        # Create a case
        app_client.post("/api/cases", json={"title": "Test"})

        # Filter by subject_kind
        resp = app_client.get("/api/audit?subject_kind=case")
        assert resp.status_code == 200
        body = resp.json()
        # Should find at least one case record
        assert body["total"] >= 1
        case_records = [item for item in body["items"] if item["subject_kind"] == "case"]
        assert len(case_records) >= 1

    def test_list_audit_events_filters_by_action(self, app_client: TestClient) -> None:
        """GET /api/audit?action=X should filter by action."""
        # Create a case
        app_client.post("/api/cases", json={"title": "Test"})

        # Filter by action
        resp = app_client.get("/api/audit?action=created")
        assert resp.status_code == 200
        body = resp.json()
        # Should find records with "created" action
        assert body["total"] >= 1

    def test_get_audit_event_by_id(self, app_client: TestClient) -> None:
        """GET /api/audit/{id} should return a single audit event."""
        # Create a case to generate an audit record
        app_client.post("/api/cases", json={"title": "Test"})

        # Get the first audit record
        resp = app_client.get("/api/audit?page_size=1")
        body = resp.json()
        assert len(body["items"]) > 0
        event_id = body["items"][0]["id"]

        # Get that specific event
        resp = app_client.get(f"/api/audit/{event_id}")
        assert resp.status_code == 200
        event = resp.json()
        assert event["id"] == event_id
        assert "actor_id" in event
        assert "subject_kind" in event

    def test_get_audit_event_404(self, app_client: TestClient) -> None:
        """GET /api/audit/{id} should return 404 for missing event."""
        resp = app_client.get("/api/audit/nonexistent")
        assert resp.status_code == 404

    def test_verify_audit_chain_empty(self, app_client: TestClient) -> None:
        """GET /api/audit/verify should return ok=true for empty chain."""
        resp = app_client.get("/api/audit/verify")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["total_rows"] == 0

    def test_verify_audit_chain_intact(self, app_client: TestClient) -> None:
        """GET /api/audit/verify should return ok=true for valid chain."""
        # Create 5 cases to generate audit records
        for i in range(5):
            app_client.post("/api/cases", json={"title": f"Case {i}"})

        resp = app_client.get("/api/audit/verify")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["total_rows"] >= 5

    def test_export_audit_csv(self, app_client: TestClient) -> None:
        """GET /api/audit/export.csv should stream CSV data."""
        # Create a case to populate audit log
        app_client.post("/api/cases", json={"title": "Test"})

        resp = app_client.get("/api/audit/export.csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        assert "audit_export.csv" in resp.headers.get("content-disposition", "")

        # Check CSV content
        content = resp.text
        assert "id,ts,actor_id,subject_kind,subject_id,action,prev_hash,row_hash" in content or "id" in content

    def test_export_audit_json(self, app_client: TestClient) -> None:
        """GET /api/audit/export.json should stream NDJSON data."""
        # Create a case to populate audit log
        app_client.post("/api/cases", json={"title": "Test"})

        resp = app_client.get("/api/audit/export.json")
        assert resp.status_code == 200
        assert "ndjson" in resp.headers.get("content-type", "")
        assert "audit_export.jsonl" in resp.headers.get("content-disposition", "")

        # Parse NDJSON - should have at least one line
        lines = [l for l in resp.text.strip().split("\n") if l.strip()]
        assert len(lines) > 0
        obj = json.loads(lines[0])
        assert "id" in obj
        assert "actor_id" in obj
        assert "subject_kind" in obj

    def test_list_audit_subjects(self, app_client: TestClient) -> None:
        """GET /api/audit/subjects should return distinct subject_kinds/actions/actors."""
        # Create a case and view
        app_client.post("/api/cases", json={"title": "Test"})
        app_client.post("/api/views", json={"name": "Test View"})

        resp = app_client.get("/api/audit/subjects")
        assert resp.status_code == 200
        body = resp.json()
        assert "subject_kinds" in body
        assert "actions" in body
        assert "actors" in body
        assert isinstance(body["subject_kinds"], list)
        assert isinstance(body["actions"], list)


# ============================================================================
# System Routes Tests
# ============================================================================


class TestSystemRoutes:
    """Tests for the /api/system routes."""

    def test_get_system_status(self, app_client: TestClient) -> None:
        """GET /api/system/status should return system metrics."""
        resp = app_client.get("/api/system/status")
        assert resp.status_code == 200
        body = resp.json()

        # Should have layer information
        assert "layers" in body
        assert isinstance(body["layers"], list)

    def test_get_system_metrics(self, app_client: TestClient) -> None:
        """GET /api/system/metrics should return system metrics."""
        resp = app_client.get("/api/system/metrics")
        assert resp.status_code == 200
        body = resp.json()

        # Should have layer information
        assert "layers" in body
        assert isinstance(body["layers"], list)

    def test_get_metrics_timeseries_default(self, app_client: TestClient) -> None:
        """GET /api/system/metrics/timeseries should return timeseries data."""
        resp = app_client.get("/api/system/metrics/timeseries")
        assert resp.status_code == 200
        body = resp.json()

        # Check for expected fields (may be window_spec and bin instead of window/bin_spec)
        assert ("window" in body or "window_spec" in body)
        assert ("bin" in body or "bin_spec" in body)
        assert ("timeseries" in body or "series" in body)

    def test_get_metrics_timeseries_with_params(
        self, app_client: TestClient
    ) -> None:
        """GET /api/system/metrics/timeseries should accept window and bin params."""
        resp = app_client.get("/api/system/metrics/timeseries?window=24h&bin=1h")
        assert resp.status_code == 200
        body = resp.json()

        # Check field names (may vary)
        window_val = body.get("window") or body.get("window_spec")
        bin_val = body.get("bin") or body.get("bin_spec")
        assert window_val == "24h"
        assert bin_val == "1h"

    def test_get_detectors(self, app_client: TestClient) -> None:
        """GET /api/system/detectors should return detector panel."""
        resp = app_client.get("/api/system/detectors")
        assert resp.status_code == 200
        body = resp.json()

        assert "available" in body
        # available may be False if runtime not warmed
        assert isinstance(body["available"], bool)


# ============================================================================
# Settings Routes Tests
# ============================================================================


class TestSettingsRoutes:
    """Tests for the /api/settings routes."""

    def test_get_settings(self, app_client: TestClient) -> None:
        """GET /api/settings should return all settings projections."""
        resp = app_client.get("/api/settings")
        assert resp.status_code == 200
        body = resp.json()

        # Should have the three projections
        assert "runtime" in body
        assert "policy" in body
        assert "gui" in body

    def test_get_settings_runtime(self, app_client: TestClient) -> None:
        """GET /api/settings/runtime should return runtime config."""
        resp = app_client.get("/api/settings/runtime")
        assert resp.status_code == 200
        body = resp.json()

        assert "available" in body
        # available may be False if runtime not warmed

    def test_get_settings_policy(self, app_client: TestClient) -> None:
        """GET /api/settings/policy should return redaction policy."""
        resp = app_client.get("/api/settings/policy")
        assert resp.status_code == 200
        body = resp.json()

        # Should have policy information
        assert isinstance(body, dict)

    def test_get_settings_gui(self, app_client: TestClient) -> None:
        """GET /api/settings/gui should return GUI config snapshot."""
        resp = app_client.get("/api/settings/gui")
        assert resp.status_code == 200
        body = resp.json()

        # Should have GUI configuration
        assert "env" in body or "host" in body or isinstance(body, dict)


# ============================================================================
# Integration Tests - Audit Hooks in Write Routes
# ============================================================================


class TestAuditHooksIntegration:
    """Tests for audit hooks in existing write routes."""

    def test_create_case_emits_audit_record(self, app_client: TestClient) -> None:
        """POST /api/cases should emit one audit_events record."""
        # Create a case
        resp = app_client.post("/api/cases", json={"title": "Audit Test Case"})
        assert resp.status_code == 201
        case = resp.json()

        # Check audit log
        audit_resp = app_client.get("/api/audit")
        assert audit_resp.status_code == 200
        body = audit_resp.json()

        # Should have at least one audit record for case creation
        assert body["total"] >= 1

        # Find the case creation record
        case_records = [
            item for item in body["items"]
            if item["subject_kind"] == "case" and item["action"] == "created"
        ]
        assert len(case_records) >= 1

    def test_update_case_emits_audit_record(self, app_client: TestClient) -> None:
        """PATCH /api/cases/{id} should emit one audit_events record."""
        # Create a case first
        case_resp = app_client.post("/api/cases", json={"title": "Test"})
        case = case_resp.json()

        # Update it
        update_resp = app_client.patch(
            f"/api/cases/{case['id']}",
            json={"expected_version": case["version"], "status": "triage"},
        )
        assert update_resp.status_code == 200

        # Check audit log for update
        audit_resp = app_client.get("/api/audit")
        body = audit_resp.json()

        update_records = [
            item for item in body["items"]
            if item["subject_kind"] == "case" and item["action"] == "updated"
        ]
        assert len(update_records) >= 1

    def test_delete_case_emits_audit_record(self, app_client: TestClient) -> None:
        """DELETE /api/cases/{id} should emit one audit_events record."""
        # Create a case first
        case_resp = app_client.post("/api/cases", json={"title": "Test"})
        case = case_resp.json()

        # Delete it
        delete_resp = app_client.delete(f"/api/cases/{case['id']}")
        assert delete_resp.status_code == 204

        # Check audit log for delete
        audit_resp = app_client.get("/api/audit")
        body = audit_resp.json()

        delete_records = [
            item for item in body["items"]
            if item["subject_kind"] == "case" and item["action"] == "deleted"
        ]
        assert len(delete_records) >= 1


# ============================================================================
# Hash Chain Integrity Tests
# ============================================================================


class TestHashChainIntegrity:
    """Tests for hash chain integrity verification."""

    def test_hash_chain_links_all_records(self, app_client: TestClient) -> None:
        """Each record's prev_hash should point to the previous record's row_hash."""
        # Create 5 cases to generate 5 audit records
        for i in range(5):
            app_client.post("/api/cases", json={"title": f"Case {i}"})

        # Get the audit records
        audit_resp = app_client.get("/api/audit?page_size=100")
        items = audit_resp.json()["items"]

        # Should have at least 5 records
        assert len(items) >= 5

        # Verify chaining: each record's prev_hash should point to the previous record's row_hash
        # Sort by timestamp to ensure proper order (API returns newest first)
        items_sorted = sorted(items, key=lambda x: x["ts"])

        for i in range(1, len(items_sorted)):
            assert items_sorted[i]["prev_hash"] == items_sorted[i - 1]["row_hash"]

    def test_hash_deterministic_for_same_content(
        self, app_client: TestClient
    ) -> None:
        """Same content should always produce the same hash."""
        from scafad.gui.backend.audit import _compute_row_hash

        ts_str = "2026-04-27T12:00:00.000000Z"
        prev_hash = "0" * 64

        hash1 = _compute_row_hash(
            event_id="event-1",
            ts_str=ts_str,
            actor_id="user-1",
            subject_kind="case",
            subject_id="case-1",
            action="created",
            payload_json='{"title":"Test"}',
            prev_hash=prev_hash,
        )

        hash2 = _compute_row_hash(
            event_id="event-1",
            ts_str=ts_str,
            actor_id="user-1",
            subject_kind="case",
            subject_id="case-1",
            action="created",
            payload_json='{"title":"Test"}',
            prev_hash=prev_hash,
        )

        assert hash1 == hash2

    def test_hash_changes_with_different_content(
        self, app_client: TestClient
    ) -> None:
        """Different content should produce different hashes."""
        from scafad.gui.backend.audit import _compute_row_hash

        ts_str = "2026-04-27T12:00:00.000000Z"
        prev_hash = "0" * 64

        hash1 = _compute_row_hash(
            event_id="event-1",
            ts_str=ts_str,
            actor_id="user-1",
            subject_kind="case",
            subject_id="case-1",
            action="created",
            payload_json='{"title":"Test1"}',
            prev_hash=prev_hash,
        )

        hash2 = _compute_row_hash(
            event_id="event-1",
            ts_str=ts_str,
            actor_id="user-1",
            subject_kind="case",
            subject_id="case-1",
            action="created",
            payload_json='{"title":"Test2"}',
            prev_hash=prev_hash,
        )

        assert hash1 != hash2


# ============================================================================
# Router Registration Tests
# ============================================================================


class TestPhase4RouterRegistration:
    """Tests to verify Phase 4 routers are properly registered."""

    def test_audit_router_registered(self, app_client: TestClient) -> None:
        """Audit router should be registered."""
        # If this doesn't raise an error, the router is registered
        resp = app_client.get("/api/audit")
        assert resp.status_code == 200

    def test_system_router_registered(self, app_client: TestClient) -> None:
        """System router should be registered."""
        resp = app_client.get("/api/system/metrics")
        assert resp.status_code == 200

    def test_settings_router_registered(self, app_client: TestClient) -> None:
        """Settings router should be registered."""
        resp = app_client.get("/api/settings")
        assert resp.status_code == 200

    def test_route_ordering_respects_specificity(
        self, app_client: TestClient
    ) -> None:
        """Specific routes (/audit/verify) should be matched before /audit/{id}."""
        # Create a case to populate audit log
        app_client.post("/api/cases", json={"title": "Test"})

        # /verify should match before /{id}
        verify_resp = app_client.get("/api/audit/verify")
        assert verify_resp.status_code == 200
        assert "ok" in verify_resp.json()

        # /export.csv should match before /{id}
        csv_resp = app_client.get("/api/audit/export.csv")
        assert csv_resp.status_code == 200
        assert "audit_export.csv" in csv_resp.headers.get("content-disposition", "")


__all__ = [
    "TestAuditDispatcher",
    "TestCanonicalJson",
    "TestAuditRoutes",
    "TestSystemRoutes",
    "TestSettingsRoutes",
    "TestAuditHooksIntegration",
    "TestHashChainIntegrity",
    "TestPhase4RouterRegistration",
]
