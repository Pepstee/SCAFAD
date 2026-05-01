"""
scafad/layer1/tests/test_layer1_utils_validators.py
====================================================

T-033 — Unit tests for `layer1/utils/validators.py`
(TelemetryRecordValidator + module-level helpers).

Phase-4 coverage retrofit, Tier A item 4 (see
`docs/PHASE_4_COVERAGE_AUDIT.md` §4). Pre-retrofit, `utils/validators.py`
had zero direct test coverage — it was transitively exercised by the
pipeline tests in `test_layer1_validation.py` and the extended-module
tests, but its public contract (ValidationRule / ValidationError /
ValidationResult, the four rule types `required` / `type` / `range`
/ `pattern` / `enum`, and the module-level helpers
`validate_telemetry_record`, `validate_field_type`,
`validate_required_fields`, `create_telemetry_record_validator`) had
never been pinned down by assertion.

The schema this module enforces is L1-side of the L0→L1 contract
(`record_id`, `timestamp`, `function_name`, `execution_phase`,
`anomaly_type`, `telemetry_data` required; `provenance_chain`,
`context_metadata`, `schema_version` optional). Silent changes to
that schema would invalidate C-1 claims downstream, so these tests
lock the happy-path vocabulary and the error-type taxonomy in place.

Covered surfaces:
  - Vocabulary: ValidationSeverity (4 members), FieldType (14 members).
  - Dataclass construction: ValidationRule, ValidationError,
    ValidationResult.
  - validate_record happy path on a well-formed v2.1 record.
  - validate_record surfaces `missing_required_field` for dropped keys.
  - validate_record surfaces `type_mismatch` when record_id is not str.
  - validate_record surfaces `enum_violation` for a bad execution_phase.
  - validate_record surfaces `pattern_mismatch` (as a warning) for a
    function_name that breaks the Python-identifier pattern.
  - validate_record emits `unknown_field` warnings for unrecognised keys.
  - add_validation_rule registers a rule into a new schema bucket.
  - Module-level helpers: validate_telemetry_record, validate_field_type
    (TRUE for good types, FALSE for wrong types — incl. bool vs int
    discrimination), validate_required_fields (returns missing names).
  - create_telemetry_record_validator factory returns a
    TelemetryRecordValidator with fresh stats.
  - validation_stats accumulate total_validations across calls.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict

from layer1.utils.validators import (
    FieldType,
    TelemetryRecordValidator,
    ValidationError,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
    create_telemetry_record_validator,
    validate_field_type,
    validate_required_fields,
    validate_telemetry_record,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _v21_record(**overrides: Any) -> Dict[str, Any]:
    """Well-formed v2.1 telemetry record. Passes the default rule set
    with zero errors (a WARNING is still permitted for the pattern
    rule on function_name, but the happy-path base uses a valid
    Python-identifier name so no warning fires either)."""
    base: Dict[str, Any] = {
        "record_id": "rec_0001",
        "timestamp": 1_714_000_000.0,
        "function_name": "demo_lambda",
        "execution_phase": "invocation",
        "anomaly_type": "benign",
        "telemetry_data": {"cpu_usage": 12.5},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Vocabulary / dataclass shapes
# ---------------------------------------------------------------------------

class TestVocabularyContract(unittest.TestCase):
    """Lock in the enum and dataclass surfaces."""

    def test_validation_severity_has_four_levels(self) -> None:
        self.assertEqual(
            {m.name for m in ValidationSeverity},
            {"INFO", "WARNING", "ERROR", "CRITICAL"},
        )

    def test_field_type_vocabulary_is_exhaustive(self) -> None:
        expected = {
            "STRING", "INTEGER", "FLOAT", "BOOLEAN", "TIMESTAMP",
            "IP_ADDRESS", "URL", "EMAIL", "JSON_OBJECT", "BASE64",
            "UUID", "ENUM", "ARRAY", "NESTED_OBJECT",
        }
        self.assertEqual({t.name for t in FieldType}, expected)

    def test_validation_rule_dataclass_minimal_construction(self) -> None:
        rule = ValidationRule(
            field_name="name",
            rule_type="type",
            parameters={"expected_type": FieldType.STRING},
        )
        self.assertEqual(rule.field_name, "name")
        self.assertEqual(rule.rule_type, "type")
        self.assertEqual(rule.severity, ValidationSeverity.ERROR)
        self.assertEqual(rule.description, "")
        self.assertIsNone(rule.custom_validator)

    def test_validation_error_dataclass_minimal_construction(self) -> None:
        err = ValidationError(
            field_name="x",
            error_type="type_mismatch",
            message="wrong type",
            severity=ValidationSeverity.ERROR,
        )
        self.assertEqual(err.field_name, "x")
        self.assertEqual(err.error_type, "type_mismatch")
        self.assertEqual(err.severity, ValidationSeverity.ERROR)
        self.assertIsNone(err.actual_value)


# ---------------------------------------------------------------------------
# validate_record — happy path
# ---------------------------------------------------------------------------

class TestValidateRecordHappyPath(unittest.TestCase):
    """A well-formed v2.1 record must pass validation cleanly."""

    def setUp(self) -> None:
        self.validator = TelemetryRecordValidator()

    def test_valid_v21_record_passes_with_no_errors(self) -> None:
        result = self.validator.validate_record(_v21_record())
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, [])
        self.assertGreater(result.fields_validated, 0)
        self.assertGreaterEqual(result.validation_time_ms, 0.0)

    def test_result_metadata_carries_schema_version_and_record_id(self) -> None:
        result = self.validator.validate_record(_v21_record(record_id="rec_meta"))
        self.assertIsNotNone(result.metadata)
        self.assertEqual(result.metadata.get("schema_version"), "v2.1")
        self.assertEqual(result.metadata.get("record_id"), "rec_meta")


# ---------------------------------------------------------------------------
# validate_record — violation surface
# ---------------------------------------------------------------------------

class TestValidateRecordViolations(unittest.TestCase):
    """Each branch of `_apply_validation_rule` plus
    `_validate_required_fields` and `_validate_unknown_fields` should
    surface as a distinct error_type on the result."""

    def setUp(self) -> None:
        self.validator = TelemetryRecordValidator()

    def test_missing_required_field_fails_validation(self) -> None:
        record = _v21_record()
        del record["function_name"]
        result = self.validator.validate_record(record)
        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(e.error_type == "missing_required_field"
                and e.field_name == "function_name"
                for e in result.errors),
            f"Expected missing_required_field for function_name, got: "
            f"{[(e.error_type, e.field_name) for e in result.errors]}",
        )

    def test_type_mismatch_on_record_id_fails_validation(self) -> None:
        # record_id rule asserts FieldType.STRING
        result = self.validator.validate_record(_v21_record(record_id=12345))
        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(e.error_type == "type_mismatch" and e.field_name == "record_id"
                for e in result.errors),
        )

    def test_enum_violation_on_execution_phase_fails_validation(self) -> None:
        # execution_phase rule asserts allowed_values {invocation, execution,
        # completion, error}
        result = self.validator.validate_record(
            _v21_record(execution_phase="take_off"),
        )
        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(e.error_type == "enum_violation"
                and e.field_name == "execution_phase"
                for e in result.errors),
        )

    def test_pattern_mismatch_on_function_name_raises_warning_only(self) -> None:
        """The function_name pattern rule is severity=WARNING, so a
        non-identifier name must NOT flip is_valid to False — it should
        land as a warning."""
        result = self.validator.validate_record(
            _v21_record(function_name="not a valid identifier"),
        )
        self.assertTrue(result.is_valid, "Pattern rule is WARNING, not ERROR")
        self.assertTrue(
            any(w.error_type == "pattern_mismatch"
                and w.field_name == "function_name"
                for w in result.warnings),
        )

    def test_unknown_field_surfaces_as_warning(self) -> None:
        result = self.validator.validate_record(
            _v21_record(rogue_field="I do not belong here"),
        )
        # Unknown-field check is WARNING-severity, so is_valid stays True
        # provided the rest of the record is fine.
        self.assertTrue(result.is_valid)
        self.assertTrue(
            any(w.error_type == "unknown_field"
                and w.field_name == "rogue_field"
                for w in result.warnings),
        )


# ---------------------------------------------------------------------------
# add_validation_rule + statistics
# ---------------------------------------------------------------------------

class TestValidatorExtensibilityAndStats(unittest.TestCase):

    def test_add_validation_rule_creates_bucket_for_new_schema(self) -> None:
        validator = TelemetryRecordValidator()
        rule = ValidationRule(
            field_name="custom_field",
            rule_type="type",
            parameters={"expected_type": FieldType.STRING},
            severity=ValidationSeverity.ERROR,
            description="Custom rule for v3.0",
        )
        validator.add_validation_rule(rule, schema_version="v3.0")
        self.assertIn("v3.0", validator.validation_rules)
        self.assertEqual(len(validator.validation_rules["v3.0"]), 1)

    def test_validation_stats_accumulate_total_validations(self) -> None:
        validator = TelemetryRecordValidator()
        before = validator.get_validation_stats()
        self.assertEqual(before["total_validations"], 0)
        validator.validate_record(_v21_record())
        validator.validate_record(_v21_record())
        after = validator.get_validation_stats()
        self.assertEqual(after["total_validations"], 2)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

class TestModuleLevelHelpers(unittest.TestCase):

    def test_validate_telemetry_record_convenience_matches_class_method(self) -> None:
        result = validate_telemetry_record(_v21_record())
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_field_type_accepts_correct_types(self) -> None:
        self.assertTrue(validate_field_type("hello", FieldType.STRING))
        self.assertTrue(validate_field_type(42, FieldType.INTEGER))
        self.assertTrue(validate_field_type(3.14, FieldType.FLOAT))
        self.assertTrue(validate_field_type(True, FieldType.BOOLEAN))
        self.assertTrue(validate_field_type({"k": 1}, FieldType.JSON_OBJECT))
        self.assertTrue(validate_field_type([1, 2, 3], FieldType.ARRAY))

    def test_validate_field_type_rejects_wrong_types(self) -> None:
        # Booleans must not register as INTEGER (the validator explicitly
        # guards against this with `not isinstance(x, bool)`).
        self.assertFalse(validate_field_type(True, FieldType.INTEGER))
        self.assertFalse(validate_field_type("not-an-int", FieldType.INTEGER))
        self.assertFalse(validate_field_type(42, FieldType.STRING))
        self.assertFalse(validate_field_type("not-a-list", FieldType.ARRAY))

    def test_validate_required_fields_returns_missing_names(self) -> None:
        record = {"a": 1, "c": 3}
        missing = validate_required_fields(record, ["a", "b", "c", "d"])
        self.assertEqual(set(missing), {"b", "d"})

    def test_validate_required_fields_treats_none_as_missing(self) -> None:
        record = {"a": 1, "b": None}
        missing = validate_required_fields(record, ["a", "b"])
        self.assertEqual(missing, ["b"])

    def test_create_telemetry_record_validator_factory_returns_fresh_instance(self) -> None:
        validator = create_telemetry_record_validator()
        self.assertIsInstance(validator, TelemetryRecordValidator)
        stats = validator.get_validation_stats()
        self.assertEqual(stats["total_validations"], 0)
        self.assertEqual(stats["total_errors"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
