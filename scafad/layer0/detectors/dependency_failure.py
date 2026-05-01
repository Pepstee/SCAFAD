"""
SCAFAD Layer 0 — Detector: dependency_failure
Algorithm 25: Algorithm 25: Dependency failure detection

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
    """Algorithm 25: Dependency failure detection"""
    
    # Dependency failure patterns
    duration = telemetry.duration
    network_bytes = telemetry.network_io_bytes
    execution_phase = telemetry.execution_phase
    
    # Common dependency failure indicators
    timeout_like_duration = duration > 30.0  # Long duration suggesting timeouts
    low_network_activity = network_bytes < 1024  # Very low network suggests failed connections
    error_phase = execution_phase == ExecutionPhase.ERROR
    
    # Analyze network patterns for dependency failures
    if len(historical_data) >= 5:
        recent_network = [t.network_io_bytes for t in list(historical_data)[-5:]]
        avg_network = np.mean(recent_network)
        
        # Sudden drop in network activity
        network_drop_score = 0.0
        if avg_network > 10 * 1024 and network_bytes < avg_network * 0.1:  # 90% drop
            network_drop_score = 0.7
    else:
        network_drop_score = 0.0
    
    # Duration analysis for dependency timeouts
    timeout_score = 0.0
    if timeout_like_duration:
        # Common service timeout values
        common_timeouts = [5, 10, 30, 60]  # seconds
        
        for timeout_val in common_timeouts:
            if abs(duration - timeout_val) < 1.0:  # Within 1 second of common timeout
                timeout_score = 0.8
                break
        
        if timeout_score == 0.0:  # Not a standard timeout, but still long
            timeout_score = min(duration / 60.0, 0.6)
    
    # Error phase scoring
    error_phase_score = 0.6 if error_phase else 0.0
    
    # Low network activity score
    low_network_score = 0.4 if low_network_activity and not error_phase else 0.0
    
    # Combined dependency failure score
    dependency_failure_score = max(timeout_score, error_phase_score, network_drop_score, low_network_score)
    
    anomaly_detected = dependency_failure_score > 0.4
    confidence = dependency_failure_score
    
    return DetectionResult(
        algorithm_name="dependency_failure",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.TIMEOUT_FALLBACK if timeout_like_duration else AnomalyType.EXECUTION_FAILURE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Dependency analysis: duration {duration:.3f}s, network {network_bytes} bytes, error phase: {error_phase}",
        contributing_features={
            'timeout_score': timeout_score,
            'error_phase_score': error_phase_score,
            'network_drop_score': network_drop_score,
            'low_network_score': low_network_score,
            'timeout_like_duration': timeout_like_duration
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('dependency_failure', 0.038462, detect)
