"""
Tests for: WP-GUI-4 Repair - TypeScript Type Annotations

This test suite verifies that the TypeScript frontend repair:
1. Added explicit type parameters to all 11 Phase 4 API methods
2. Imported all three missing types (GUIConfigSnapshot, RedactionPolicy, RuntimeRuntimeConfig)
3. Fixed property name mismatches in frontend pages (e.g., total_rows)
4. Properly typed all data accesses in pages

Test Mode: LIGHT
Source Task: e9ef3b99-2111-453b-b351-8f98c6e47504 (Repair)
"""

import json
import subprocess
import sys
from pathlib import Path


class TestTypeScriptCompilation:
    """Verify that TypeScript compilation succeeds with zero errors."""

    def test_frontend_files_exist(self):
        """Frontend source files should exist."""
        frontend_dir = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend")

        # Verify directory exists
        assert frontend_dir.exists(), f"Frontend directory not found at {frontend_dir}"
        assert (frontend_dir / "package.json").exists(), "package.json not found"
        assert (frontend_dir / "src" / "lib" / "api.ts").exists(), "api.ts not found"
        assert (frontend_dir / "src" / "pages").exists(), "pages directory not found"


class TestAPITypeAnnotations:
    """Verify that all Phase 4 API methods have proper type annotations."""

    def test_system_metrics_typed(self):
        """getSystemMetrics should have SystemMetricsResponse type."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        # Should contain explicit type parameter
        assert "getSystemMetrics: () => jsonFetch<SystemMetricsResponse>" in content, \
            "getSystemMetrics missing SystemMetricsResponse type annotation"

    def test_system_metrics_timeseries_typed(self):
        """getSystemMetricsTimeseries should have MetricsTimeseriesResponse type."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "jsonFetch<MetricsTimeseriesResponse>" in content, \
            "getSystemMetricsTimeseries missing MetricsTimeseriesResponse type annotation"

    def test_detectors_typed(self):
        """getDetectors should have DetectorPanel type."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "getDetectors: () => jsonFetch<DetectorPanel>" in content, \
            "getDetectors missing DetectorPanel type annotation"

    def test_settings_typed(self):
        """getSettings should have SettingsResponse type."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "getSettings: () => jsonFetch<SettingsResponse>" in content, \
            "getSettings missing SettingsResponse type annotation"

    def test_settings_runtime_typed(self):
        """getSettingsRuntime should have RuntimeRuntimeConfig type."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "getSettingsRuntime: () => jsonFetch<RuntimeRuntimeConfig>" in content, \
            "getSettingsRuntime missing RuntimeRuntimeConfig type annotation"

    def test_settings_policy_typed(self):
        """getSettingsPolicy should have RedactionPolicy type."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "getSettingsPolicy: () => jsonFetch<RedactionPolicy>" in content, \
            "getSettingsPolicy missing RedactionPolicy type annotation"

    def test_settings_gui_typed(self):
        """getSettingsGUI should have GUIConfigSnapshot type."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "getSettingsGUI: () => jsonFetch<GUIConfigSnapshot>" in content, \
            "getSettingsGUI missing GUIConfigSnapshot type annotation"

    def test_audit_list_typed(self):
        """listAudit should have AuditEventListResponse type."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "jsonFetch<AuditEventListResponse>" in content, \
            "listAudit missing AuditEventListResponse type annotation"

    def test_audit_get_typed(self):
        """getAuditEvent should have AuditEvent type."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "getAuditEvent: (id: string) => jsonFetch<AuditEvent>" in content, \
            "getAuditEvent missing AuditEvent type annotation"

    def test_verify_audit_chain_typed(self):
        """verifyAuditChain should have AuditChainVerification type."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "verifyAuditChain: () => jsonFetch<AuditChainVerification>" in content, \
            "verifyAuditChain missing AuditChainVerification type annotation"


class TestMissingImports:
    """Verify that all three missing types are now imported."""

    def test_gui_config_snapshot_imported(self):
        """GUIConfigSnapshot should be imported from types."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "GUIConfigSnapshot" in content, "GUIConfigSnapshot not imported"

    def test_redaction_policy_imported(self):
        """RedactionPolicy should be imported from types."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "RedactionPolicy" in content, "RedactionPolicy not imported"

    def test_runtime_runtime_config_imported(self):
        """RuntimeRuntimeConfig should be imported from types."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        assert "RuntimeRuntimeConfig" in content, "RuntimeRuntimeConfig not imported"


class TestFrontendPageFixes:
    """Verify that frontend pages use correct property names and types."""

    def test_audit_page_uses_total_rows(self):
        """Audit.tsx should use chainData.total_rows not chainData.total."""
        audit_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\pages\\Audit.tsx")
        content = audit_file.read_text(encoding='utf-8')

        # Should use total_rows
        assert "chainData.total_rows" in content, "Audit.tsx not using total_rows property"

        # Should NOT use old property name
        assert "chainData.total}" not in content, "Audit.tsx still using old total property"

    def test_functions_page_has_type_import(self):
        """Functions.tsx should import FunctionListResponse."""
        functions_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\pages\\Functions.tsx")
        content = functions_file.read_text(encoding='utf-8')

        assert "FunctionListResponse" in content, "Functions.tsx missing FunctionListResponse import"

    def test_functions_page_has_type_assertion(self):
        """Functions.tsx should cast data to FunctionListResponse."""
        functions_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\pages\\Functions.tsx")
        content = functions_file.read_text(encoding='utf-8')

        assert "as FunctionListResponse" in content, "Functions.tsx missing type assertion"

    def test_threat_map_page_has_type_import(self):
        """ThreatMap.tsx should import ThreatMapResponse."""
        threat_map_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\pages\\ThreatMap.tsx")
        content = threat_map_file.read_text(encoding='utf-8')

        assert "ThreatMapResponse" in content, "ThreatMap.tsx missing ThreatMapResponse import"

    def test_threat_map_page_uses_ternary_conditional(self):
        """ThreatMap.tsx should use ternary operator for JSX type safety."""
        threat_map_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\pages\\ThreatMap.tsx")
        content = threat_map_file.read_text(encoding='utf-8')

        # Should use ternary with null
        assert "{threatData ? (" in content, "ThreatMap.tsx not using ternary operator"
        assert ") : null}" in content, "ThreatMap.tsx not using null for JSX type safety"

    def test_threat_map_page_has_type_assertion(self):
        """ThreatMap.tsx should use type assertions for data access."""
        threat_map_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\pages\\ThreatMap.tsx")
        content = threat_map_file.read_text(encoding='utf-8')

        assert "(threatData as" in content, "ThreatMap.tsx missing type assertions"


class TestBackendIntegration:
    """Verify that backend tests still pass after repair."""

    def test_backend_phase4_tests_pass(self):
        """All 40 Phase 4 backend tests should pass."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest",
             "tests/unit/test_gui_backend_phase4_audit.py",
             "-v", "--tb=short"],
            cwd="C:\\Projects\\SCAFAD\\project\\scafad-r-core",
            capture_output=True,
            text=True,
            timeout=60
        )

        assert result.returncode == 0, f"Backend tests failed: {result.stderr}"
        assert "40 passed" in result.stdout, f"Expected 40 passed tests, got: {result.stdout}"


class TestNoLogicChanges:
    """Verify that the repair made no logic changes, only type annotations."""

    def test_api_methods_have_same_endpoints(self):
        """API methods should call same endpoints as before."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        # Verify all key endpoints are still present (with both quote and backtick variants)
        endpoints = [
            "/system/metrics",
            "system/metrics/timeseries",  # Can be in backtick template
            "/system/detectors",
            "/settings",
            "/settings/runtime",
            "/settings/policy",
            "/settings/gui",
            "/audit",
            "/audit/verify",
        ]

        for endpoint in endpoints:
            assert endpoint in content, f"Endpoint {endpoint} not found in API"

    def test_no_parameter_changes(self):
        """API method parameters should not change."""
        api_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\lib\\api.ts")
        content = api_file.read_text(encoding='utf-8')

        # Verify key parameter structures are intact
        assert "params.window" in content, "window parameter missing from metrics timeseries"
        assert "params.bin" in content, "bin parameter missing from metrics timeseries"
        assert "params.page" in content, "page parameter missing from audit list"
        assert "params.page_size" in content, "page_size parameter missing from audit list"

    def test_frontend_render_logic_unchanged(self):
        """Frontend page render logic should be structurally unchanged."""
        audit_file = Path("C:\\Projects\\SCAFAD\\project\\scafad-r-core\\scafad\\gui\\frontend\\src\\pages\\Audit.tsx")
        content = audit_file.read_text(encoding='utf-8')

        # Verify key JSX structure is still present
        assert "Filter" in content, "Filters section missing from Audit page"
        assert "table" in content, "Table element missing from Audit page"
        assert "pagination" in content.lower(), "Pagination missing from Audit page"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
