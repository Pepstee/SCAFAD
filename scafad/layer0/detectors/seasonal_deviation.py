"""
SCAFAD Layer 0 — Detector: seasonal_deviation
Algorithm 5: Algorithm 5: Seasonal pattern deviation detection

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
    """Algorithm 5: Seasonal pattern deviation detection"""
    
    # Simplified seasonal detection - look for hour-of-day patterns
    current_hour = time.gmtime(telemetry.timestamp).tm_hour
    
    # Group historical data by hour
    hourly_data = defaultdict(list)
    for hist in historical_data:
        hist_hour = time.gmtime(hist.timestamp).tm_hour
        hourly_data[hist_hour].append(hist.duration)
    
    if current_hour not in hourly_data or len(hourly_data[current_hour]) < 5:
        return DetectionResult(
            algorithm_name="seasonal_deviation",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation=f"Insufficient seasonal data for hour {current_hour}",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Compare current duration to same hour historically
    same_hour_durations = hourly_data[current_hour]
    mean_duration = np.mean(same_hour_durations)
    std_duration = np.std(same_hour_durations)
    
    if std_duration > 0:
        seasonal_z_score = abs(telemetry.duration - mean_duration) / std_duration
        anomaly_detected = seasonal_z_score > 2.5
        confidence = min(seasonal_z_score / 5.0, 1.0)
    else:
        seasonal_z_score = 0.0
        anomaly_detected = False
        confidence = 0.0
    
    return DetectionResult(
        algorithm_name="seasonal_deviation",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.TIMEOUT_FALLBACK if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Seasonal analysis for hour {current_hour}: z-score {seasonal_z_score:.2f}",
        contributing_features={
            'hour': current_hour,
            'seasonal_z_score': seasonal_z_score,
            'expected_duration': mean_duration
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('seasonal_deviation', 0.038462, detect)
