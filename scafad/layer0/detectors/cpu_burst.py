"""
SCAFAD Layer 0 — Detector: cpu_burst
Algorithm 11: Algorithm 11: CPU burst detection

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
    """Algorithm 11: CPU burst detection"""
    
    cpu_threshold = 75.0  # High CPU threshold
    current_cpu = telemetry.cpu_utilization
    
    # Get recent CPU utilization for context
    if len(historical_data) >= 5:
        recent_cpu = [t.cpu_utilization for t in list(historical_data)[-5:]]
        avg_recent_cpu = np.mean(recent_cpu)
        cpu_spike_ratio = current_cpu / (avg_recent_cpu + 1)
    else:
        cpu_spike_ratio = 1.0
    
    # CPU burst scoring
    threshold_score = max(0, current_cpu - cpu_threshold) / (100 - cpu_threshold)
    spike_score = min(cpu_spike_ratio - 1.0, 2.0) / 2.0 if cpu_spike_ratio > 1.5 else 0.0
    
    combined_score = (threshold_score + spike_score) / 2
    anomaly_detected = combined_score > 0.3
    confidence = min(combined_score, 1.0)
    
    return DetectionResult(
        algorithm_name="cpu_burst",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.CPU_BURST if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"CPU burst analysis: {current_cpu:.1f}% utilization (spike ratio: {cpu_spike_ratio:.2f})",
        contributing_features={
            'cpu_utilization': current_cpu,
            'threshold_score': threshold_score,
            'spike_score': spike_score,
            'cpu_spike_ratio': cpu_spike_ratio
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('cpu_burst', 0.038462, detect)
