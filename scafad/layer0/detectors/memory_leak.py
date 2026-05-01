"""
SCAFAD Layer 0 — Detector: memory_leak
Algorithm 10: Algorithm 10: Memory leak pattern detection

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
    """Algorithm 10: Memory leak pattern detection"""
    
    if len(historical_data) < 10:
        return DetectionResult(
            algorithm_name="memory_leak",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for memory leak detection",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Analyze memory trend over recent invocations
    recent_memory = [t.memory_spike_kb for t in list(historical_data)[-10:]]
    
    # Calculate memory growth trend
    n = len(recent_memory)
    x_values = list(range(n))
    
    # Linear regression for memory trend
    sum_x = sum(x_values)
    sum_y = sum(recent_memory)
    sum_xy = sum(x * y for x, y in zip(x_values, recent_memory))
    sum_x2 = sum(x * x for x in x_values)
    
    if n * sum_x2 - sum_x * sum_x != 0:
        memory_slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
    else:
        memory_slope = 0.0
    
    # Memory leak indicators
    avg_memory = np.mean(recent_memory)
    memory_growth_rate = memory_slope / (avg_memory + 1)  # Normalized growth rate
    
    # Check for consistent upward trend
    increasing_count = sum(1 for i in range(1, len(recent_memory)) 
                          if recent_memory[i] > recent_memory[i-1])
    consistency_score = increasing_count / (len(recent_memory) - 1)
    
    # Combined memory leak score
    leak_score = memory_growth_rate * consistency_score * 10  # Scale factor
    anomaly_detected = leak_score > 0.3 and memory_slope > 1000  # 1KB growth per invocation
    confidence = min(leak_score, 1.0)
    
    return DetectionResult(
        algorithm_name="memory_leak",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.MEMORY_SPIKE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Memory leak analysis: slope {memory_slope:.2f} KB/invocation, consistency {consistency_score:.2f}",
        contributing_features={
            'memory_slope': memory_slope,
            'memory_growth_rate': memory_growth_rate,
            'consistency_score': consistency_score,
            'leak_score': leak_score
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('memory_leak', 0.038462, detect)
