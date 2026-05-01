"""
SCAFAD Layer 0 — Detector: statistical_outlier
Algorithm 1: Algorithm 1: Statistical outlier detection using z-score

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
    """Algorithm 1: Statistical outlier detection using z-score"""
    
    if len(historical_data) < 10:
        return DetectionResult(
            algorithm_name="statistical_outlier",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient historical data",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Extract numerical features
    current_features = {
        'duration': telemetry.duration,
        'memory': telemetry.memory_spike_kb,
        'cpu': telemetry.cpu_utilization,
        'network': telemetry.network_io_bytes
    }
    
    historical_features = defaultdict(list)
    for hist_telemetry in list(historical_data)[:-1]:  # Exclude current
        historical_features['duration'].append(hist_telemetry.duration)
        historical_features['memory'].append(hist_telemetry.memory_spike_kb)
        historical_features['cpu'].append(hist_telemetry.cpu_utilization)
        historical_features['network'].append(hist_telemetry.network_io_bytes)
    
    # Calculate z-scores
    z_scores = {}
    anomaly_scores = {}
    
    for feature, current_value in current_features.items():
        if len(historical_features[feature]) > 0:
            mean_val = np.mean(historical_features[feature])
            std_val = np.std(historical_features[feature])
            
            if std_val > 0:
                z_score = abs((current_value - mean_val) / std_val)
                z_scores[feature] = z_score
                anomaly_scores[feature] = min(z_score / config.statistical_threshold, 1.0)
    
    # Determine overall anomaly
    max_z_score = max(z_scores.values()) if z_scores else 0
    anomaly_detected = max_z_score > config.statistical_threshold
    confidence = min(max_z_score / (config.statistical_threshold * 2), 1.0)
    
    # Determine anomaly type based on dominant feature
    anomaly_type = AnomalyType.BENIGN
    if anomaly_detected:
        dominant_feature = max(z_scores.items(), key=lambda x: x[1])[0]
        if dominant_feature == 'duration':
            anomaly_type = AnomalyType.TIMEOUT_FALLBACK
        elif dominant_feature == 'memory':
            anomaly_type = AnomalyType.MEMORY_SPIKE
        elif dominant_feature == 'cpu':
            anomaly_type = AnomalyType.CPU_BURST
        elif dominant_feature == 'network':
            anomaly_type = AnomalyType.NETWORK_ANOMALY
    
    return DetectionResult(
        algorithm_name="statistical_outlier",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=anomaly_type,
        severity=confidence,
        explanation=f"Z-score analysis: max z-score {max_z_score:.2f} (threshold: {config.statistical_threshold})",
        contributing_features=z_scores,
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('statistical_outlier', 0.038462, detect)
