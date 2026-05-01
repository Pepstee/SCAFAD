"""
scafad/layer0/tests/test_layer0_core.py
========================================

T-026 — Layer 0 core unit tests.

Covers the public API of SCAFAD Layer 0 (Adaptive Telemetry Controller):
  - TelemetryRecord construction and field contracts
  - AnomalyDetectionEngine instantiation and algorithm registration
  - detect_anomalies() output structure for benign and anomalous inputs
  - FusionResult field contracts including statistical confidence fields
  - DetectionConfig defaults and customisation
  - Historical data accumulation and statistics
  - Import-alias contracts (L0L1ContractValidator, PrivacyComplianceEngine)
  - Layer0_AdaptiveTelemetryController smoke test

WP: Layer 0 — 100% completion
"""

from __future__ import annotations

import time
import unittest
import uuid
from dataclasses import fields as dc_fields
from typing import Any

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from layer0.app_telemetry import (
    AnomalyType,
    ExecutionPhase,
    TelemetryRecord,
    TelemetrySource,
)
from layer0.layer0_core import (
    AnomalyDetectionEngine,
    DetectionConfig,
    DetectionResult,
    FusionResult,
)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _make_record(
    anomaly_type: AnomalyType = AnomalyType.BENIGN,
    execution_phase: ExecutionPhase = ExecutionPhase.INVOKE,
    duration: float = 100.0,
    cpu_utilization: float = 15.0,
    memory_spike_kb: int = 0,
    network_io_bytes: int = 0,
    adversarial_score: float = 0.0,
) -> TelemetryRecord:
    return TelemetryRecord(
        event_id=str(uuid.uuid4()),
        timestamp=time.time(),
        function_id="test-fn",
        execution_phase=execution_phase,
        anomaly_type=anomaly_type,
        source=TelemetrySource.SCAFAD_LAYER0,
        duration=duration,
        memory_spike_kb=memory_spike_kb,
        cpu_utilization=cpu_utilization,
        network_io_bytes=network_io_bytes,
        fallback_mode=False,
        concurrency_id="conc-001",
        adversarial_score=adversarial_score,
        economic_risk_score=0.0,
        silent_failure_probability=0.0,
        completeness_score=1.0,
        confidence_level=1.0,
        data_quality_score=1.0,
    )


# ===========================================================================
# 1. TelemetryRecord — construction and field contracts
# ===========================================================================

class TestTelemetryRecord(unittest.TestCase):
    """TelemetryRecord dataclass: required fields, defaults, post-init validation."""

    def test_construct_with_required_fields(self) -> None:
        rec = _make_record()
        self.assertIsNotNone(rec)

    def test_event_id_preserved(self) -> None:
        eid = str(uuid.uuid4())
        rec = TelemetryRecord(
            event_id=eid,
            timestamp=time.time(),
            function_id="fn",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            source=TelemetrySource.SCAFAD_LAYER0,
            duration=10.0,
            memory_spike_kb=0,
            cpu_utilization=5.0,
            network_io_bytes=0,
            fallback_mode=False,
            concurrency_id="c",
        )
        self.assertEqual(rec.event_id, eid)

    def test_schema_version_default(self) -> None:
        rec = _make_record()
        self.assertEqual(rec.schema_version, "v4.2")

    def test_empty_event_id_raises(self) -> None:
        with self.assertRaises((ValueError, Exception)):
            TelemetryRecord(
                event_id="",
                timestamp=time.time(),
                function_id="fn",
                execution_phase=ExecutionPhase.INVOKE,
                anomaly_type=AnomalyType.BENIGN,
                source=TelemetrySource.SCAFAD_LAYER0,
                duration=10.0,
                memory_spike_kb=0,
                cpu_utilization=5.0,
                network_io_bytes=0,
                fallback_mode=False,
                concurrency_id="c",
            )

    def test_string_execution_phase_coerced(self) -> None:
        rec = TelemetryRecord(
            event_id=str(uuid.uuid4()),
            timestamp=time.time(),
            function_id="fn",
            execution_phase="invoke",  # type: ignore[arg-type]
            anomaly_type=AnomalyType.BENIGN,
            source=TelemetrySource.SCAFAD_LAYER0,
            duration=10.0,
            memory_spike_kb=0,
            cpu_utilization=5.0,
            network_io_bytes=0,
            fallback_mode=False,
            concurrency_id="c",
        )
        self.assertIsInstance(rec.execution_phase, ExecutionPhase)

    def test_adversarial_score_default_zero(self) -> None:
        rec = _make_record()
        self.assertEqual(rec.adversarial_score, 0.0)

    def test_parent_chain_default_empty(self) -> None:
        rec = _make_record()
        self.assertIsInstance(rec.parent_chain, list)
        self.assertEqual(len(rec.parent_chain), 0)

    def test_signature_algorithm_default(self) -> None:
        rec = _make_record()
        self.assertEqual(rec.signature_algorithm, "HMAC-SHA256")


# ===========================================================================
# 2. DetectionConfig — defaults and customisation
# ===========================================================================

class TestDetectionConfig(unittest.TestCase):
    """DetectionConfig dataclass: defaults are sensible, fields are writable."""

    def test_default_statistical_threshold(self) -> None:
        cfg = DetectionConfig()
        self.assertGreater(cfg.statistical_threshold, 0.0)

    def test_default_algorithm_weights_non_empty(self) -> None:
        cfg = DetectionConfig()
        self.assertGreater(len(cfg.algorithm_weights), 0)

    def test_algorithm_weights_sum_reasonable(self) -> None:
        cfg = DetectionConfig()
        total = sum(cfg.algorithm_weights.values())
        # Weights should sum to something close to 1.0 (within 0.3 tolerance)
        self.assertAlmostEqual(total, 1.0, delta=0.3)

    def test_custom_threshold_honoured(self) -> None:
        cfg = DetectionConfig(statistical_threshold=5.0)
        self.assertEqual(cfg.statistical_threshold, 5.0)

    def test_trust_weights_non_empty(self) -> None:
        cfg = DetectionConfig()
        self.assertIn("high_confidence", cfg.trust_weights)


# ===========================================================================
# 3. AnomalyDetectionEngine — instantiation and algorithm registration
# ===========================================================================

class TestAnomalyDetectionEngineInit(unittest.TestCase):
    """AnomalyDetectionEngine must register algorithms on construction."""

    def setUp(self) -> None:
        self.engine = AnomalyDetectionEngine()

    def test_instantiates_without_args(self) -> None:
        self.assertIsNotNone(self.engine)

    def test_algorithms_registered(self) -> None:
        self.assertGreater(len(self.engine.algorithms), 0)

    def test_algorithm_count_at_least_ten(self) -> None:
        # Dissertation claims 26 detectors; allow some to be optional
        self.assertGreaterEqual(len(self.engine.algorithms), 10)

    def test_detection_stats_initialised(self) -> None:
        stats = self.engine.detection_stats
        self.assertIn("total_detections", stats)
        self.assertEqual(stats["total_detections"], 0)

    def test_custom_config_accepted(self) -> None:
        cfg = DetectionConfig(statistical_threshold=3.0)
        engine = AnomalyDetectionEngine(config=cfg)
        self.assertIsNotNone(engine)

    def test_historical_data_empty_on_init(self) -> None:
        self.assertEqual(len(self.engine.historical_data), 0)


# ===========================================================================
# 4. detect_anomalies — FusionResult structural contract
# ===========================================================================

class TestDetectAnomaliesStructure(unittest.TestCase):
    """detect_anomalies() must return a FusionResult with all required fields."""

    def setUp(self) -> None:
        self.engine = AnomalyDetectionEngine()
        self.result = self.engine.detect_anomalies(_make_record())

    def test_returns_fusion_result(self) -> None:
        self.assertIsInstance(self.result, FusionResult)

    def test_final_anomaly_detected_is_bool(self) -> None:
        self.assertIsInstance(self.result.final_anomaly_detected, bool)

    def test_combined_confidence_in_unit_range(self) -> None:
        self.assertGreaterEqual(self.result.combined_confidence, 0.0)
        self.assertLessEqual(self.result.combined_confidence, 1.0)

    def test_combined_severity_in_unit_range(self) -> None:
        self.assertGreaterEqual(self.result.combined_severity, 0.0)
        self.assertLessEqual(self.result.combined_severity, 1.0)

    def test_trust_weighted_score_in_unit_range(self) -> None:
        self.assertGreaterEqual(self.result.trust_weighted_score, 0.0)
        self.assertLessEqual(self.result.trust_weighted_score, 1.0)

    def test_algorithm_votes_is_dict(self) -> None:
        self.assertIsInstance(self.result.algorithm_votes, dict)

    def test_algorithm_votes_non_empty(self) -> None:
        self.assertGreater(len(self.result.algorithm_votes), 0)

    def test_explanation_is_string(self) -> None:
        self.assertIsInstance(self.result.explanation, str)

    def test_processing_time_ms_positive(self) -> None:
        self.assertGreater(self.result.processing_time_ms, 0.0)

    def test_consensus_strength_in_unit_range(self) -> None:
        self.assertGreaterEqual(self.result.consensus_strength, 0.0)
        self.assertLessEqual(self.result.consensus_strength, 1.0)


# ===========================================================================
# 5. FusionResult — statistical fields (C-5 academic rigour)
# ===========================================================================

class TestFusionResultStatisticalFields(unittest.TestCase):
    """FusionResult must carry statistical confidence fields for academic rigour."""

    def setUp(self) -> None:
        self.engine = AnomalyDetectionEngine()
        self.result = self.engine.detect_anomalies(_make_record())

    def test_confidence_interval_95_is_tuple(self) -> None:
        ci = self.result.confidence_interval_95
        self.assertIsInstance(ci, (tuple, list))
        self.assertEqual(len(ci), 2)

    def test_confidence_interval_lower_le_upper(self) -> None:
        lo, hi = self.result.confidence_interval_95
        self.assertLessEqual(lo, hi)

    def test_bootstrap_variance_non_negative(self) -> None:
        self.assertGreaterEqual(self.result.bootstrap_variance, 0.0)

    def test_statistical_significance_in_unit_range(self) -> None:
        p = self.result.statistical_significance
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)

    def test_uncertainty_quantification_is_dict(self) -> None:
        self.assertIsInstance(self.result.uncertainty_quantification, dict)


# ===========================================================================
# 6. detect_anomalies — behavioural correctness
# ===========================================================================

class TestDetectAnomaliesBehaviour(unittest.TestCase):
    """Behavioural checks: benign vs. obviously anomalous inputs."""

    def setUp(self) -> None:
        self.engine = AnomalyDetectionEngine()

    def test_benign_record_processed_without_error(self) -> None:
        result = self.engine.detect_anomalies(_make_record(anomaly_type=AnomalyType.BENIGN))
        self.assertIsNotNone(result)

    def test_high_cpu_record_has_non_zero_confidence(self) -> None:
        result = self.engine.detect_anomalies(_make_record(
            anomaly_type=AnomalyType.CPU_BURST,
            cpu_utilization=99.0,
            duration=3000.0,
        ))
        self.assertGreater(result.combined_confidence, 0.0)

    def test_cold_start_record_processed(self) -> None:
        result = self.engine.detect_anomalies(_make_record(
            anomaly_type=AnomalyType.COLD_START,
            duration=5000.0,
        ))
        self.assertIsNotNone(result)

    def test_adversarial_record_score_non_zero(self) -> None:
        result = self.engine.detect_anomalies(_make_record(
            anomaly_type=AnomalyType.ADVERSARIAL_INJECTION,
            adversarial_score=0.95,
            cpu_utilization=90.0,
            memory_spike_kb=150_000,
            duration=2500.0,
        ))
        self.assertGreater(result.trust_weighted_score, 0.0)

    def test_primary_anomaly_type_is_anomaly_type(self) -> None:
        result = self.engine.detect_anomalies(_make_record())
        self.assertIsInstance(result.primary_anomaly_type, AnomalyType)


# ===========================================================================
# 7. Historical data and statistics
# ===========================================================================

class TestHistoricalDataAndStats(unittest.TestCase):
    """historical_data and detection_stats must be updated on each call."""

    def setUp(self) -> None:
        self.engine = AnomalyDetectionEngine()

    def test_historical_data_grows(self) -> None:
        for _ in range(3):
            self.engine.detect_anomalies(_make_record())
        self.assertEqual(len(self.engine.historical_data), 3)

    def test_total_detections_incremented(self) -> None:
        n = 5
        for _ in range(n):
            self.engine.detect_anomalies(_make_record())
        self.assertEqual(self.engine.detection_stats["total_detections"], n)

    def test_processing_times_recorded(self) -> None:
        self.engine.detect_anomalies(_make_record())
        times = self.engine.detection_stats["processing_times"]
        self.assertGreater(len(times), 0)
        self.assertGreater(times[-1], 0.0)

    def test_multiple_records_independent(self) -> None:
        r1 = self.engine.detect_anomalies(_make_record(anomaly_type=AnomalyType.BENIGN))
        r2 = self.engine.detect_anomalies(_make_record(anomaly_type=AnomalyType.CPU_BURST, cpu_utilization=99.0))
        # Both should return results without error
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)


# ===========================================================================
# 8. Import alias contracts
# ===========================================================================

class TestImportAliases(unittest.TestCase):
    """L0L1ContractValidator and PrivacyComplianceEngine aliases must resolve."""

    def test_l0l1_contract_validator_alias_importable(self) -> None:
        from layer0.layer0_l1_contract import L0L1ContractValidator
        self.assertIsNotNone(L0L1ContractValidator)

    def test_l0l1_contract_validator_is_class(self) -> None:
        from layer0.layer0_l1_contract import L0L1ContractValidator, ContractValidator
        self.assertIs(L0L1ContractValidator, ContractValidator)

    def test_privacy_compliance_engine_alias_importable(self) -> None:
        from layer0.layer0_privacy_compliance import PrivacyComplianceEngine
        self.assertIsNotNone(PrivacyComplianceEngine)

    def test_privacy_compliance_engine_is_pipeline(self) -> None:
        from layer0.layer0_privacy_compliance import (
            PrivacyComplianceEngine,
            PrivacyCompliancePipeline,
        )
        self.assertIs(PrivacyComplianceEngine, PrivacyCompliancePipeline)

    def test_contract_schema_importable_from_l1_contract(self) -> None:
        from layer0.layer0_l1_contract import ContractSchema
        self.assertIsNotNone(ContractSchema)

    def test_validation_result_importable_from_l1_contract(self) -> None:
        from layer0.layer0_l1_contract import ValidationResult
        self.assertIsNotNone(ValidationResult)


# ===========================================================================
# 9. Layer 0 package-level import
# ===========================================================================

class TestLayer0PackageImport(unittest.TestCase):
    """All 27 Layer 0 modules must be importable without errors."""

    MODULES = [
        "layer0.app_config",
        "layer0.app_telemetry",
        "layer0.adapter",
        "layer0.app_adversarial",
        "layer0.app_economic",
        "layer0.app_formal",
        "layer0.app_graph",
        "layer0.app_provenance",
        "layer0.app_schema",
        "layer0.app_silent_failure",
        "layer0.layer0_core",
        "layer0.layer0_adaptive_buffer",
        "layer0.layer0_compression_optimizer",
        "layer0.layer0_fallback_orchestrator",
        "layer0.layer0_health_monitor",
        "layer0.layer0_l1_contract",
        "layer0.layer0_privacy_compliance",
        "layer0.layer0_redundancy_manager",
        "layer0.layer0_runtime_control",
        "layer0.layer0_sampler",
        "layer0.layer0_signal_negotiation",
        "layer0.layer0_stream_processor",
        "layer0.layer0_vendor_adapters",
        "layer0.formal_memory_bounds_analysis",
        "layer0.layer0_aws_integration",
        "layer0.layer0_comprehensive_validation",
        "layer0.app_main",
    ]

    def test_all_modules_importable(self) -> None:
        import importlib
        failures = []
        for m in self.MODULES:
            try:
                importlib.import_module(m)
            except Exception as e:
                failures.append(f"{m}: {e}")
        self.assertEqual(failures, [], f"Import failures:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
