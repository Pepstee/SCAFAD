"""
SCAFAD Layer 0 — Detector: duration_outlier
Algorithm 8: Algorithm 8: Duration outlier detection with percentile analysis

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
    """Algorithm 8: Duration outlier detection with percentile analysis"""
    
    if len(historical_data) < 20:
        return DetectionResult(
            algorithm_name="duration_outlier",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for duration analysis",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Get duration distribution
    durations = [t.duration for t in historical_data]
    
    # Calculate percentiles
    p95 = np.percentile(durations, 95)
    p99 = np.percentile(durations, 99)
    p1 = np.percentile(durations, 1)
    p5 = np.percentile(durations, 5)
    median = np.percentile(durations, 50)
    
    current_duration = telemetry.duration
    
    # Determine outlier status
    is_high_outlier = current_duration > p99
    is_moderate_high_outlier = current_duration > p95
    is_low_outlier = current_duration < p1
    is_moderate_low_outlier = current_duration < p5
    
    # Calculate confidence based on how extreme the outlier is
    if is_high_outlier:
        confidence = min((current_duration - p99) / (p99 - median + 0.001), 1.0)
        anomaly_type = AnomalyType.TIMEOUT_FALLBACK
    elif is_low_outlier:
        confidence = min((p1 - current_duration) / (median - p1 + 0.001), 1.0)
        anomaly_type = AnomalyType.EXECUTION_FAILURE
    elif is_moderate_high_outlier:
        confidence = min((current_duration - p95) / (p99 - p95 + 0.001), 0.7)
        anomaly_type = AnomalyType.CPU_BURST
    elif is_moderate_low_outlier:
        confidence = min((p5 - current_duration) / (p5 - p1 + 0.001), 0.5)
        anomaly_type = AnomalyType.COLD_START
    else:
        confidence = 0.0
        anomaly_type = AnomalyType.BENIGN
    
    anomaly_detected = confidence > 0.3
    
    return DetectionResult(
        algorithm_name="duration_outlier",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=anomaly_type,
        severity=confidence,
        explanation=f"Duration {current_duration:.3f}s vs percentiles [P1:{p1:.3f}, P5:{p5:.3f}, P50:{median:.3f}, P95:{p95:.3f}, P99:{p99:.3f}]",
        contributing_features={
            'duration': current_duration,
            'p1': p1, 'p5': p5, 'p50': median, 'p95': p95, 'p99': p99,
            'is_high_outlier': is_high_outlier,
            'is_low_outlier': is_low_outlier
        },
        processing_time_ms=0.0
    )

# Resource-Based Detection Algorithms (6)


# Register with DetectorRegistry at import time
REGISTRY.register('duration_outlier', 0.038462, detect)
