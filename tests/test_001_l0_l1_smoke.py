"""
Test #001: L0 -> L1 Smoke Test
================================

PERMANENT TEST -- must never be deleted.
Must pass after every subsequent code change in both repositories.

Scope: minimum viable integration path only.
  real TelemetryRecord  ->  RCoreToLayer1Adapter  ->  InputValidationGateway

Does NOT depend on layer1_core.py, subsystems, or any Layer 1 component
beyond the validation gate. The sanitisation, privacy, and preservation
layers are covered in Test #002 onwards.

To run:
    cd scafad-r-core
    python -m pytest tests/test_001_l0_l1_smoke.py -v

Dependencies (must be installed):
    pip install pytest numpy scipy jsonschema cerberus validators psutil

Author: Claude (Test #001, written 2026-04-15)
Version: 1.0.1
Revision: importlib.util path loading to avoid core/ namespace collision
"""

import asyncio
import importlib.util
import os
import sys
import time
import types
import uuid
import inspect
from urllib.parse import urlparse

import pytest

# =============================================================================
# Path setup
# =============================================================================

RCORE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DELTA_ROOT = os.path.join(os.path.dirname(RCORE_ROOT), "scafad-delta")

for _path in [RCORE_ROOT, DELTA_ROOT]:
    if _path not in sys.path:
        sys.path.append(_path)


def _install_dependency_shims():
    """
    Provide tiny import shims for optional Layer 1 validator dependencies that
    are not installed in this environment.
    """
    if "cerberus" not in sys.modules:
        sys.modules["cerberus"] = types.ModuleType("cerberus")

    if "validators" not in sys.modules:
        validators_mod = types.ModuleType("validators")

        def _url(value):
            if not isinstance(value, str):
                return False
            parsed = urlparse(value)
            return bool(parsed.scheme and parsed.netloc)

        def _email(value):
            return isinstance(value, str) and "@" in value and "." in value.split("@")[-1]

        validators_mod.url = _url
        validators_mod.email = _email
        sys.modules["validators"] = validators_mod


_install_dependency_shims()


def _load_delta(module_name: str, relative_path: str):
    """Load a scafad-delta module by explicit file path into a unique namespace."""
    full_path = os.path.join(DELTA_ROOT, relative_path)
    qualified = f"scafad_delta.{module_name}"
    spec = importlib.util.spec_from_file_location(qualified, full_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load delta module '{module_name}' from {full_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = mod
    spec.loader.exec_module(mod)
    return mod


# Load delta modules under unique names -- avoids core/ namespace collision
_delta_config     = _load_delta("layer1_config",    "configs/layer1_config.py")
_delta_validation = _load_delta("layer1_validation", "core/layer1_validation.py")

Layer1Config           = _delta_config.Layer1Config
ProcessingMode         = _delta_config.ProcessingMode
InputValidationGateway = _delta_validation.InputValidationGateway
ValidationStatus       = _delta_validation.ValidationStatus

# =============================================================================
# r-core imports
# =============================================================================

from layer0.app_telemetry import (          # noqa: E402
    AnomalyType,
    ExecutionPhase,
    TelemetryRecord,
    TelemetrySource,
)
from layer0.adapter import RCoreToLayer1Adapter  # noqa: E402

# =============================================================================
# Helpers
# =============================================================================

def make_record(**overrides) -> TelemetryRecord:
    """Construct a fully populated real TelemetryRecord with no mocks or stubs."""
    defaults = dict(
        event_id=str(uuid.uuid4()),
        timestamp=time.time(),
        function_id="test_function_smoke_001",
        execution_phase=ExecutionPhase.INVOKE,
        anomaly_type=AnomalyType.MEMORY_SPIKE,
        duration=0.250,
        memory_spike_kb=512,
        cpu_utilization=45.0,
        network_io_bytes=1024,
        fallback_mode=False,
        source=TelemetrySource.SCAFAD_LAYER0,
        concurrency_id=str(uuid.uuid4()),
    )
    defaults.update(overrides)
    return TelemetryRecord(**defaults)


def make_gateway_config() -> Layer1Config:
    """Layer1Config for smoke testing: standard validation level."""
    return Layer1Config(
        test_mode=False,
        processing_mode=ProcessingMode.TESTING,
        schema_version="v2.1",
    )


def run_async(coro):
    """Run an async coroutine synchronously in a fresh event loop."""
    if not inspect.isawaitable(coro):
        return coro
    return asyncio.run(coro)


# =============================================================================
# Test #001 Suite
# =============================================================================

class TestL0ToL1Smoke:
    """
    Test #001 -- L0->L1 Smoke Test Suite.

    All tests are permanent per the SCAFAD development protocol.
    """

    def test_001a_adapter_produces_all_required_l1_fields(self):
        """Adapter output contains every field required by L1 v2.1 schema."""
        record = make_record()
        result = RCoreToLayer1Adapter().adapt(record)
        required = {"record_id", "timestamp", "function_name",
                    "execution_phase", "anomaly_type", "telemetry_data", "schema_version"}
        missing = required - result.keys()
        assert not missing, f"Missing required fields: {missing}"

    def test_001b_schema_version_is_v2_1(self):
        """Adapter always emits schema_version='v2.1' regardless of L0 version."""
        result = RCoreToLayer1Adapter().adapt(make_record())
        assert result["schema_version"] == "v2.1"
        assert result["context_metadata"]["l0_schema_version"] == "v4.2"

    def test_001c_event_id_maps_to_record_id(self):
        """event_id (L0) is preserved as record_id (L1)."""
        eid = str(uuid.uuid4())
        result = RCoreToLayer1Adapter().adapt(make_record(event_id=eid))
        assert result["record_id"] == eid

    def test_001d_function_id_maps_to_function_name(self):
        """function_id (L0) maps to function_name (L1) with name preserved."""
        result = RCoreToLayer1Adapter().adapt(make_record(function_id="my_handler_function"))
        assert result["function_name"] == "my_handler_function"

    def test_001e_function_name_pattern_sanitisation(self):
        """function_name with illegal characters is sanitised to L1 pattern."""
        import re
        result = RCoreToLayer1Adapter().adapt(make_record(function_id="my function/with spaces\!"))
        assert re.match(r"^[a-zA-Z0-9_\-\.]+$", result["function_name"]), (
            f"Sanitised function_name '{result['function_name']}' still contains illegal characters"
        )

    def test_001f_non_uuid_event_id_generates_valid_uuid(self):
        """If event_id is not UUID format, a new valid UUID is generated."""
        result = RCoreToLayer1Adapter().adapt(make_record(event_id="not-a-uuid-value"))
        try:
            uuid.UUID(result["record_id"])
        except ValueError:
            pytest.fail(f"Generated record_id '{result['record_id']}' is not valid UUID")

    def test_001g_all_anomaly_types_map_to_valid_l1_categories(self):
        """Every AnomalyType in r-core maps to a valid L1 v2.1 category."""
        adapter = RCoreToLayer1Adapter()
        allowed = {"benign", "suspicious", "malicious", "unknown"}
        failures = []
        for anomaly_type in AnomalyType:
            result = adapter.adapt(make_record(anomaly_type=anomaly_type))
            if result["anomaly_type"] not in allowed:
                failures.append(f"AnomalyType.{anomaly_type.name} -> '{result['anomaly_type']}'")
        assert not failures, "Invalid anomaly_type mappings:\n" + "\n".join(failures)

    def test_001h_benign_maps_to_benign(self):
        """BENIGN maps strictly to 'benign'."""
        result = RCoreToLayer1Adapter().adapt(make_record(anomaly_type=AnomalyType.BENIGN))
        assert result["anomaly_type"] == "benign"

    def test_001i_security_anomalies_map_to_malicious(self):
        """Security-class anomaly types map to 'malicious'."""
        adapter = RCoreToLayer1Adapter()
        for anomaly_type in [AnomalyType.ADVERSARIAL_INJECTION, AnomalyType.BILLING_ABUSE,
                              AnomalyType.DOS_AMPLIFICATION, AnomalyType.DATA_EXFILTRATION,
                              AnomalyType.PRIVILEGE_ESCALATION, AnomalyType.CRYPTOMINING]:
            result = adapter.adapt(make_record(anomaly_type=anomaly_type))
            assert result["anomaly_type"] == "malicious", (
                f"Expected 'malicious' for {anomaly_type.name}, got '{result['anomaly_type']}'"
            )

    def test_001j_original_anomaly_type_preserved_in_metadata(self):
        """Original L0 anomaly type string is always preserved in context_metadata."""
        result = RCoreToLayer1Adapter().adapt(make_record(anomaly_type=AnomalyType.DATA_EXFILTRATION))
        assert result["context_metadata"]["original_anomaly_type"] == "data_exfiltration"
        assert result["context_metadata"]["anomaly_normalised_to"] == "malicious"

    def test_001k_all_execution_phases_map_to_valid_l1_phases(self):
        """Every ExecutionPhase in r-core maps to a valid L1 v2.1 phase."""
        adapter = RCoreToLayer1Adapter()
        allowed = {"initialization", "execution", "completion", "error", "timeout"}
        failures = []
        for phase in ExecutionPhase:
            result = adapter.adapt(make_record(execution_phase=phase))
            if result["execution_phase"] not in allowed:
                failures.append(f"ExecutionPhase.{phase.name} -> '{result['execution_phase']}'")
        assert not failures, "Invalid execution_phase mappings:\n" + "\n".join(failures)

    def test_001l_invoke_maps_to_execution(self):
        """ExecutionPhase.INVOKE maps to 'execution'."""
        result = RCoreToLayer1Adapter().adapt(make_record(execution_phase=ExecutionPhase.INVOKE))
        assert result["execution_phase"] == "execution"

    def test_001m_init_maps_to_initialization(self):
        """ExecutionPhase.INIT maps to 'initialization'."""
        result = RCoreToLayer1Adapter().adapt(make_record(execution_phase=ExecutionPhase.INIT))
        assert result["execution_phase"] == "initialization"

    def test_001n_shutdown_maps_to_completion(self):
        """ExecutionPhase.SHUTDOWN maps to 'completion'."""
        result = RCoreToLayer1Adapter().adapt(make_record(execution_phase=ExecutionPhase.SHUTDOWN))
        assert result["execution_phase"] == "completion"

    def test_001o_risk_scores_preserved_in_context_metadata(self):
        """Adversarial, economic, and silent failure scores survive the adaptation."""
        record = make_record(adversarial_score=0.85, economic_risk_score=0.42,
                             silent_failure_probability=0.12, confidence_level=0.95)
        meta = RCoreToLayer1Adapter().adapt(record)["context_metadata"]
        assert meta["adversarial_score"] == 0.85
        assert meta["economic_risk_score"] == 0.42
        assert meta["silent_failure_probability"] == 0.12
        assert meta["confidence_level"] == 0.95

    def test_001p_execution_metrics_in_telemetry_data(self):
        """Duration, memory, CPU, and network metrics are in telemetry_data."""
        record = make_record(duration=1.23, memory_spike_kb=2048,
                             cpu_utilization=78.5, network_io_bytes=4096)
        td = RCoreToLayer1Adapter().adapt(record)["telemetry_data"]
        assert td["l0_duration_ms"] == 1.23
        assert td["l0_memory_spike_kb"] == 2048
        assert td["l0_cpu_utilization"] == 78.5
        assert td["l0_network_io_bytes"] == 4096

    def test_001q_layer0_metrics_block_present(self):
        """telemetry_data contains a 'layer0_metrics' sub-dict with adapter info."""
        result = RCoreToLayer1Adapter().adapt(make_record())
        assert "layer0_metrics" in result["telemetry_data"]
        lm = result["telemetry_data"]["layer0_metrics"]
        assert lm["l0_adapter_version"] == "2.0.1"
        assert "l0_original_anomaly_type" in lm
        assert "l0_original_execution_phase" in lm
        assert "l0_schema_version" in lm

    def test_001r_provenance_chain_populated(self):
        """provenance_chain contains source_layer and schema_migration fields."""
        result = RCoreToLayer1Adapter().adapt(make_record())
        pc = result["provenance_chain"]
        assert pc["source_layer"] == "layer_0"
        assert pc["schema_migration"] == "r_core_v4.2_to_layer1_v2.1"
        assert pc["adapter_version"] == "2.0.1"

    def test_001s_validation_gate_accepts_adapted_record(self):
        """Core integration test: adapted record passes InputValidationGateway."""
        record = make_record()
        adapted = RCoreToLayer1Adapter().adapt(record)
        gateway = InputValidationGateway(make_gateway_config())
        result = run_async(gateway.validate_telemetry_record(adapted))
        assert result.is_valid, (
            f"Validation FAILED.\nStatus: {result.status}\nErrors: {result.errors}"
        )

    def test_001t_validation_gate_accepts_all_anomaly_types(self):
        """Validation gate accepts adapted records for all 21 L0 anomaly types."""
        adapter = RCoreToLayer1Adapter()
        gateway = InputValidationGateway(make_gateway_config())
        failures = []
        for anomaly_type in AnomalyType:
            record = make_record(anomaly_type=anomaly_type)
            adapted = adapter.adapt(record)
            result = run_async(gateway.validate_telemetry_record(adapted))
            if not result.is_valid:
                failures.append(
                    f"AnomalyType.{anomaly_type.name}: status={result.status}, errors={result.errors}"
                )
        assert not failures, f"Validation failed for {len(failures)} anomaly types:\n" + "\n".join(failures)

    def test_001u_validation_gate_accepts_all_execution_phases(self):
        """Validation gate accepts adapted records for all 5 L0 execution phases."""
        adapter = RCoreToLayer1Adapter()
        gateway = InputValidationGateway(make_gateway_config())
        failures = []
        for phase in ExecutionPhase:
            record = make_record(execution_phase=phase)
            adapted = adapter.adapt(record)
            result = run_async(gateway.validate_telemetry_record(adapted))
            if not result.is_valid:
                failures.append(
                    f"ExecutionPhase.{phase.name}: status={result.status}, errors={result.errors}"
                )
        assert not failures, f"Validation failed for {len(failures)} execution phases:\n" + "\n".join(failures)

    def test_001v_adapter_raises_on_none_input(self):
        """Adapter raises ValueError if None is passed."""
        with pytest.raises(ValueError, match="must not be None"):
            RCoreToLayer1Adapter().adapt(None)

    def test_001w_adapter_raises_on_wrong_type(self):
        """Adapter raises TypeError if a non-TelemetryRecord is passed."""
        with pytest.raises(TypeError, match="Expected TelemetryRecord"):
            RCoreToLayer1Adapter().adapt({"event_id": "fake"})

    def test_001x_fallback_mode_true_preserved(self):
        """fallback_mode=True is correctly preserved in telemetry_data."""
        result = RCoreToLayer1Adapter().adapt(make_record(fallback_mode=True))
        assert result["telemetry_data"]["l0_fallback_mode"] is True

    def test_001y_optional_fields_with_none_values_do_not_crash(self):
        """Optional L0 fields being None does not cause the adapter or validation gate to raise."""
        record = make_record(
            container_id=None, region=None, runtime_version=None,
            trigger_type=None, provenance_id=None, graph_node_id=None,
        )
        adapted = RCoreToLayer1Adapter().adapt(record)
        gateway = InputValidationGateway(make_gateway_config())
        result = run_async(gateway.validate_telemetry_record(adapted))
        assert result.is_valid, f"Validation failed with None optional fields: {result.errors}"
