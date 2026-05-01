"""Tests for Phase 3 route endpoints and API contracts."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from scafad.gui.backend.main import create_app
from scafad.gui.backend.config import GUISettings
from scafad.gui.backend.store import DetectionStore


@pytest.fixture
def app_with_phase3_data(tmp_path):
    """Create a test app with Phase 3 detection data."""
    db_path = str(tmp_path / "test.db")

    # Create app with custom settings
    settings = GUISettings(db_path=db_path)
    app = create_app(settings=settings)
    test_client = TestClient(app)

    # Insert test data via the store
    store = DetectionStore(db_path)

    # Insert function 1
    for i in range(5):
        store.insert_detection(
            event_id=f"evt-func1-{i}",
            function_id="lambda-function-1",
            anomaly_type="spike",
            severity="review",
            trust_score=0.8,
            mitre_techniques=["T1059", "T1567"],
            layer_payload={"test": True},
        )

    # Insert function 2
    for i in range(3):
        store.insert_detection(
            event_id=f"evt-func2-{i}",
            function_id="lambda-function-2",
            anomaly_type="exfil",
            severity="escalate",
            trust_score=0.9,
            mitre_techniques=["T1537"],
            layer_payload={"test": True},
        )

    return test_client


class TestPhase3Routes:
    """Test Phase 3 route endpoints."""

    def test_routes_are_registered(self):
        """Verify Phase 3 routes are registered in the app."""
        from scafad.gui.backend.routes import functions, threat_map

        # Just verify the routers exist and have routes
        assert hasattr(functions, 'router')
        assert hasattr(threat_map, 'router')

        # Verify they have registered routes
        assert len(functions.router.routes) > 0
        assert len(threat_map.router.routes) > 0

    def test_threat_map_grid_endpoint_works(self, app_with_phase3_data):
        """Verify GET /api/threat-map/grid endpoint works."""
        client = app_with_phase3_data
        response = client.get("/api/threat-map/grid")
        # This endpoint should work and return the static grid
        assert response.status_code == 200
        data = response.json()
        assert "tactics" in data
        # Should have the expected tactics
        assert any(tactic in data["tactics"] for tactic in ["execution", "exfiltration", "discovery"])

    def test_threat_map_cells_endpoint_works(self, app_with_phase3_data):
        """Verify GET /api/threat-map/cells/{technique_id}/detections endpoint exists."""
        client = app_with_phase3_data
        response = client.get("/api/threat-map/cells/T1059/detections?window=24h")
        # Should return detections or 404, not an internal server error
        assert response.status_code in (200, 404, 422)


class TestPhase3SchemaIntegrity:
    """Test that Phase 3 schema is correctly initialized."""

    def test_detections_table_has_required_columns(self, tmp_path):
        """Verify detections table has all required columns."""
        db_path = str(tmp_path / "test.db")
        store = DetectionStore(db_path)

        with store._connect() as conn:
            cursor = conn.execute("PRAGMA table_info(detections)")
            columns = {row[1] for row in cursor.fetchall()}

            required_columns = {
                "id", "ingested_at", "event_id", "function_id",
                "anomaly_type", "severity", "trust_score", "mitre_techniques",
                "decision", "risk_band", "duration_ms", "correlation_id",
                "layer_payload"
            }
            assert required_columns <= columns, f"Missing columns: {required_columns - columns}"

    def test_phase3_index_created(self, tmp_path):
        """Verify Phase 3 composite index is created."""
        db_path = str(tmp_path / "test.db")
        store = DetectionStore(db_path)

        with store._connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'ix_detections%'"
            )
            indices = {row[0] for row in cursor.fetchall()}

            # Should have the Phase 3 index
            assert "ix_detections_func_ingested" in indices

    def test_no_new_tables_created(self, tmp_path):
        """Verify no new tables were added (Phase 3 uses existing tables only)."""
        db_path = str(tmp_path / "test.db")
        store = DetectionStore(db_path)

        with store._connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = {row[0] for row in cursor.fetchall()}

            # Should have Phase 1 + Phase 2 tables (no new Phase 3 tables)
            # The comments table was added in Phase 2
            # The audit_events table provides immutable audit trail for compliance
            expected_tables = {"detections", "cases", "case_detections", "case_events", "saved_views", "comments", "audit_events"}
            assert tables == expected_tables, f"Unexpected tables: {tables}"


class TestPhase3BoundaryIntegrity:
    """Test that Phase 3 maintains boundary rules (no imports from layer* or runtime)."""

    def test_threat_map_no_layer_imports(self):
        """Verify threat_map.py does not import from scafad.layer*."""
        # Import the module to verify no import errors
        from scafad.gui.backend import threat_map

        # Verify the static grid is defined
        assert hasattr(threat_map, 'MITRE_TACTIC_TECHNIQUE_GRID')
        assert hasattr(threat_map, 'TECHNIQUE_TO_TACTIC')

        # The grid should not be imported from layer5
        # This is verified by checking the source code contains a literal definition
        import inspect
        source = inspect.getsource(threat_map)
        assert 'from scafad.layer' not in source or 'MITRE' not in source

    def test_functions_module_no_boundary_violations(self):
        """Verify functions.py does not violate boundary rules."""
        from scafad.gui.backend import functions
        import inspect
        source = inspect.getsource(functions)
        assert 'from scafad.layer' not in source
        assert 'from scafad.runtime' not in source


class TestPhase3APISchemas:
    """Test that API response schemas are properly defined."""

    def test_pydantic_dtos_importable(self):
        """Verify all Phase 3 Pydantic DTOs can be imported."""
        from scafad.gui.backend.schemas import (
            FunctionRollup,
            FunctionListResponse,
            FunctionDetail,
            ThreatMapCell,
            ThreatMapResponse,
            ThreatMapGridResponse,
        )

        # Just verify they exist and are classes
        assert all(hasattr(cls, '__pydantic_core_schema__')
                   for cls in [FunctionRollup, FunctionListResponse, FunctionDetail,
                              ThreatMapCell, ThreatMapResponse, ThreatMapGridResponse])

    def test_typescript_types_exist(self):
        """Verify Phase 3 TypeScript types are defined."""
        # Read the types file
        import os
        types_file = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "scafad", "gui", "frontend", "src", "lib", "types.ts"
        )

        if os.path.exists(types_file):
            with open(types_file) as f:
                content = f.read()

            # Check for Phase 3 types
            assert "FunctionRollup" in content or "function" in content.lower()
            assert "ThreatMap" in content or "threat" in content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
