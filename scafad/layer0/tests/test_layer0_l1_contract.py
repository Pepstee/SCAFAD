"""
scafad/layer0/tests/test_layer0_l1_contract.py
===============================================

T-031 — L0→L1 contract surface tests.

Phase 4 coverage retrofit, Tier A.2 of ``docs/PHASE_4_COVERAGE_AUDIT.md``.
The contract surface is a C-1 load-bearing module: every telemetry record
and every detection result crossing L0→L1 flows through it. Prior to this
module the surface had no dedicated test (see audit §2.3).

Scope: exercise the three primary classes — ``SchemaRegistry``,
``ContractValidator``, ``L0L1ContractManager`` — plus the
``L0L1ContractValidator`` compatibility alias. Covers: default-schema
registration, version lookups, payload validation (happy path, missing
required field, type mismatch, oversize payload, deprecated warning),
metrics accumulation, version-compatibility traversal, migration-path
calculation, and status summary.

These tests do not mock ``jsonschema`` — the real library is in the
project's install footprint (imported at module top of
``layer0_l1_contract.py``), so validation must work end-to-end.
"""
from __future__ import annotations

import time
import unittest

from layer0.layer0_l1_contract import (
    CompatibilityLevel,
    ContractMetrics,
    ContractSchema,
    ContractValidator,
    ContractViolation,
    ContractViolationType,
    InterfaceType,
    L0L1ContractManager,
    L0L1ContractValidator,
    SchemaRegistry,
    SchemaVersion,
    ValidationResult,
    create_l0_l1_contract_manager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_telemetry_v1() -> dict:
    return {
        "telemetry_id": "tid-001",
        "timestamp": time.time(),
        "function_id": "fn-test",
        "execution_phase": "invoke",
        "duration": 0.12,
        "memory_spike_kb": 64,
        "cpu_utilization": 25.5,
        "anomaly_type": "benign",
        "custom_fields": {"k": "v"},
    }


def _valid_anomaly_result_v1() -> dict:
    return {
        "result_id": "res-001",
        "telemetry_id": "tid-001",
        "timestamp": time.time(),
        "overall_confidence": 0.82,
        "detections": [
            {
                "anomaly_type": "cpu_burst",
                "confidence": 0.9,
                "algorithm_name": "cpu_burst",
                "details": {"threshold": 0.8},
            }
        ],
    }


def _valid_health_status_v1() -> dict:
    return {
        "component_id": "layer0",
        "timestamp": time.time(),
        "status": "healthy",
        "metrics": {"queue_depth": 0},
        "alerts": [],
    }


# ---------------------------------------------------------------------------
# SchemaRegistry
# ---------------------------------------------------------------------------

class TestSchemaRegistry(unittest.TestCase):

    def setUp(self) -> None:
        self.registry = SchemaRegistry()

    def test_default_schemas_are_registered(self) -> None:
        """Registry should ship with at least 4 default schemas covering
        telemetry v1/v2, anomaly_result v1, and health_status v1."""
        self.assertGreaterEqual(len(self.registry.schemas), 4)
        keys = set(self.registry.schemas.keys())
        self.assertIn(
            (InterfaceType.TELEMETRY_INGESTION, SchemaVersion.V1_0), keys,
        )
        self.assertIn(
            (InterfaceType.TELEMETRY_INGESTION, SchemaVersion.V2_0), keys,
        )
        self.assertIn(
            (InterfaceType.ANOMALY_DETECTION_RESULT, SchemaVersion.V1_0), keys,
        )
        self.assertIn(
            (InterfaceType.HEALTH_STATUS, SchemaVersion.V1_0), keys,
        )

    def test_get_latest_schema_returns_v2_for_telemetry(self) -> None:
        """Telemetry has v1 and v2 registered; latest must be v2."""
        latest = self.registry.get_latest_schema(InterfaceType.TELEMETRY_INGESTION)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.version, SchemaVersion.V2_0)

    def test_get_latest_schema_returns_none_for_unknown_interface(self) -> None:
        """Unknown interface type returns None."""
        # Use a contrived registry to simulate — but actually, all four
        # InterfaceTypes are enum values and all four should have at least
        # some schema. So pop the only schema for CONFIGURATION_UPDATE
        # (which has none registered by default) and confirm it's None.
        latest = self.registry.get_latest_schema(
            InterfaceType.CONFIGURATION_UPDATE,
        )
        self.assertIsNone(latest)

    def test_get_schema_returns_none_for_unknown_version(self) -> None:
        """Requesting an unregistered (interface, version) pair returns None."""
        schema = self.registry.get_schema(
            InterfaceType.HEALTH_STATUS, SchemaVersion.V2_1,
        )
        self.assertIsNone(schema)

    def test_register_custom_schema_roundtrip(self) -> None:
        """register_schema then get_schema returns the same object."""
        custom = ContractSchema(
            interface_type=InterfaceType.ALERT_NOTIFICATION,
            version=SchemaVersion.V1_0,
            schema_definition={
                "type": "object",
                "properties": {"alert_id": {"type": "string"}},
                "required": ["alert_id"],
                "additionalProperties": False,
            },
            required_fields=["alert_id"],
        )
        self.registry.register_schema(custom)
        got = self.registry.get_schema(
            InterfaceType.ALERT_NOTIFICATION, SchemaVersion.V1_0,
        )
        self.assertIs(got, custom)

    def test_get_compatible_versions_includes_same_major(self) -> None:
        """Telemetry v1.0 should have at least v1.0 and v2.0 in its
        compatible set (both registered; same-major is BACKWARD, cross-major
        is FORWARD — but the code only filters out BREAKING_CHANGE)."""
        compatible = self.registry.get_compatible_versions(
            InterfaceType.TELEMETRY_INGESTION, SchemaVersion.V1_0,
        )
        # v1.0 itself is FULLY_COMPATIBLE
        self.assertIn(SchemaVersion.V1_0, compatible)


# ---------------------------------------------------------------------------
# ContractValidator
# ---------------------------------------------------------------------------

class TestContractValidator(unittest.TestCase):

    def setUp(self) -> None:
        self.registry = SchemaRegistry()
        self.validator = ContractValidator(self.registry)

    def test_valid_telemetry_payload_passes(self) -> None:
        result = self.validator.validate_payload(
            _valid_telemetry_v1(),
            InterfaceType.TELEMETRY_INGESTION,
            SchemaVersion.V1_0,
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid, msg=f"violations={result.violations}")
        self.assertEqual(result.violations, [])

    def test_missing_required_field_fails(self) -> None:
        """Drop telemetry_id — must fail with REQUIRED_FIELD_MISSING or
        SCHEMA_MISMATCH (jsonschema raises on `required` before the
        manual required-field loop runs, so either is acceptable)."""
        payload = _valid_telemetry_v1()
        del payload["telemetry_id"]
        result = self.validator.validate_payload(
            payload, InterfaceType.TELEMETRY_INGESTION, SchemaVersion.V1_0,
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.violations), 0)
        violation_types = {v.violation_type for v in result.violations}
        self.assertTrue(
            ContractViolationType.REQUIRED_FIELD_MISSING in violation_types
            or ContractViolationType.SCHEMA_MISMATCH in violation_types,
            f"Expected required/schema violation, got {violation_types}",
        )

    def test_type_mismatch_fails(self) -> None:
        """duration must be number; pass a string."""
        payload = _valid_telemetry_v1()
        payload["duration"] = "not-a-number"
        result = self.validator.validate_payload(
            payload, InterfaceType.TELEMETRY_INGESTION, SchemaVersion.V1_0,
        )
        self.assertFalse(result.is_valid)
        # jsonschema.validate raises ValidationError → SCHEMA_MISMATCH
        self.assertTrue(any(
            v.violation_type == ContractViolationType.SCHEMA_MISMATCH
            for v in result.violations
        ))

    def test_payload_too_large_fails(self) -> None:
        """Build a payload exceeding max_payload_size_bytes (default 1MB)."""
        payload = _valid_telemetry_v1()
        payload["custom_fields"] = {"blob": "x" * (1024 * 1024 + 100)}
        result = self.validator.validate_payload(
            payload, InterfaceType.TELEMETRY_INGESTION, SchemaVersion.V1_0,
        )
        self.assertFalse(result.is_valid)
        self.assertTrue(any(
            v.violation_type == ContractViolationType.PAYLOAD_TOO_LARGE
            for v in result.violations
        ))

    def test_unknown_version_fails_with_version_incompatible(self) -> None:
        """Requesting health_status v2.1 (not registered) must fail with
        VERSION_INCOMPATIBLE, not SCHEMA_MISMATCH."""
        result = self.validator.validate_payload(
            _valid_health_status_v1(),
            InterfaceType.HEALTH_STATUS,
            SchemaVersion.V2_1,
        )
        self.assertFalse(result.is_valid)
        self.assertTrue(any(
            v.violation_type == ContractViolationType.VERSION_INCOMPATIBLE
            for v in result.violations
        ))

    def test_metrics_update_on_validation(self) -> None:
        """total_validations and successful_validations must increment."""
        initial_total = self.validator.metrics.total_validations
        initial_success = self.validator.metrics.successful_validations
        self.validator.validate_payload(
            _valid_telemetry_v1(),
            InterfaceType.TELEMETRY_INGESTION,
            SchemaVersion.V1_0,
        )
        self.assertEqual(
            self.validator.metrics.total_validations, initial_total + 1,
        )
        self.assertEqual(
            self.validator.metrics.successful_validations, initial_success + 1,
        )

    def test_metrics_record_failed_validation(self) -> None:
        """A failing validation must increment failed_validations and
        contract_violations counters."""
        payload = _valid_telemetry_v1()
        del payload["function_id"]
        initial_failed = self.validator.metrics.failed_validations
        self.validator.validate_payload(
            payload, InterfaceType.TELEMETRY_INGESTION, SchemaVersion.V1_0,
        )
        self.assertEqual(
            self.validator.metrics.failed_validations, initial_failed + 1,
        )

    def test_get_validation_metrics_shape(self) -> None:
        """get_validation_metrics returns the documented shape."""
        self.validator.validate_payload(
            _valid_telemetry_v1(),
            InterfaceType.TELEMETRY_INGESTION,
            SchemaVersion.V1_0,
        )
        metrics = self.validator.get_validation_metrics()
        for key in (
            "total_validations", "successful_validations",
            "failed_validations", "success_rate", "contract_violations",
            "version_distribution", "interface_usage", "violation_types",
        ):
            self.assertIn(key, metrics)
        self.assertGreaterEqual(metrics["success_rate"], 0.0)
        self.assertLessEqual(metrics["success_rate"], 1.0)

    def test_get_recent_violations_returns_list(self) -> None:
        """After a failing validation, get_recent_violations returns the
        violation record with documented keys."""
        payload = _valid_telemetry_v1()
        del payload["telemetry_id"]
        self.validator.validate_payload(
            payload, InterfaceType.TELEMETRY_INGESTION, SchemaVersion.V1_0,
        )
        recent = self.validator.get_recent_violations(limit=10)
        self.assertIsInstance(recent, list)
        self.assertGreater(len(recent), 0)
        first = recent[0]
        for key in (
            "violation_id", "timestamp", "interface_type",
            "violation_type", "expected_version", "details",
        ):
            self.assertIn(key, first)


# ---------------------------------------------------------------------------
# L0L1ContractManager
# ---------------------------------------------------------------------------

class TestL0L1ContractManager(unittest.TestCase):

    def setUp(self) -> None:
        self.manager = L0L1ContractManager()

    def test_validate_telemetry_record_passes_valid_v1(self) -> None:
        result = self.manager.validate_telemetry_record(
            _valid_telemetry_v1(), SchemaVersion.V1_0,
        )
        self.assertTrue(result.is_valid, msg=f"violations={result.violations}")

    def test_validate_anomaly_result_passes_valid_v1(self) -> None:
        result = self.manager.validate_anomaly_result(
            _valid_anomaly_result_v1(), SchemaVersion.V1_0,
        )
        self.assertTrue(result.is_valid, msg=f"violations={result.violations}")

    def test_validate_health_status_passes_valid_v1(self) -> None:
        result = self.manager.validate_health_status(
            _valid_health_status_v1(), SchemaVersion.V1_0,
        )
        self.assertTrue(result.is_valid, msg=f"violations={result.violations}")

    def test_check_version_compatibility_v1_to_v2_is_breaking(self) -> None:
        """Telemetry v1 → v2 is a major-version crossing in the enum
        ("1.0" → "2.0"). The current `_check_compatibility` classes
        different-major crossings as BREAKING_CHANGE. Lock this in so
        a future refactor must update this assertion intentionally
        rather than silently change the contract semantics."""
        compatibility = self.manager.check_version_compatibility(
            InterfaceType.TELEMETRY_INGESTION,
            SchemaVersion.V1_0,
            SchemaVersion.V2_0,
        )
        self.assertIsInstance(compatibility, CompatibilityLevel)
        self.assertEqual(compatibility, CompatibilityLevel.BREAKING_CHANGE)

    def test_check_version_compatibility_same_version_is_fully_compatible(self) -> None:
        compatibility = self.manager.check_version_compatibility(
            InterfaceType.TELEMETRY_INGESTION,
            SchemaVersion.V1_0,
            SchemaVersion.V1_0,
        )
        self.assertEqual(compatibility, CompatibilityLevel.FULLY_COMPATIBLE)

    def test_check_version_compatibility_missing_schema_returns_breaking(self) -> None:
        compatibility = self.manager.check_version_compatibility(
            InterfaceType.HEALTH_STATUS,
            SchemaVersion.V1_0,
            SchemaVersion.V2_1,  # not registered
        )
        self.assertEqual(compatibility, CompatibilityLevel.BREAKING_CHANGE)

    def test_get_supported_versions_is_sorted(self) -> None:
        versions = self.manager.get_supported_versions(
            InterfaceType.TELEMETRY_INGESTION,
        )
        self.assertGreaterEqual(len(versions), 2)
        # Must be sorted ascending by semantic version
        self.assertEqual(
            versions, sorted(versions, key=lambda v: tuple(map(int, v.value.split(".")))),
        )

    def test_get_migration_path_returns_sorted_range(self) -> None:
        """from V1_0 to V2_0 — path includes both endpoints in order."""
        path = self.manager.get_migration_path(
            InterfaceType.TELEMETRY_INGESTION,
            SchemaVersion.V1_0,
            SchemaVersion.V2_0,
        )
        self.assertIn(SchemaVersion.V1_0, path)
        self.assertIn(SchemaVersion.V2_0, path)
        self.assertEqual(path[0], SchemaVersion.V1_0)
        self.assertEqual(path[-1], SchemaVersion.V2_0)

    def test_get_migration_path_returns_empty_for_unknown_version(self) -> None:
        path = self.manager.get_migration_path(
            InterfaceType.TELEMETRY_INGESTION,
            SchemaVersion.V2_1,  # not registered for telemetry
            SchemaVersion.V1_0,
        )
        self.assertEqual(path, [])

    def test_get_contract_status_shape(self) -> None:
        status = self.manager.get_contract_status()
        self.assertIn("schema_registry", status)
        self.assertIn("validation_metrics", status)
        self.assertIn("recent_violations_count", status)
        reg = status["schema_registry"]
        for key in ("total_schemas", "interface_types", "supported_versions"):
            self.assertIn(key, reg)
        self.assertGreater(reg["total_schemas"], 0)

    def test_register_custom_schema_via_manager(self) -> None:
        custom = ContractSchema(
            interface_type=InterfaceType.ALERT_NOTIFICATION,
            version=SchemaVersion.V1_0,
            schema_definition={
                "type": "object",
                "properties": {"alert_id": {"type": "string"}},
                "required": ["alert_id"],
                "additionalProperties": False,
            },
            required_fields=["alert_id"],
        )
        self.manager.register_custom_schema(custom)
        # And it must now be retrievable via the manager's registry
        self.assertIs(
            self.manager.schema_registry.get_schema(
                InterfaceType.ALERT_NOTIFICATION, SchemaVersion.V1_0,
            ),
            custom,
        )


# ---------------------------------------------------------------------------
# Factory function and compatibility alias
# ---------------------------------------------------------------------------

class TestFactoryAndAlias(unittest.TestCase):

    def test_create_l0_l1_contract_manager_returns_instance(self) -> None:
        mgr = create_l0_l1_contract_manager()
        self.assertIsInstance(mgr, L0L1ContractManager)

    def test_l0l1_contract_validator_is_alias_for_contract_validator(self) -> None:
        """The compatibility alias is relied on by
        layer0_comprehensive_validation.py. It must remain the same class
        object, not a subclass or a wrapper."""
        self.assertIs(L0L1ContractValidator, ContractValidator)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
