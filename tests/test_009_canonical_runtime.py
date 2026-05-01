"""Test #009: canonical application runtime entrypoint."""

from scafad.layer0 import AnomalyType, ExecutionPhase, TelemetryRecord, TelemetrySource
from scafad.runtime import SCAFADCanonicalRuntime


def _make_record() -> TelemetryRecord:
    return TelemetryRecord(
        event_id="runtime-record-001",
        timestamp=1744719000.0,
        function_id="runtime_image_processor",
        execution_phase=ExecutionPhase.INVOKE,
        anomaly_type=AnomalyType.MEMORY_SPIKE,
        duration=0.95,
        memory_spike_kb=262144,
        cpu_utilization=89.0,
        network_io_bytes=6144,
        fallback_mode=False,
        source=TelemetrySource.SCAFAD_LAYER0,
        concurrency_id="runtime-conc-001",
        region="eu-west-1",
        runtime_version="python3.11",
        custom_fields={"email": "runtime@example.com"},
    )


def _make_event() -> dict:
    return {
        "payload_id": "runtime-event-001",
        "invocation_timestamp": 1744719010.0,
        "function_profile_id": "runtime_event_processor",
        "concurrency_id": "runtime-event-conc",
        "execution_phase": "invoke",
        "anomaly": "memory_spike",
        "execution_environment": {"region": "eu-west-1", "runtime": "python3.11"},
        "telemetry_fields": {"duration_ms": 1250, "max_memory_used_mb": 512},
        "network_calls": 6,
        "generic_data": {"phone": "+44 7700 900123"},
        "confidence_level": 0.92,
    }


def test_009a_runtime_processes_real_telemetry_record():
    runtime = SCAFADCanonicalRuntime()
    result = runtime.process_record(_make_record(), analyst_label="confirmed")
    assert result.adapted_record["record_id"]
    assert result.layer1_record.trace_id
    assert result.multilayer_result.layer2.anomaly_indicated is True
    assert result.multilayer_result.layer4.decision in {"review", "escalate"}
    assert result.multilayer_result.layer6 is not None


def test_009b_runtime_builds_and_processes_event_payload():
    runtime = SCAFADCanonicalRuntime()
    result = runtime.process_event(_make_event(), analyst_label="true_positive")
    assert result.layer0_record.function_id == "runtime_event_processor"
    assert result.layer1_record.schema_version == "v2.1"
    assert result.multilayer_result.layer3.risk_band in {"medium", "high"}
    assert result.multilayer_result.layer5.attack_story


def test_009c_runtime_result_is_serializable_end_to_end():
    runtime = SCAFADCanonicalRuntime()
    result = runtime.process_event(_make_event(), analyst_label="true_positive")
    payload = result.to_dict()
    assert payload["adapted_record"]["record_id"] == payload["layer1_record"]["record_id"]
    assert payload["layer1_record"]["trace_id"] == payload["multilayer_result"]["layer2"]["trace_id"]
    assert payload["multilayer_result"]["layer6"]["trace_id"] == payload["layer1_record"]["trace_id"]
