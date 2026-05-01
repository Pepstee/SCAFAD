"""
SCAFAD Layer 0 — Detector: timeout_pattern
Algorithm 17: Algorithm 17: Timeout pattern detection

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
    """Algorithm 17: Timeout pattern detection"""
    
    # Timeout indicators
    duration = telemetry.duration
    execution_phase = telemetry.execution_phase
    
    # Common Lambda timeout thresholds
    timeout_thresholds = [15, 30, 60, 120, 300, 900]  # Common timeout values in seconds
    timeout_warning_ratio = 0.9  # 90% of timeout threshold
    
    # Find likely timeout threshold based on duration
    likely_timeout = None
    for threshold in timeout_thresholds:
        if duration > threshold * timeout_warning_ratio:
            likely_timeout = threshold
            break
    
    if likely_timeout is None:
        # Check for custom timeout patterns in historical data
        if len(historical_data) > 20:
            max_duration = max(t.duration for t in historical_data)
            if duration > max_duration * 0.95:  # Close to historical maximum
                likely_timeout = max_duration * 1.1
    
    # Timeout scoring
    if likely_timeout:
        timeout_proximity = duration / likely_timeout
        timeout_score = max(0, timeout_proximity - timeout_warning_ratio) / (1 - timeout_warning_ratio)
    else:
        timeout_score = 0.0
    
    # Check for error phase indicating timeout
    error_phase_score = 1.0 if execution_phase == ExecutionPhase.ERROR else 0.0
    
    # Combined timeout pattern score
    combined_timeout_score = max(timeout_score, error_phase_score * 0.7)
    anomaly_detected = combined_timeout_score > 0.3
    confidence = min(combined_timeout_score, 1.0)
    
    return DetectionResult(
        algorithm_name="timeout_pattern",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.TIMEOUT_FALLBACK if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Timeout analysis: {duration:.3f}s duration, likely timeout {likely_timeout}s",
        contributing_features={
            'duration': duration,
            'likely_timeout': likely_timeout,
            'timeout_proximity': duration / likely_timeout if likely_timeout else 0,
            'timeout_score': timeout_score,
            'error_phase_score': error_phase_score
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('timeout_pattern', 0.038462, detect)
