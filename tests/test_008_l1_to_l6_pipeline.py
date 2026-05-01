"""Test #008: Canonical Layer 1 to Layer 6 pipeline."""

from pathlib import Path
import json
from typing import Any, Dict, List

from layer0.app_telemetry import AnomalyType, ExecutionPhase, TelemetryRecord, TelemetrySource
from layer1.pipeline import Layer1CanonicalPipeline
from runtime.pipeline import SCAFADMultilayerPipeline


RCORE_ROOT = Path(__file__).resolve().parents[1]
ARCHIVED_PAYLOAD_DIR = (
    RCORE_ROOT / "legacy" / "archive" / "generated" / "telemetry" / "payloads"
)


def _load_payloads(limit: int = 2) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    files = sorted(ARCHIVED_PAYLOAD_DIR.glob("payload_*.json"))
    for path in files[:limit]:
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    if payloads:
        return payloads
    return [
        {
            "payload_id": "archived-benign",
            "invocation_timestamp": 1744718400.0,
            "function_profile_id": "archived_benign_fn",
            "concurrency_id": "archived-benign-conc",
            "execution_phase": "invoke",
            "anomaly": "none",
            "execution_environment": {"region": "eu-west-1", "runtime": "python3.11", "memory_allocation": 256},
            "telemetry_fields": {"duration_ms": 104, "max_memory_used_mb": 64},
            "network_calls": 1,
            "generic_data": {"email": "user@example.com"},
        },
        {
            "payload_id": "archived-anomaly",
            "invocation_timestamp": 1744718500.0,
            "function_profile_id": "archived_anomaly_fn",
            "concurrency_id": "archived-anomaly-conc",
            "execution_phase": "invoke",
            "anomaly": "memory_spike",
            "execution_environment": {"region": "eu-west-1", "runtime": "python3.11", "memory_allocation": 1024},
            "telemetry_fields": {"duration_ms": 980, "max_memory_used_mb": 912},
            "network_calls": 4,
            "generic_data": {"phone": "+44 7700 900123"},
        },
    ]


def _anomalous_payload() -> Dict[str, Any]:
    return {
        "payload_id": "canonical-anomaly",
        "invocation_timestamp": 1744718600.0,
        "function_profile_id": "canonical_anomaly_fn",
        "concurrency_id": "canonical-anomaly-conc",
        "execution_phase": "invoke",
        "anomaly": "memory_spike",
        "execution_environment": {"region": "eu-west-1", "runtime": "python3.11", "memory_allocation": 1024},
        "telemetry_fields": {"duration_ms": 1400, "max_memory_used_mb": 960},
        "network_calls": 6,
        "generic_data": {"phone": "+44 7700 900123", "email": "alert@example.com"},
    }


def _build_record(payload: Dict[str, Any]) -> TelemetryRecord:
    anomaly = payload.get("anomaly", "none")
    if anomaly == "memory_spike":
        anomaly_type = AnomalyType.MEMORY_SPIKE
    elif anomaly == "network_anomaly":
        anomaly_type = AnomalyType.NETWORK_ANOMALY
    elif anomaly == "timeout":
        anomaly_type = AnomalyType.TIMEOUT_ANOMALY
    else:
        anomaly_type = AnomalyType.BENIGN

    raw_network_calls = payload.get("network_calls", 0)
    if isinstance(raw_network_calls, list):
        network_calls = len(raw_network_calls)
    else:
        network_calls = int(raw_network_calls or 0)

    return TelemetryRecord(
        event_id=str(payload.get("payload_id")),
        timestamp=float(payload.get("invocation_timestamp", 0.0)),
        function_id=str(payload.get("function_profile_id")),
        execution_phase=ExecutionPhase.INVOKE,
        anomaly_type=anomaly_type,
        duration=float(payload.get("telemetry_fields", {}).get("duration_ms", 100)) / 1000.0,
        memory_spike_kb=int(payload.get("telemetry_fields", {}).get("max_memory_used_mb", 64) * 1024),
        cpu_utilization=88.0 if anomaly != "none" else 26.0,
        network_io_bytes=network_calls * 1024,
        fallback_mode=False,
        source=TelemetrySource.SCAFAD_LAYER0,
        concurrency_id=str(payload.get("concurrency_id")),
        region=payload.get("execution_environment", {}).get("region"),
        runtime_version=payload.get("execution_environment", {}).get("runtime"),
        custom_fields={"generic_data": payload.get("generic_data", {})},
    )


def test_008a_canonical_l1_pipeline_produces_processed_record():
    pipeline = Layer1CanonicalPipeline()
    record = _build_record(_load_payloads(limit=1)[0])
    processed = pipeline.process_l0_record(record)
    assert processed.schema_version == "v2.1"
    assert processed.quality_report.completeness_score == 1.0
    assert processed.audit_record.phases_completed == [
        "validation",
        "sanitisation",
        "privacy",
        "hashing",
        "preservation",
        "quality",
        "audit",
    ]
    assert processed.trace_id


def test_008b_benign_record_flows_l1_to_l6_predictably():
    pipeline = Layer1CanonicalPipeline()
    higher = SCAFADMultilayerPipeline()
    benign_payload = _load_payloads(limit=1)[0]
    result = higher.process_record(
        pipeline.process_l0_record(_build_record(benign_payload)),
        analyst_label="benign",
    )
    payload = result.to_dict()
    assert payload["layer2"]["trace_id"] == payload["layer1"]["trace_id"]
    assert payload["layer2"]["evidence_summary"]
    assert result.layer4.decision in {"observe", "review"}
    assert result.layer5.campaign_cluster.startswith(result.layer4.decision)
    assert result.layer4.recommended_action in {"monitor", "analyst_triage"}
    assert result.layer6 is not None
    assert result.layer6.adjusted_trust <= 0.8


def test_008c_anomalous_record_flows_l1_to_l6_predictably():
    pipeline = Layer1CanonicalPipeline()
    higher = SCAFADMultilayerPipeline()
    anomalous_payload = _anomalous_payload()
    result = higher.process_record(
        pipeline.process_l0_record(_build_record(anomalous_payload)),
        analyst_label="confirmed",
        verbosity="verbose",
    )
    assert result.layer2.anomaly_indicated is True
    assert result.layer3.fused_score >= 0.3
    assert result.layer3.risk_band in {"medium", "high"}
    assert result.layer4.decision in {"review", "escalate"}
    assert result.layer4.evidence_items
    assert result.layer5.tactics
    assert result.layer5.attack_story
    assert result.layer6 is not None
    assert result.layer6.trace_id == result.layer1.trace_id
    assert result.layer6.adjusted_trust >= 0.8


def test_008d_threat_alignment_and_feedback_have_stable_contract():
    pipeline = Layer1CanonicalPipeline()
    higher = SCAFADMultilayerPipeline()
    anomalous_payload = _load_payloads(limit=2)[-1]
    result = higher.process_record(
        pipeline.process_l0_record(_build_record(anomalous_payload)),
        analyst_label="true_positive",
    )
    assert isinstance(result.layer5.tactics, list)
    assert isinstance(result.layer5.techniques, list)
    assert isinstance(result.layer5.campaign_cluster, str)
    assert result.layer6 is not None
    assert result.layer6.replay_priority in {"medium", "high"}
    assert result.layer6.feedback_events[0].analyst_label == "true_positive"
    assert result.to_dict()["layer5"]["trace_id"] == result.layer1.trace_id
