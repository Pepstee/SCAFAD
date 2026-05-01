"""Focused tests for the basic SCAFAD Layers 2-6 scaffold."""

from layer0.app_telemetry import AnomalyType, ExecutionPhase, TelemetryRecord, TelemetrySource
from layer1.pipeline import Layer1CanonicalPipeline
from layer2.detection_matrix import MultiVectorDetectionMatrix
from layer3.trust_fusion import TrustWeightedFusionEngine
from layer4.explainability import ExplainabilityDecisionEngine
from layer5.threat_alignment import ThreatAlignmentEngine
from layer6.feedback_learning import FeedbackLearningEngine
from runtime.pipeline import SCAFADMultilayerPipeline


def _sample_record():
    return TelemetryRecord(
        event_id="rec-001",
        timestamp=1744718400.0,
        function_id="image_processor",
        execution_phase=ExecutionPhase.INVOKE,
        anomaly_type=AnomalyType.MEMORY_SPIKE,
        duration=0.33,
        memory_spike_kb=196608,
        cpu_utilization=91.0,
        network_io_bytes=4096,
        fallback_mode=False,
        source=TelemetrySource.SCAFAD_LAYER0,
        concurrency_id="conc-001",
    )


def _sample_processed_record():
    pipeline = Layer1CanonicalPipeline()
    return pipeline.process_l0_record(_sample_record())


def _legacy_like_record_dict():
    return {
        "record_id": "rec-001",
        "timestamp": 1744718400.0,
        "function_name": "image_processor",
        "execution_phase": "execution",
        "anomaly_type": "memory_spike",
        "telemetry_data": {
            "memory_usage_mb": 192,
            "cpu_utilization": 91,
            "latency_drift": 0.42,
            "graph_edge_count": 24,
            "graph_node_count": 4,
        },
    }


def test_layer2_detection_matrix_produces_multiple_signals():
    result = MultiVectorDetectionMatrix().analyze(_sample_processed_record())
    assert len(result.signals) == 4
    assert result.aggregate_score > 0.0
    assert result.anomaly_indicated is True
    assert result.trace_id
    assert result.trust_context["source_layer"] == "layer_1"
    assert result.detector_consensus > 0.0
    assert "memory_spike_kb" in result.telemetry_evidence
    assert result.evidence_summary


def test_layer3_fusion_uses_trust_weighted_scores():
    detection = MultiVectorDetectionMatrix().analyze(_sample_processed_record())
    fusion = TrustWeightedFusionEngine().fuse(detection)
    assert 0.0 <= fusion.fused_score <= 1.0
    assert "rule_chain" in fusion.trust_weights
    assert len(fusion.leading_signals) == 2
    assert fusion.trace_id == detection.trace_id
    assert fusion.trust_score_input >= 0.1
    assert fusion.risk_band in {"low", "medium", "high"}
    assert fusion.consensus_strength == detection.detector_consensus


def test_layer4_explainability_builds_decision_trace():
    detection = MultiVectorDetectionMatrix().analyze(_sample_processed_record())
    fusion = TrustWeightedFusionEngine().fuse(detection)
    trace = ExplainabilityDecisionEngine().build_trace(
        detection, fusion, verbosity="verbose", redacted_fields=["email"]
    )
    assert trace.record_id == detection.record_id
    assert trace.trace_id == detection.trace_id
    assert trace.decision in {"observe", "review", "escalate"}
    assert trace.severity in {"low", "medium", "high"}
    assert trace.recommended_action in {"monitor", "analyst_triage", "immediate_containment_review"}
    assert trace.redacted_fields == ["email"]
    assert trace.explanation_points
    assert trace.evidence_items


def test_layer5_threat_alignment_maps_to_tactics():
    detection = MultiVectorDetectionMatrix().analyze(_sample_processed_record())
    fusion = TrustWeightedFusionEngine().fuse(detection)
    trace = ExplainabilityDecisionEngine().build_trace(detection, fusion)
    alignment = ThreatAlignmentEngine().align("memory_spike", trace)
    assert alignment.record_id == trace.record_id
    assert alignment.trace_id == trace.trace_id
    assert alignment.tactics
    assert alignment.techniques
    assert alignment.campaign_cluster.startswith(trace.decision)
    assert alignment.attack_story


def test_layer6_feedback_learning_adjusts_trust():
    engine = FeedbackLearningEngine(initial_trust=0.7)
    detection = MultiVectorDetectionMatrix().analyze(_sample_processed_record())
    fusion = TrustWeightedFusionEngine().fuse(detection)
    trace = ExplainabilityDecisionEngine().build_trace(detection, fusion)
    alignment = ThreatAlignmentEngine().align("memory_spike", trace)
    state = engine.ingest_feedback("rec-001", trace.trace_id, "confirmed", alignment)
    assert state.record_id == "rec-001"
    assert state.trace_id == trace.trace_id
    assert state.adjusted_trust > 0.7
    assert state.replay_queue_size == 1
    assert state.replay_priority in {"medium", "high"}
    assert state.feedback_events[0].record_id == "rec-001"
    assert state.feedback_events[0].trace_id == trace.trace_id


def test_multilayer_pipeline_chains_l2_to_l6():
    pipeline = SCAFADMultilayerPipeline()
    result = pipeline.process_record(_sample_processed_record(), analyst_label="confirmed", redacted_fields=["ssn"])
    assert result.layer2.record_id
    assert result.layer1.trace_id
    assert result.layer2.trace_id == result.layer1.trace_id
    assert result.layer3.trace_id == result.layer1.trace_id
    assert result.layer4.trace_id == result.layer1.trace_id
    assert result.layer5.trace_id == result.layer1.trace_id
    assert result.layer3.fused_score >= 0.0
    assert result.layer4.redacted_fields == ["ssn"]
    assert result.layer5.tactics
    assert result.layer6 is not None
    assert result.layer6.trace_id == result.layer1.trace_id
    assert result.layer6.replay_priority in {"medium", "high"}
    assert result.layer6.replay_queue_size == 1


def test_multilayer_pipeline_accepts_legacy_like_dict_envelope():
    pipeline = SCAFADMultilayerPipeline()
    result = pipeline.process_record(_legacy_like_record_dict(), analyst_label="confirmed")
    assert result.layer1.record_id == "rec-001"
    assert result.layer2.anomaly_indicated is True


def test_multilayer_pipeline_result_is_serializable_contract():
    pipeline = SCAFADMultilayerPipeline()
    result = pipeline.process_record(
        _sample_processed_record(), analyst_label="confirmed", verbosity="verbose"
    )
    payload = result.to_dict()
    assert payload["layer1"]["trace_id"] == payload["layer2"]["trace_id"]
    assert payload["layer2"]["record_id"] == payload["layer3"]["record_id"]
    assert payload["layer4"]["trace_id"] == payload["layer5"]["trace_id"]
    assert payload["layer4"]["evidence_items"]
    assert payload["layer5"]["attack_story"]
    assert payload["layer6"]["replay_priority"] in {"medium", "high"}
    assert payload["layer6"]["feedback_events"][0]["trace_id"] == payload["layer1"]["trace_id"]
