"""
SCAFAD Layer 0 — Detector: resource_starvation
Algorithm 23: Algorithm 23: Resource starvation detection

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
    """Algorithm 23: Resource starvation detection"""
    
    # Resource starvation indicators
    duration = telemetry.duration
    memory = telemetry.memory_spike_kb
    cpu = telemetry.cpu_utilization
    
    # Starvation patterns: high duration with low resource utilization
    starvation_duration_threshold = 5.0  # 5 seconds
    low_resource_threshold_cpu = 10.0    # 10% CPU
    low_resource_threshold_memory = 5 * 1024  # 5MB
    
    # Analyze if current execution shows starvation patterns
    duration_penalty = min(duration / starvation_duration_threshold, 3.0) if duration > starvation_duration_threshold else 0.0
    low_cpu_score = max(0, (low_resource_threshold_cpu - cpu) / low_resource_threshold_cpu) if cpu < low_resource_threshold_cpu else 0.0
    low_memory_score = max(0, (low_resource_threshold_memory - memory) / low_resource_threshold_memory) if memory < low_resource_threshold_memory else 0.0
    
    # Check concurrent resource competition
    current_time = telemetry.timestamp
    concurrent_executions = [
        t for t in historical_data
        if abs(t.timestamp - current_time) <= 10.0  # 10 second window
    ]
    
    resource_competition_score = 0.0
    if len(concurrent_executions) > 2:
        total_concurrent_cpu = sum(t.cpu_utilization for t in concurrent_executions)
        total_concurrent_memory = sum(t.memory_spike_kb for t in concurrent_executions)
        
        # High total resource usage suggests competition
        if total_concurrent_cpu > 200.0:  # Over 200% CPU total
            resource_competition_score += 0.5
        if total_concurrent_memory > 100 * 1024:  # Over 100MB total
            resource_competition_score += 0.3
    
    # Combined starvation score
    starvation_score = (duration_penalty * 0.4 + 
                       (low_cpu_score + low_memory_score) * 0.4 + 
                       resource_competition_score * 0.2)
    
    anomaly_detected = starvation_score > 0.5
    confidence = min(starvation_score, 1.0)
    
    return DetectionResult(
        algorithm_name="resource_starvation",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.STARVATION_FALLBACK if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Resource starvation: duration {duration:.3f}s, CPU {cpu:.1f}%, memory {memory}KB",
        contributing_features={
            'duration_penalty': duration_penalty,
            'low_cpu_score': low_cpu_score,
            'low_memory_score': low_memory_score,
            'resource_competition_score': resource_competition_score,
            'concurrent_count': len(concurrent_executions)
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('resource_starvation', 0.038462, detect)
