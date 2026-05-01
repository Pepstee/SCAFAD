"""
SCAFAD R-Core to Layer 1 adapter.

This module translates a real `TelemetryRecord` from the Layer 0 schema used
in `scafad-r-core` into the field shape expected by the current Layer 1
validation boundary.

This is the single authoritative translation point between Layers 0 and 1.
No other file should perform this mapping.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from .app_telemetry import TelemetryRecord

logger = logging.getLogger("SCAFAD.RCoreToLayer1Adapter")

ADAPTER_VERSION = "2.0.1"
TARGET_LAYER1_SCHEMA_VERSION = "v2.1"
ERROR_STACK_PLACEHOLDER = "L0 adapter synthesized error context"

_ANOMALY_TYPE_MAP: Dict[str, str] = {
    "benign": "benign",
    "cold_start": "suspicious",
    "cpu_burst": "suspicious",
    "memory_spike": "suspicious",
    "io_intensive": "suspicious",
    "network_anomaly": "suspicious",
    "timeout_anomaly": "suspicious",
    "execution_failure": "suspicious",
    "starvation_fallback": "suspicious",
    "timeout_fallback": "suspicious",
    "schema_violation": "suspicious",
    "adversarial_injection": "malicious",
    "billing_abuse": "malicious",
    "dos_amplification": "malicious",
    "cryptomining": "malicious",
    "data_exfiltration": "malicious",
    "privilege_escalation": "malicious",
    "silent_corruption": "suspicious",
    "semantic_failure": "suspicious",
    "output_corruption": "suspicious",
    "invariant_violation": "suspicious",
}

_EXECUTION_PHASE_MAP: Dict[str, str] = {
    "init": "initialization",
    "invoke": "execution",
    "shutdown": "completion",
    "error": "error",
    "timeout": "timeout",
}

_L1_ALLOWED_ANOMALY_TYPES = frozenset({"benign", "suspicious", "malicious", "unknown"})
_L1_ALLOWED_EXECUTION_PHASES = frozenset({"initialization", "execution", "completion", "error", "timeout"})
_FUNCTION_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9_\-\.]")


class RCoreToLayer1Adapter:
    """Translate a Layer 0 TelemetryRecord into the canonical Layer 1 input shape."""

    def adapt(self, record: TelemetryRecord) -> Dict[str, Any]:
        if record is None:
            raise ValueError("record must not be None")
        if not isinstance(record, TelemetryRecord):
            raise TypeError(f"Expected TelemetryRecord, got {type(record).__name__}")

        anomaly_str = self._normalise_anomaly_type(record.anomaly_type)
        phase_str = self._normalise_execution_phase(record.execution_phase)
        adapted = {
            "record_id": self._safe_record_id(record.event_id),
            "timestamp": record.timestamp,
            "function_name": self._sanitise_function_name(record.function_id),
            "execution_phase": phase_str,
            "anomaly_type": anomaly_str,
            "telemetry_data": self._build_telemetry_data(record, phase_str),
            "provenance_chain": self._build_provenance_chain(record),
            "context_metadata": self._build_context_metadata(record, anomaly_str, phase_str),
            "schema_version": TARGET_LAYER1_SCHEMA_VERSION,
        }
        if phase_str == "error":
            adapted["error_message"] = adapted["telemetry_data"]["error_message"]
            adapted["error_stack"] = ERROR_STACK_PLACEHOLDER
        return adapted

    def _normalise_anomaly_type(self, anomaly_type: Any) -> str:
        raw = anomaly_type.value if hasattr(anomaly_type, "value") else str(anomaly_type)
        mapped = _ANOMALY_TYPE_MAP.get(raw, "unknown")
        if mapped not in _L1_ALLOWED_ANOMALY_TYPES:
            logger.warning("Anomaly type '%s' not in mapping table; using 'unknown'", raw)
            mapped = "unknown"
        return mapped

    def _normalise_execution_phase(self, execution_phase: Any) -> str:
        raw = execution_phase.value if hasattr(execution_phase, "value") else str(execution_phase)
        mapped = _EXECUTION_PHASE_MAP.get(raw, "execution")
        if mapped not in _L1_ALLOWED_EXECUTION_PHASES:
            logger.warning("Execution phase '%s' not in mapping table; using 'execution'", raw)
            mapped = "execution"
        return mapped

    def _safe_record_id(self, event_id: str) -> str:
        try:
            uuid.UUID(str(event_id))
            return str(event_id)
        except (ValueError, AttributeError):
            generated = str(uuid.uuid4())
            logger.warning("event_id '%s' is not UUID format; generated new record_id: %s", event_id, generated)
            return generated

    def _sanitise_function_name(self, function_id: str) -> str:
        sanitised = _FUNCTION_NAME_PATTERN.sub("_", str(function_id or ""))
        return (sanitised or "unknown_function")[:256]

    def _build_telemetry_data(self, record: TelemetryRecord, normalised_phase: str = "execution") -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "l0_duration_ms": record.duration,
            "l0_memory_spike_kb": record.memory_spike_kb,
            "l0_cpu_utilization": record.cpu_utilization,
            "l0_network_io_bytes": record.network_io_bytes,
            "l0_fallback_mode": record.fallback_mode,
            "l0_payload_size_bytes": record.payload_size_bytes,
            "l0_payload_hash": record.payload_hash,
            "layer0_metrics": {
                "l0_adapter_version": ADAPTER_VERSION,
                "l0_original_anomaly_type": record.anomaly_type.value if hasattr(record.anomaly_type, "value") else str(record.anomaly_type),
                "l0_original_execution_phase": record.execution_phase.value if hasattr(record.execution_phase, "value") else str(record.execution_phase),
                "l0_schema_version": record.schema_version,
                "l0_processing_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
        if normalised_phase == "error":
            anomaly_raw = record.anomaly_type.value if hasattr(record.anomaly_type, "value") else str(record.anomaly_type)
            data["error_message"] = f"L0 execution error - anomaly: {anomaly_raw}"
        return data

    def _build_provenance_chain(self, record: TelemetryRecord) -> Dict[str, Any]:
        return {
            "source_layer": "layer_0",
            "provenance_id": record.provenance_id,
            "parent_chain": list(record.parent_chain or []),
            "graph_node_id": record.graph_node_id,
            "causal_depth": record.causal_depth,
            "source": record.source.value if hasattr(record.source, "value") else str(record.source),
            "concurrency_id": record.concurrency_id,
            "conversion_timestamp": datetime.now(timezone.utc).isoformat(),
            "adapter_version": ADAPTER_VERSION,
            "schema_migration": f"r_core_v4.2_to_layer1_{TARGET_LAYER1_SCHEMA_VERSION}",
        }

    def _build_context_metadata(self, record: TelemetryRecord, normalised_anomaly: str, normalised_phase: str) -> Dict[str, Any]:
        return {
            "adversarial_score": record.adversarial_score,
            "economic_risk_score": record.economic_risk_score,
            "silent_failure_probability": record.silent_failure_probability,
            "completeness_score": record.completeness_score,
            "confidence_level": record.confidence_level,
            "data_quality_score": record.data_quality_score,
            "original_anomaly_type": record.anomaly_type.value if hasattr(record.anomaly_type, "value") else str(record.anomaly_type),
            "anomaly_normalised_to": normalised_anomaly,
            "anomaly_severity": record.anomaly_type.severity_level if hasattr(record.anomaly_type, "severity_level") else 0,
            "anomaly_category": record.anomaly_type.category if hasattr(record.anomaly_type, "category") else "unknown",
            "original_execution_phase": record.execution_phase.value if hasattr(record.execution_phase, "value") else str(record.execution_phase),
            "execution_phase_normalised_to": normalised_phase,
            "container_id": record.container_id,
            "region": record.region,
            "runtime_version": record.runtime_version,
            "trigger_type": record.trigger_type,
            "signature": record.signature,
            "content_hash": record.content_hash,
            "signature_algorithm": record.signature_algorithm,
            "emission_channels": list(record.emission_channels or []),
            "emission_attempts": record.emission_attempts,
            "emission_timestamp": record.emission_timestamp,
            "tags": dict(record.tags or {}),
            "custom_fields": dict(record.custom_fields or {}),
            "l0_schema_version": record.schema_version,
        }


__all__ = [
    "ADAPTER_VERSION",
    "TARGET_LAYER1_SCHEMA_VERSION",
    "ERROR_STACK_PLACEHOLDER",
    "RCoreToLayer1Adapter",
]

