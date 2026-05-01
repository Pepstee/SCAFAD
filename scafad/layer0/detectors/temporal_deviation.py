"""
SCAFAD Layer 0 — Detector: temporal_deviation
Algorithm 3: Algorithm 3: Temporal pattern deviation detection

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
    """Algorithm 3: Temporal pattern deviation detection"""
    
    if len(historical_data) < 20:
        return DetectionResult(
            algorithm_name="temporal_deviation",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient temporal data",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Analyze temporal patterns in the last hour
    current_time = telemetry.timestamp
    recent_data = [
        t for t in historical_data 
        if current_time - t.timestamp < 3600  # Last hour
    ]
    
    if len(recent_data) < 10:
        return DetectionResult(
            algorithm_name="temporal_deviation",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient recent temporal data",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Calculate recent vs historical averages
    recent_durations = [t.duration for t in recent_data]
    historical_durations = [t.duration for t in historical_data if t not in recent_data]
    
    if not historical_durations:
        return DetectionResult(
            algorithm_name="temporal_deviation",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="No historical baseline",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    recent_avg = np.mean(recent_durations)
    historical_avg = np.mean(historical_durations)
    historical_std = np.std(historical_durations)
    
    # Detect significant deviation
    if historical_std > 0:
        deviation_score = abs(recent_avg - historical_avg) / historical_std
        anomaly_detected = deviation_score > 2.0
        confidence = min(deviation_score / 4.0, 1.0)
    else:
        deviation_score = 0
        anomaly_detected = False
        confidence = 0.0
    
    return DetectionResult(
        algorithm_name="temporal_deviation",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.TIMEOUT_FALLBACK if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Temporal deviation: recent avg {recent_avg:.3f}s vs historical {historical_avg:.3f}s (score: {deviation_score:.2f})",
        contributing_features={
            'recent_avg': recent_avg,
            'historical_avg': historical_avg,
            'deviation_score': deviation_score
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('temporal_deviation', 0.038462, detect)
