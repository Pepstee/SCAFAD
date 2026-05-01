"""
SCAFAD Layer 0 — Detector: execution_pattern
Algorithm 15: Algorithm 15: Execution pattern anomaly detection

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
    """Algorithm 15: Execution pattern anomaly detection"""
    
    if len(historical_data) < 15:
        return DetectionResult(
            algorithm_name="execution_pattern",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for execution pattern analysis",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Analyze execution phase patterns
    current_phase = telemetry.execution_phase
    phase_counts = defaultdict(int)
    phase_durations = defaultdict(list)
    
    for hist in historical_data:
        phase_counts[hist.execution_phase] += 1
        phase_durations[hist.execution_phase].append(hist.duration)
    
    # Expected pattern analysis
    total_executions = len(historical_data)
    current_phase_frequency = phase_counts[current_phase] / total_executions
    
    # Duration analysis for current phase
    if current_phase in phase_durations and len(phase_durations[current_phase]) > 3:
        phase_duration_mean = np.mean(phase_durations[current_phase])
        phase_duration_std = np.std(phase_durations[current_phase])
        
        if phase_duration_std > 0:
            duration_z_score = abs(telemetry.duration - phase_duration_mean) / phase_duration_std
        else:
            duration_z_score = 0.0
    else:
        duration_z_score = 0.0
    
    # Pattern anomaly scoring
    frequency_anomaly_score = 0.0
    if current_phase_frequency < 0.05:  # Very rare execution phase
        frequency_anomaly_score = 0.5
    
    duration_anomaly_score = min(duration_z_score / 3.0, 1.0)
    
    pattern_anomaly_score = max(frequency_anomaly_score, duration_anomaly_score)
    anomaly_detected = pattern_anomaly_score > 0.4
    confidence = pattern_anomaly_score
    
    return DetectionResult(
        algorithm_name="execution_pattern",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.EXECUTION_FAILURE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Execution pattern for {current_phase.value}: freq {current_phase_frequency:.2f}, duration z-score {duration_z_score:.2f}",
        contributing_features={
            'execution_phase': current_phase.value,
            'phase_frequency': current_phase_frequency,
            'duration_z_score': duration_z_score,
            'frequency_anomaly_score': frequency_anomaly_score
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('execution_pattern', 0.038462, detect)
