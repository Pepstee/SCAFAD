"""
SCAFAD Layer 0 — Detector: isolation_forest
Algorithm 2: Algorithm 2: Isolation Forest anomaly detection

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

# Fallback import: isolation_forest delegates to statistical_outlier when
# sklearn is unavailable or insufficient historical data exists.
from layer0.detectors.statistical_outlier import detect as _fallback_statistical

def detect(
    telemetry: TelemetryRecord,
    historical_data: deque,
    ml_models: dict,
    config: DetectionConfig,
) -> DetectionResult:
    """Algorithm 2: Isolation Forest anomaly detection"""
    
    if not HAS_SKLEARN or len(historical_data) < 50:
        # Fallback to simple statistical method
        return _fallback_statistical(telemetry, historical_data, ml_models, config)
    
    try:
        # Prepare feature matrix
        features = []
        for hist_telemetry in historical_data:
            features.append([
                hist_telemetry.duration,
                hist_telemetry.memory_spike_kb,
                hist_telemetry.cpu_utilization,
                hist_telemetry.network_io_bytes
            ])
        
        # Train isolation forest
        iso_forest = ml_models['isolation_forest']
        iso_forest.fit(features)
        
        # Score current telemetry
        current_features = [[
            telemetry.duration,
            telemetry.memory_spike_kb,
            telemetry.cpu_utilization,
            telemetry.network_io_bytes
        ]]
        
        anomaly_score = iso_forest.decision_function(current_features)[0]
        is_outlier = iso_forest.predict(current_features)[0] == -1
        
        # Convert to confidence score
        confidence = abs(anomaly_score)
        anomaly_detected = is_outlier and confidence > config.isolation_threshold
        
        return DetectionResult(
            algorithm_name="isolation_forest",
            anomaly_detected=anomaly_detected,
            confidence_score=confidence,
            anomaly_type=AnomalyType.EXECUTION_FAILURE if anomaly_detected else AnomalyType.BENIGN,
            severity=confidence,
            explanation=f"Isolation Forest: score {anomaly_score:.3f}, outlier: {is_outlier}",
            contributing_features={'isolation_score': anomaly_score},
            processing_time_ms=0.0
        )
        
    except Exception as e:
        logger.error(f"Isolation Forest failed: {e}")
        return _fallback_statistical(telemetry, historical_data, ml_models, config)


# Register with DetectorRegistry at import time
REGISTRY.register('isolation_forest', 0.038462, detect)
