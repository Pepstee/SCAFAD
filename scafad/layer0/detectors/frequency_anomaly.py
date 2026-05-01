"""
SCAFAD Layer 0 — Detector: frequency_anomaly
Algorithm 7: Algorithm 7: Invocation frequency anomaly detection

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
    """Algorithm 7: Invocation frequency anomaly detection"""
    
    # Analyze invocation frequency in the last 5 minutes
    current_time = telemetry.timestamp
    window_start = current_time - 300  # 5 minutes
    
    recent_invocations = [
        t for t in historical_data
        if t.timestamp >= window_start
    ]
    
    current_frequency = len(recent_invocations) / 5.0  # Invocations per minute
    
    # Compare to historical frequency patterns
    if len(historical_data) < 100:
        return DetectionResult(
            algorithm_name="frequency_anomaly",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for frequency analysis",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Calculate historical frequency windows
    historical_frequencies = []
    for i in range(20, len(historical_data), 10):  # Sample every 10 records
        window_end = historical_data[i].timestamp
        window_start_hist = window_end - 300
        window_data = [
            t for t in list(historical_data)[:i]
            if t.timestamp >= window_start_hist
        ]
        if len(window_data) > 0:
            historical_frequencies.append(len(window_data) / 5.0)
    
    if not historical_frequencies:
        return DetectionResult(
            algorithm_name="frequency_anomaly",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="No historical frequency baseline",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    mean_freq = np.mean(historical_frequencies)
    std_freq = np.std(historical_frequencies)
    
    if std_freq > 0:
        freq_z_score = abs(current_frequency - mean_freq) / std_freq
        anomaly_detected = freq_z_score > 2.0
        confidence = min(freq_z_score / 4.0, 1.0)
    else:
        freq_z_score = 0.0
        anomaly_detected = False
        confidence = 0.0
    
    # Determine anomaly type based on frequency change
    anomaly_type = AnomalyType.BENIGN
    if anomaly_detected:
        if current_frequency > mean_freq * 2:
            anomaly_type = AnomalyType.ECONOMIC_ABUSE  # High frequency abuse
        else:
            anomaly_type = AnomalyType.EXECUTION_FAILURE  # Unusual pattern
    
    return DetectionResult(
        algorithm_name="frequency_anomaly",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=anomaly_type,
        severity=confidence,
        explanation=f"Frequency analysis: {current_frequency:.2f} inv/min vs {mean_freq:.2f} baseline (z-score: {freq_z_score:.2f})",
        contributing_features={
            'current_frequency': current_frequency,
            'mean_frequency': mean_freq,
            'freq_z_score': freq_z_score
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('frequency_anomaly', 0.038462, detect)
