"""
SCAFAD Layer 0 — Detector: error_clustering
Algorithm 18: Algorithm 18: Error clustering detection

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
    """Algorithm 18: Error clustering detection"""
    
    if len(historical_data) < 10:
        return DetectionResult(
            algorithm_name="error_clustering",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for error clustering analysis",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Analyze recent error patterns
    current_time = telemetry.timestamp
    recent_window = 600  # 10 minutes
    
    recent_data = [
        t for t in historical_data
        if current_time - t.timestamp <= recent_window
    ]
    
    if len(recent_data) < 5:
        return DetectionResult(
            algorithm_name="error_clustering",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient recent data for error clustering",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Count error-like patterns in recent data
    error_indicators = 0
    total_recent = len(recent_data)
    
    for t in recent_data:
        # Error indicators
        if (t.execution_phase == ExecutionPhase.ERROR or 
            t.anomaly_type in [AnomalyType.EXECUTION_FAILURE, AnomalyType.TIMEOUT_FALLBACK] or
            t.duration > 30.0):  # Long duration as error proxy
            error_indicators += 1
    
    error_rate = error_indicators / total_recent
    
    # Historical error rate for comparison
    historical_errors = sum(1 for t in historical_data 
                           if t.execution_phase == ExecutionPhase.ERROR or 
                              t.anomaly_type in [AnomalyType.EXECUTION_FAILURE, AnomalyType.TIMEOUT_FALLBACK])
    
    historical_error_rate = historical_errors / len(historical_data)
    
    # Error clustering score
    if historical_error_rate > 0:
        error_rate_ratio = error_rate / historical_error_rate
    else:
        error_rate_ratio = error_rate * 10  # High penalty for first errors
    
    clustering_score = min(error_rate_ratio, 3.0) / 3.0 if error_rate > 0.1 else 0.0
    anomaly_detected = clustering_score > 0.3
    confidence = clustering_score
    
    return DetectionResult(
        algorithm_name="error_clustering",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.EXECUTION_FAILURE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Error clustering: {error_rate:.2%} recent error rate vs {historical_error_rate:.2%} baseline",
        contributing_features={
            'recent_error_rate': error_rate,
            'historical_error_rate': historical_error_rate,
            'error_rate_ratio': error_rate_ratio,
            'recent_errors': error_indicators,
            'recent_total': total_recent
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('error_clustering', 0.038462, detect)
