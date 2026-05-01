"""
SCAFAD Layer 0 — Detector: resource_spike
Algorithm 9: Algorithm 9: General resource spike detection

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
    """Algorithm 9: General resource spike detection"""
    
    # Define resource spike thresholds
    thresholds = {
        'memory': 100 * 1024,  # 100MB
        'cpu': 80.0,           # 80%
        'network': 10 * 1024 * 1024,  # 10MB
    }
    
    current_resources = {
        'memory': telemetry.memory_spike_kb,
        'cpu': telemetry.cpu_utilization,
        'network': telemetry.network_io_bytes,
    }
    
    spike_scores = {}
    for resource, value in current_resources.items():
        threshold = thresholds[resource]
        if value > threshold:
            spike_scores[resource] = min(value / threshold, 3.0) - 1.0
        else:
            spike_scores[resource] = 0.0
    
    max_spike = max(spike_scores.values()) if spike_scores else 0.0
    anomaly_detected = max_spike > 0.5
    confidence = min(max_spike / 2.0, 1.0)
    
    # Determine primary resource spike type
    if anomaly_detected:
        primary_resource = max(spike_scores.items(), key=lambda x: x[1])[0]
        if primary_resource == 'memory':
            anomaly_type = AnomalyType.MEMORY_SPIKE
        elif primary_resource == 'cpu':
            anomaly_type = AnomalyType.CPU_BURST
        else:
            anomaly_type = AnomalyType.NETWORK_ANOMALY
    else:
        anomaly_type = AnomalyType.BENIGN
    
    return DetectionResult(
        algorithm_name="resource_spike",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=anomaly_type,
        severity=confidence,
        explanation=f"Resource spike analysis: max spike {max_spike:.2f}",
        contributing_features=spike_scores,
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('resource_spike', 0.038462, detect)
