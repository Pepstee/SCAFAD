"""Alias module: re-exports TelemetryRecord and related types from app_telemetry.

Exists so that ``from layer0.telemetry import TelemetryRecord`` works for
runtime/ and any external consumer that uses the shorter module name.
"""

from .app_telemetry import (  # noqa: F401
    TelemetryRecord,
    AnomalyType,
    ExecutionPhase,
    TelemetrySource,
)

__all__ = ["TelemetryRecord", "AnomalyType", "ExecutionPhase", "TelemetrySource"]
