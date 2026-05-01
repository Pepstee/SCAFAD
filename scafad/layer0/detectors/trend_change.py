"""
SCAFAD Layer 0 — Detector: trend_change
Algorithm 6: Algorithm 6: Trend change detection

WP-3.7: Extracted from layer0_core.py monolith.
Part of the DetectorRegistry decomposition (C-1 layered contract architecture).
"""
from __future__ import annotations

import math
import time
import logging
from collections import defaultdict, deque
from typing import Any, Dict, List

import numpy as np

from layer0.layer0_core import (
    DetectionResult,
    DetectionConfig,
    AnomalyType,
    ExecutionPhase,
    HAS_SKLEARN,
)
from layer0.app_telemetry import TelemetryRecord
from layer0.detectors.registry import REGISTRY

logger = logging.getLogger(__name__)

def detect(
    telemetry: TelemetryRecord,
    historical_data: deque,
    ml_models: dict,
    config: DetectionConfig,
) -> DetectionResult:
    """Algorithm 6: Trend change detection"""
    
    if len(historical_data) < 20:
        return DetectionResult(
            algorithm_name="trend_change",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for trend analysis",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Get recent duration trend
    recent_durations = [t.duration for t in list(historical_data)[-20:]]
    
    # Calculate simple trend using linear regression slope approximation
    n = len(recent_durations)
    x_values = list(range(n))
    
    # Simple slope calculation
    sum_x = sum(x_values)
    sum_y = sum(recent_durations)
    sum_xy = sum(x * y for x, y in zip(x_values, recent_durations))
    sum_x2 = sum(x * x for x in x_values)
    
    if n * sum_x2 - sum_x * sum_x != 0:
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
    else:
        slope = 0.0
    
    # Detect significant trend changes
    abs_slope = abs(slope)
    trend_threshold = 0.01  # Adjust based on typical duration ranges
    
    anomaly_detected = abs_slope > trend_threshold
    confidence = min(abs_slope / (trend_threshold * 2), 1.0)
    
    trend_direction = "increasing" if slope > 0 else "decreasing"
    
    return DetectionResult(
        algorithm_name="trend_change",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.TIMEOUT_FALLBACK if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Trend analysis: {trend_direction} trend with slope {slope:.4f}",
        contributing_features={
            'slope': slope,
            'trend_direction': trend_direction,
            'abs_slope': abs_slope
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('trend_change', 0.038462, detect)
