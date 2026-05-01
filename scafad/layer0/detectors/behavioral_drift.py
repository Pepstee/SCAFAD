"""
SCAFAD Layer 0 — Detector: behavioral_drift
Algorithm 21: Algorithm 21: Behavioral drift detection

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
    """Algorithm 21: Behavioral drift detection"""
    
    if len(historical_data) < 50:
        return DetectionResult(
            algorithm_name="behavioral_drift",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for behavioral drift analysis",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Compare recent behavior to historical baseline
    recent_window = min(20, len(historical_data) // 4)
    baseline_window = min(30, len(historical_data) // 2)
    
    recent_data = list(historical_data)[-recent_window:]
    baseline_data = list(historical_data)[:baseline_window]
    
    # Calculate behavioral features
    def calculate_behavior_features(data):
        return {
            'avg_duration': np.mean([t.duration for t in data]),
            'avg_memory': np.mean([t.memory_spike_kb for t in data]),
            'avg_cpu': np.mean([t.cpu_utilization for t in data]),
            'avg_network': np.mean([t.network_io_bytes for t in data]),
            'duration_variance': np.std([t.duration for t in data]),
            'phase_distribution': len(set(t.execution_phase for t in data))
        }
    
    recent_features = calculate_behavior_features(recent_data)
    baseline_features = calculate_behavior_features(baseline_data)
    
    # Calculate drift scores for each feature
    drift_scores = {}
    for feature in recent_features.keys():
        recent_val = recent_features[feature]
        baseline_val = baseline_features[feature]
        
        if baseline_val > 0:
            drift_ratio = abs(recent_val - baseline_val) / baseline_val
            drift_scores[feature] = min(drift_ratio, 2.0)
        else:
            drift_scores[feature] = 1.0 if recent_val > 0 else 0.0
    
    # Overall behavioral drift score
    avg_drift = np.mean(list(drift_scores.values()))
    max_drift = max(drift_scores.values())
    
    behavioral_drift_score = (avg_drift * 0.6 + max_drift * 0.4)
    anomaly_detected = behavioral_drift_score > 0.3
    confidence = min(behavioral_drift_score, 1.0)
    
    return DetectionResult(
        algorithm_name="behavioral_drift",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.EXECUTION_FAILURE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Behavioral drift analysis: avg drift {avg_drift:.2f}, max drift {max_drift:.2f}",
        contributing_features=drift_scores,
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('behavioral_drift', 0.038462, detect)
