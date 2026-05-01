"""
SCAFAD Layer 0 — Detector: concurrency_anomaly
Algorithm 20: Algorithm 20: Concurrency anomaly detection

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
    """Algorithm 20: Concurrency anomaly detection"""
    
    # Analyze concurrent execution patterns based on timestamps
    current_time = telemetry.timestamp
    concurrent_window = 5.0  # 5 second window
    
    # Find potentially concurrent executions
    concurrent_executions = [
        t for t in historical_data
        if abs(t.timestamp - current_time) <= concurrent_window and t != telemetry
    ]
    
    concurrent_count = len(concurrent_executions)
    
    # Analyze resource usage during concurrent period
    if concurrent_executions:
        concurrent_total_memory = sum(t.memory_spike_kb for t in concurrent_executions) + telemetry.memory_spike_kb
        concurrent_total_cpu = sum(t.cpu_utilization for t in concurrent_executions) + telemetry.cpu_utilization
        concurrent_avg_duration = np.mean([t.duration for t in concurrent_executions + [telemetry]])
    else:
        concurrent_total_memory = telemetry.memory_spike_kb
        concurrent_total_cpu = telemetry.cpu_utilization
        concurrent_avg_duration = telemetry.duration
    
    # Concurrency thresholds
    high_concurrency_threshold = 5
    resource_contention_threshold = 200 * 1024  # 200MB total memory
    cpu_contention_threshold = 300.0  # 300% total CPU (indicating oversubscription)
    
    # Scoring
    concurrency_score = min(concurrent_count / high_concurrency_threshold, 2.0) if concurrent_count > 2 else 0.0
    memory_contention_score = min(concurrent_total_memory / resource_contention_threshold, 1.5) if concurrent_total_memory > resource_contention_threshold else 0.0
    cpu_contention_score = min(concurrent_total_cpu / cpu_contention_threshold, 1.5) if concurrent_total_cpu > cpu_contention_threshold else 0.0
    
    # Duration penalty for concurrent executions (resource contention effect)
    duration_penalty = min(concurrent_avg_duration / 2.0, 1.0) if concurrent_count > 0 else 0.0
    
    # Combined concurrency anomaly score
    concurrency_anomaly_score = max(concurrency_score, memory_contention_score, cpu_contention_score) + duration_penalty * 0.3
    anomaly_detected = concurrency_anomaly_score > 0.6
    confidence = min(concurrency_anomaly_score / 1.5, 1.0)
    
    return DetectionResult(
        algorithm_name="concurrency_anomaly",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.STARVATION_FALLBACK if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Concurrency analysis: {concurrent_count} concurrent executions, total memory {concurrent_total_memory}KB",
        contributing_features={
            'concurrent_count': concurrent_count,
            'concurrent_total_memory': concurrent_total_memory,
            'concurrent_total_cpu': concurrent_total_cpu,
            'concurrency_score': concurrency_score,
            'memory_contention_score': memory_contention_score
        },
        processing_time_ms=0.0
    )

# Advanced Detection Algorithms (6)


# Register with DetectorRegistry at import time
REGISTRY.register('concurrency_anomaly', 0.038462, detect)
