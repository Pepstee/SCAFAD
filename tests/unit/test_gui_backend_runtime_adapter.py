"""Unit tests for the GUI runtime adapter."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from scafad.gui.backend.runtime_adapter import GUIRuntimeAdapter, IngestionOutcome  # noqa: E402


@pytest.fixture
def adapter() -> GUIRuntimeAdapter:
    a = GUIRuntimeAdapter()
    a.reset_latency()
    return a


def test_adapter_runs_canonical_runtime(adapter: GUIRuntimeAdapter) -> None:
    outcome = adapter.ingest({
        "event_id": "adapter-evt-1",
        "function_id": "adapter_fn",
        "anomaly": "memory_spike",
        "duration": 0.95,
        "memory_spike_kb": 262_144,
        "cpu_utilization": 89.0,
    })
    assert isinstance(outcome, IngestionOutcome)
    assert outcome.severity in {"observe", "review", "escalate"}
    assert outcome.duration_ms > 0
    assert "layer0_record" in outcome.layer_payload
    assert "multilayer_result" in outcome.layer_payload


def test_adapter_projects_function_id_from_event(adapter: GUIRuntimeAdapter) -> None:
    outcome = adapter.ingest({
        "event_id": "adapter-evt-2",
        "function_id": "billing_aggregator",
        "anomaly": "benign",
    })
    assert outcome.function_id == "billing_aggregator"


def test_adapter_returns_mitre_techniques_list(adapter: GUIRuntimeAdapter) -> None:
    outcome = adapter.ingest({
        "event_id": "adapter-evt-3",
        "function_id": "auth_service",
        "anomaly": "security_anomaly",
        "adversarial_score": 0.8,
    })
    assert isinstance(outcome.mitre_techniques, list)
    for t in outcome.mitre_techniques:
        assert isinstance(t, str)


def test_adapter_records_latency_p95(adapter: GUIRuntimeAdapter) -> None:
    for i in range(3):
        adapter.ingest({
            "event_id": f"latency-{i}",
            "function_id": "latency_fn",
            "anomaly": "benign",
        })
    p95 = adapter.latency_p95_ms()
    assert p95 > 0


def test_adapter_severity_falls_back_to_observe_when_unknown(adapter: GUIRuntimeAdapter) -> None:
    # Synthesise a payload with an unrecognised decision label and re-project.
    payload = {
        "layer0_record": {"event_id": "x", "function_id": "fn"},
        "layer1_record": {"anomaly_type": "benign"},
        "multilayer_result": {
            "layer3": {"fused_score": 0.1, "risk_band": "low"},
            "layer4": {"decision": "totally-not-a-real-decision"},
            "layer5": {"techniques": []},
        },
    }
    out = GUIRuntimeAdapter._project_outcome(payload, duration_ms=1.0, event={})
    assert out.severity == "observe"


def test_adapter_handles_dict_techniques_defensively() -> None:
    payload = {
        "layer0_record": {"event_id": "y", "function_id": "fn"},
        "layer1_record": {"anomaly_type": "memory_spike"},
        "multilayer_result": {
            "layer3": {"fused_score": 0.5, "risk_band": "medium"},
            "layer4": {"decision": "review"},
            "layer5": {"techniques": {"T1059": {}, "T1110": {}}},
        },
    }
    out = GUIRuntimeAdapter._project_outcome(payload, duration_ms=1.0, event={})
    assert set(out.mitre_techniques) == {"T1059", "T1110"}
