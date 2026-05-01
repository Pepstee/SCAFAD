"""
layer0 — SCAFAD Adaptive Telemetry Controller
==============================================

Layer 0 is the capture layer. It:
  - Produces TelemetryRecord v4.2 from Lambda invocation events
  - Runs 26 anomaly detectors over raw telemetry
  - Signs and provisions records for downstream layers
  - Adapts its output to the Layer 1 intake contract via adapter.py

Public API
----------
  TelemetryRecord           — core telemetry dataclass
  AnomalyType               — enumeration of 21 anomaly classes
  ExecutionPhase            — enumeration of execution phases
  TelemetrySource           — enumeration of telemetry sources
  Layer0Config              — runtime configuration dataclass
  RCoreToLayer1Adapter      — sole authorised L0 → L1 translation point
  Layer0_AdaptiveTelemetryController — top-level orchestrator
"""

from .app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource
from .app_config import Layer0Config
from .adapter import RCoreToLayer1Adapter

try:
    from .app_main import Layer0_AdaptiveTelemetryController
except Exception:  # noqa: BLE001 — optional heavy dep (sklearn etc.)
    Layer0_AdaptiveTelemetryController = None  # type: ignore[assignment,misc]

__all__ = [
    "TelemetryRecord",
    "AnomalyType",
    "ExecutionPhase",
    "TelemetrySource",
    "Layer0Config",
    "RCoreToLayer1Adapter",
    "Layer0_AdaptiveTelemetryController",
]
