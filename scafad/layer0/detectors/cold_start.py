"""
SCAFAD Layer 0 — Detector: cold_start
Algorithm 16: Algorithm 16: Cold start detection

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
    """Algorithm 16: Cold start detection"""
    
    # Cold start indicators
    duration = telemetry.duration
    memory = telemetry.memory_spike_kb
    execution_phase = telemetry.execution_phase
    
    # Cold start patterns
    cold_start_duration_threshold = 1.0  # Seconds
    cold_start_memory_threshold = 20 * 1024  # 20MB
    
    # Scoring factors
    duration_score = min(duration / cold_start_duration_threshold, 2.0) if duration > cold_start_duration_threshold else 0.0
    memory_score = min(memory / cold_start_memory_threshold, 1.5) if memory > cold_start_memory_threshold else 0.0
    phase_score = 1.0 if execution_phase == ExecutionPhase.INIT else 0.0
    
    # Check recent invocation pattern (cold starts often follow gaps)
    time_gap_score = 0.0
    if len(historical_data) > 1:
        last_invocation = list(historical_data)[-2]  # Previous invocation
        time_gap = telemetry.timestamp - last_invocation.timestamp
        if time_gap > 300:  # 5 minute gap suggests cold start
            time_gap_score = min(time_gap / 600, 1.0)  # Scale to 10 minutes
    
    # Combined cold start score
    cold_start_score = (duration_score * 0.4 + memory_score * 0.3 + 
                       phase_score * 0.2 + time_gap_score * 0.1)
    
    anomaly_detected = cold_start_score > 0.5
    confidence = min(cold_start_score, 1.0)
    
    return DetectionResult(
        algorithm_name="cold_start",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.COLD_START if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Cold start analysis: duration {duration:.3f}s, memory {memory}KB, phase {execution_phase.value}",
        contributing_features={
            'duration_score': duration_score,
            'memory_score': memory_score,
            'phase_score': phase_score,
            'time_gap_score': time_gap_score,
            'cold_start_score': cold_start_score
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('cold_start', 0.038462, detect)
