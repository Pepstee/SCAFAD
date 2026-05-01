"""
SCAFAD Layer 0 — Detector: cascade_failure
Algorithm 22: Algorithm 22: Cascade failure detection

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
    """Algorithm 22: Cascade failure detection"""
    
    if len(historical_data) < 10:
        return DetectionResult(
            algorithm_name="cascade_failure",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for cascade failure analysis",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Analyze failure propagation patterns
    current_time = telemetry.timestamp
    cascade_window = 300  # 5 minutes
    
    # Find recent failures
    recent_failures = [
        t for t in historical_data
        if (current_time - t.timestamp <= cascade_window and
            (t.execution_phase == ExecutionPhase.ERROR or
             t.anomaly_type in [AnomalyType.EXECUTION_FAILURE, AnomalyType.TIMEOUT_FALLBACK] or
             t.duration > 30.0))
    ]
    
    failure_count = len(recent_failures)
    
    if failure_count == 0:
        return DetectionResult(
            algorithm_name="cascade_failure",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="No recent failures detected",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Analyze failure timeline for cascade patterns
    failure_times = sorted([t.timestamp for t in recent_failures])
    
    # Calculate time intervals between failures
    intervals = []
    for i in range(1, len(failure_times)):
        intervals.append(failure_times[i] - failure_times[i-1])
    
    # Cascade indicators
    rapid_succession_threshold = 30  # 30 seconds
    rapid_failures = sum(1 for interval in intervals if interval < rapid_succession_threshold)
    
    # Escalating resource usage pattern
    failure_durations = [t.duration for t in recent_failures]
    duration_trend = 0.0
    if len(failure_durations) > 2:
        # Simple trend calculation
        n = len(failure_durations)
        x_vals = list(range(n))
        sum_x = sum(x_vals)
        sum_y = sum(failure_durations)
        sum_xy = sum(x * y for x, y in zip(x_vals, failure_durations))
        sum_x2 = sum(x * x for x in x_vals)
        
        if n * sum_x2 - sum_x * sum_x != 0:
            duration_trend = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
    
    # Cascade scoring
    failure_frequency_score = min(failure_count / 5.0, 1.5)
    rapid_succession_score = min(rapid_failures / 3.0, 1.0)
    escalation_score = min(abs(duration_trend) / 5.0, 0.8) if duration_trend > 0 else 0.0
    
    cascade_score = (failure_frequency_score * 0.4 + 
                    rapid_succession_score * 0.4 + 
                    escalation_score * 0.2)
    
    anomaly_detected = cascade_score > 0.6
    confidence = min(cascade_score, 1.0)
    
    return DetectionResult(
        algorithm_name="cascade_failure",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.EXECUTION_FAILURE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Cascade analysis: {failure_count} failures in {cascade_window}s, {rapid_failures} rapid succession",
        contributing_features={
            'failure_count': failure_count,
            'rapid_failures': rapid_failures,
            'duration_trend': duration_trend,
            'cascade_score': cascade_score
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('cascade_failure', 0.038462, detect)
