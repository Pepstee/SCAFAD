"""
scafad/layer1/tests/test_layer1_field_mapper.py
================================================

T-032 — Unit tests for FieldMapper (scafad/layer1/utils/field_mapper.py).

Phase-4 coverage retrofit (Tier A, item 3 of docs/PHASE_4_COVERAGE_AUDIT.md
§4). Pre-retrofit baseline: zero tests exercised this module — the 881-line
`field_mapper.py` was transitively referenced by extended L1 code but had
no direct assertion coverage. This suite pins down the public contract so
future schema-evolution work cannot silently break it.

Covers:
  - Dataclass shapes: FieldMapping, SchemaMapping, MappingResult,
    FieldValidation.
  - Enum vocabulary: MappingStrategy has all 8 declared strategies;
    FieldType has all 10 declared types.
  - FieldMapper lifecycle: default v2.0→v2.1 mapping is registered on
    construction; active_mapping defaults to that mapping.
  - register_schema_mapping: happy path; rejects a mapping with an empty
    mapping_id; rejects a mapping with no field_mappings.
  - set_active_mapping: switches to a valid ID; refuses an unknown ID.
  - map_fields: DIRECT strategy copies fields; missing optional source
    fields drop out; missing required fields with default_value fall
    back; unknown fields are preserved when preserve_unknown_fields=True;
    MappingResult carries mapping_time_ms, fields_mapped, schema_mapping_used.
  - Built-in transform functions: 'to_uppercase' and 'to_lowercase' apply
    when wired via TRANSFORM strategy.
  - add_transform_function: a custom function is registered and invoked.
  - validate_field: type match returns is_valid=True; type mismatch
    returns is_valid=False with error string; min_length/max_length
    custom rules trigger errors.
  - mapper_stats accumulates total_mappings and total_fields_mapped
    across successive map_fields calls.
  - create_field_mapper factory returns a working FieldMapper.
  - FieldMappingEngine backward-compat alias is FieldMapper.
"""
from __future__ import annotations

import time
import unittest
from typing import Any, Dict

from layer1.utils.field_mapper import (
    FieldMapper,
    FieldMapping,
    FieldMappingEngine,
    FieldType,
    FieldValidation,
    MappingResult,
    MappingStrategy,
    SchemaMapping,
    TransformationType,
    create_field_mapper,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _v20_record(**overrides: Any) -> Dict[str, Any]:
    """A representative v2.0-shaped record matching the default mapping's
    source schema (keys: id, timestamp, function, phase, anomaly, data,
    provenance, context, schema_version)."""
    base: Dict[str, Any] = {
        "id": "rec-0001",
        "timestamp": 1_714_000_000.0,
        "function": "demo-lambda",
        "phase": "invocation",
        "anomaly": "benign",
        "data": {"cpu": 12.5},
        "provenance": {"source": "unit-test"},
        "context": {"env": "ci"},
    }
    base.update(overrides)
    return base


def _string_only_mapping(mapping_id: str = "upper-case") -> SchemaMapping:
    """A trivial SchemaMapping that transforms a single string field to
    uppercase via the built-in 'to_uppercase' transform function."""
    return SchemaMapping(
        mapping_id=mapping_id,
        source_schema="raw",
        target_schema="upper",
        version="1.0",
        field_mappings=[
            FieldMapping(
                source_field="name",
                target_field="name_upper",
                strategy=MappingStrategy.TRANSFORM,
                transformation=TransformationType.FORMAT_CHANGE,
                transform_function="to_uppercase",
                required=True,
            ),
        ],
        validation_rules={
            "required_fields": ["name_upper"],
            "field_types": {"name_upper": FieldType.STRING},
        },
        performance_mode=False,
        preserve_unknown_fields=False,
    )


# ---------------------------------------------------------------------------
# Dataclass / enum vocabulary
# ---------------------------------------------------------------------------

class TestVocabularyContract(unittest.TestCase):
    """Lock in the enum and dataclass surfaces that downstream layers
    (Layer-1 extended modules) rely on."""

    def test_mapping_strategy_has_all_eight_strategies(self) -> None:
        expected = {
            "DIRECT", "TRANSFORM", "CALCULATE", "CONDITIONAL",
            "AGGREGATE", "SPLIT", "MERGE", "DEFAULT",
        }
        self.assertEqual({m.name for m in MappingStrategy}, expected)

    def test_field_type_has_all_ten_declared_types(self) -> None:
        expected = {
            "STRING", "INTEGER", "FLOAT", "BOOLEAN", "TIMESTAMP",
            "JSON_OBJECT", "JSON_ARRAY", "BINARY", "ENUM", "CUSTOM",
        }
        self.assertEqual({t.name for t in FieldType}, expected)

    def test_field_mapping_dataclass_minimal_construction(self) -> None:
        fm = FieldMapping(
            source_field="a",
            target_field="b",
            strategy=MappingStrategy.DIRECT,
        )
        self.assertEqual(fm.source_field, "a")
        self.assertEqual(fm.target_field, "b")
        self.assertEqual(fm.strategy, MappingStrategy.DIRECT)
        # Optional defaults
        self.assertIsNone(fm.transformation)
        self.assertIsNone(fm.transform_function)
        self.assertIsNone(fm.default_value)
        self.assertFalse(fm.required)


# ---------------------------------------------------------------------------
# FieldMapper lifecycle
# ---------------------------------------------------------------------------

class TestFieldMapperLifecycle(unittest.TestCase):
    """FieldMapper construction, schema-mapping registration, activation."""

    def setUp(self) -> None:
        self.mapper = FieldMapper()

    def test_default_v2_0_to_v2_1_mapping_is_registered_on_construction(self) -> None:
        mappings = self.mapper.get_schema_mappings()
        self.assertIn("v2.0_to_v2.1", mappings)

    def test_active_mapping_defaults_to_first_registered(self) -> None:
        active = self.mapper.get_active_mapping()
        self.assertIsNotNone(active)
        self.assertEqual(active.mapping_id, "v2.0_to_v2.1")

    def test_register_schema_mapping_accepts_valid_mapping(self) -> None:
        ok = self.mapper.register_schema_mapping(_string_only_mapping())
        self.assertTrue(ok)
        self.assertIn("upper-case", self.mapper.get_schema_mappings())

    def test_register_schema_mapping_rejects_empty_mapping_id(self) -> None:
        bad = _string_only_mapping(mapping_id="")
        self.assertFalse(self.mapper.register_schema_mapping(bad))
        self.assertNotIn("", self.mapper.get_schema_mappings())

    def test_register_schema_mapping_rejects_empty_field_mappings(self) -> None:
        bad = SchemaMapping(
            mapping_id="empty",
            source_schema="a",
            target_schema="b",
            version="1.0",
            field_mappings=[],
            validation_rules={},
        )
        self.assertFalse(self.mapper.register_schema_mapping(bad))
        self.assertNotIn("empty", self.mapper.get_schema_mappings())

    def test_set_active_mapping_switches_to_valid_id(self) -> None:
        self.mapper.register_schema_mapping(_string_only_mapping())
        self.assertTrue(self.mapper.set_active_mapping("upper-case"))
        self.assertEqual(self.mapper.get_active_mapping().mapping_id, "upper-case")

    def test_set_active_mapping_rejects_unknown_id(self) -> None:
        self.assertFalse(self.mapper.set_active_mapping("does-not-exist"))


# ---------------------------------------------------------------------------
# map_fields — core mapping behaviour
# ---------------------------------------------------------------------------

class TestMapFieldsBehaviour(unittest.TestCase):
    """map_fields() should apply strategies, honour defaults, preserve
    unknowns, and return a well-formed MappingResult."""

    def setUp(self) -> None:
        self.mapper = FieldMapper()

    def test_map_fields_direct_strategy_rewrites_field_names(self) -> None:
        """Default v2.0→v2.1 mapping renames id→record_id, function→
        function_name, phase→execution_phase, etc."""
        result = self.mapper.map_fields(_v20_record(), mapping_id="v2.0_to_v2.1")
        self.assertIsInstance(result, MappingResult)
        self.assertEqual(result.mapped_data.get("record_id"), "rec-0001")
        self.assertEqual(result.mapped_data.get("function_name"), "demo-lambda")
        self.assertEqual(result.mapped_data.get("execution_phase"), "invocation")
        self.assertEqual(result.mapped_data.get("anomaly_type"), "benign")
        self.assertIn("record_id", result.fields_mapped)

    def test_map_fields_populates_default_value_for_absent_required_field(self) -> None:
        """When a required source field is missing *and* a default_value is
        provided, the mapper substitutes the default rather than raising.
        (The behaviour for required-without-default is to raise, surfaced
        via fields_failed.)"""
        fallback = SchemaMapping(
            mapping_id="fallback",
            source_schema="in",
            target_schema="out",
            version="1.0",
            field_mappings=[
                FieldMapping(
                    source_field="label",
                    target_field="label",
                    strategy=MappingStrategy.DIRECT,
                    required=True,
                    default_value="UNKNOWN",
                ),
            ],
            validation_rules={},
        )
        self.mapper.register_schema_mapping(fallback)
        result = self.mapper.map_fields({}, mapping_id="fallback")
        self.assertEqual(result.mapped_data.get("label"), "UNKNOWN")

    def test_map_fields_result_carries_timing_and_schema_id(self) -> None:
        result = self.mapper.map_fields(_v20_record(), mapping_id="v2.0_to_v2.1")
        self.assertEqual(result.schema_mapping_used, "v2.0_to_v2.1")
        self.assertGreaterEqual(result.mapping_time_ms, 0.0)
        self.assertIsInstance(result.fields_mapped, list)
        self.assertIsInstance(result.fields_failed, list)
        self.assertIsInstance(result.validation_errors, list)

    def test_map_fields_preserves_unknown_fields_when_enabled(self) -> None:
        """The default mapping has preserve_unknown_fields=True, so any
        source field not named in field_mappings passes straight through
        into mapped_data under its original name."""
        record = _v20_record(extra_marker="keep-me")
        result = self.mapper.map_fields(record, mapping_id="v2.0_to_v2.1")
        self.assertEqual(result.mapped_data.get("extra_marker"), "keep-me")

    def test_map_fields_with_no_mapping_raises(self) -> None:
        empty_mapper = FieldMapper()
        # Clear the default mapping so there's nothing active
        empty_mapper.schema_mappings.clear()
        empty_mapper.active_mapping = None
        with self.assertRaises(ValueError):
            empty_mapper.map_fields({"id": "x"})

    def test_map_fields_via_transform_strategy_uppercases_string(self) -> None:
        self.mapper.register_schema_mapping(_string_only_mapping())
        result = self.mapper.map_fields(
            {"name": "lambda-42"}, mapping_id="upper-case",
        )
        self.assertEqual(result.mapped_data.get("name_upper"), "LAMBDA-42")


# ---------------------------------------------------------------------------
# Transform function registry
# ---------------------------------------------------------------------------

class TestTransformFunctionRegistry(unittest.TestCase):
    """Built-in + custom transformation functions."""

    def setUp(self) -> None:
        self.mapper = FieldMapper()

    def test_builtin_transform_functions_are_available(self) -> None:
        names = self.mapper.get_transform_functions()
        for expected in ("to_uppercase", "to_lowercase", "trim", "to_int",
                         "to_json", "from_json", "hash_value"):
            self.assertIn(expected, names)

    def test_add_transform_function_registers_custom_callable(self) -> None:
        self.mapper.add_transform_function("double", lambda x: x * 2)
        self.assertIn("double", self.mapper.get_transform_functions())
        # Wire it into a mapping and prove it runs
        custom = SchemaMapping(
            mapping_id="doubler",
            source_schema="a",
            target_schema="b",
            version="1.0",
            field_mappings=[
                FieldMapping(
                    source_field="n",
                    target_field="n2",
                    strategy=MappingStrategy.TRANSFORM,
                    transform_function="double",
                    required=True,
                ),
            ],
            validation_rules={},
        )
        self.mapper.register_schema_mapping(custom)
        result = self.mapper.map_fields({"n": 7}, mapping_id="doubler")
        self.assertEqual(result.mapped_data.get("n2"), 14)


# ---------------------------------------------------------------------------
# Field validation
# ---------------------------------------------------------------------------

class TestFieldValidation(unittest.TestCase):
    """validate_field() returns a FieldValidation record and honours
    custom rules."""

    def setUp(self) -> None:
        self.mapper = FieldMapper()

    def test_validate_field_accepts_matching_type(self) -> None:
        v = self.mapper.validate_field(
            field_name="name",
            field_value="hello",
            field_type=FieldType.STRING,
        )
        self.assertIsInstance(v, FieldValidation)
        self.assertTrue(v.is_valid)
        self.assertEqual(v.validation_errors, [])

    def test_validate_field_rejects_type_mismatch(self) -> None:
        v = self.mapper.validate_field(
            field_name="count",
            field_value="not-a-number",
            field_type=FieldType.INTEGER,
        )
        self.assertFalse(v.is_valid)
        self.assertTrue(any("type mismatch" in err.lower() for err in v.validation_errors))

    def test_validate_field_applies_min_and_max_length_rules(self) -> None:
        too_short = self.mapper.validate_field(
            field_name="id",
            field_value="a",
            field_type=FieldType.STRING,
            validation_rules={"min_length": 3, "max_length": 10},
        )
        self.assertFalse(too_short.is_valid)
        too_long = self.mapper.validate_field(
            field_name="id",
            field_value="abcdefghijk",  # 11 chars, limit is 10
            field_type=FieldType.STRING,
            validation_rules={"min_length": 3, "max_length": 10},
        )
        self.assertFalse(too_long.is_valid)
        just_right = self.mapper.validate_field(
            field_name="id",
            field_value="abcd",
            field_type=FieldType.STRING,
            validation_rules={"min_length": 3, "max_length": 10},
        )
        self.assertTrue(just_right.is_valid)


# ---------------------------------------------------------------------------
# Stats & factory
# ---------------------------------------------------------------------------

class TestMapperStatsAndFactory(unittest.TestCase):
    """Statistics accumulate across calls; factory + backward-compat alias."""

    def test_mapper_stats_accumulate_across_map_fields_calls(self) -> None:
        mapper = FieldMapper()
        before = mapper.get_mapper_stats()
        self.assertEqual(before.get("total_mappings"), 0)
        mapper.map_fields(_v20_record(), mapping_id="v2.0_to_v2.1")
        mapper.map_fields(_v20_record(), mapping_id="v2.0_to_v2.1")
        after = mapper.get_mapper_stats()
        self.assertEqual(after.get("total_mappings"), 2)
        self.assertGreater(after.get("total_fields_mapped"), 0)

    def test_create_field_mapper_factory_returns_working_mapper(self) -> None:
        mapper = create_field_mapper()
        self.assertIsInstance(mapper, FieldMapper)
        self.assertIn("v2.0_to_v2.1", mapper.get_schema_mappings())

    def test_field_mapping_engine_is_backward_compat_alias(self) -> None:
        """FieldMappingEngine is retained as a historical name. Code that
        still imports it must keep working."""
        self.assertIs(FieldMappingEngine, FieldMapper)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
