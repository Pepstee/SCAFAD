"""
SCAFAD Layer 0 — Detector: performance_regression
Algorithm 19: Algorithm 19: Performance regression detection

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
    """Algorithm 19: Performance regression detection"""
    
    if len(historical_data) < 20:
        return DetectionResult(
            algorithm_name="performance_regression",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for regression analysis",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Split data into older baseline and recent performance
    split_point = len(historical_data) // 2
    baseline_data = list(historical_data)[:split_point]
    recent_data = list(historical_data)[split_point:]
    
    # Performance metrics comparison
    baseline_duration = np.mean([t.duration for t in baseline_data])
    recent_duration = np.mean([t.duration for t in recent_data])
    
    baseline_memory = np.mean([t.memory_spike_kb for t in baseline_data])
    recent_memory = np.mean([t.memory_spike_kb for t in recent_data])
    
    baseline_cpu = np.mean([t.cpu_utilization for t in baseline_data])
    recent_cpu = np.mean([t.cpu_utilization for t in recent_data])
    
    # Calculate regression scores
    duration_regression = (recent_duration - baseline_duration) / (baseline_duration + 0.001)
    memory_regression = (recent_memory - baseline_memory) / (baseline_memory + 1)
    cpu_regression = (recent_cpu - baseline_cpu) / (baseline_cpu + 1)
    
    # Only consider significant regressions (degradation)
    duration_score = max(0, duration_regression) if duration_regression > 0.1 else 0.0
    memory_score = max(0, memory_regression) if memory_regression > 0.1 else 0.0
    cpu_score = max(0, cpu_regression) if cpu_regression > 0.1 else 0.0
    
    # Combined regression score
    regression_score = (duration_score * 0.5 + memory_score * 0.3 + cpu_score * 0.2)
    anomaly_detected = regression_score > 0.15
    confidence = min(regression_score / 0.3, 1.0)
    
    return DetectionResult(
        algorithm_name="performance_regression",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.EXECUTION_FAILURE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Performance regression: duration {duration_regression:.1%}, memory {memory_regression:.1%}, CPU {cpu_regression:.1%}",
        contributing_features={
            'duration_regression': duration_regression,
            'memory_regression': memory_regression,
            'cpu_regression': cpu_regression,
            'baseline_duration': baseline_duration,
            'recent_duration': recent_duration
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('performance_regression', 0.038462, detect)
