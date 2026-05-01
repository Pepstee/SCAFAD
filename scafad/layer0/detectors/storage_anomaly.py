"""
SCAFAD Layer 0 — Detector: storage_anomaly
Algorithm 14: Algorithm 14: Storage anomaly detection

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
    """Algorithm 14: Storage anomaly detection"""
    
    # For serverless functions, storage anomalies often relate to memory usage patterns
    memory_kb = telemetry.memory_spike_kb
    duration = telemetry.duration
    
    # Storage-related anomaly indicators
    memory_duration_ratio = memory_kb / max(duration, 0.001)  # Memory per second
    
    # Thresholds for storage anomaly patterns
    high_memory_sustained_threshold = 50 * 1024  # 50MB sustained
    rapid_memory_growth_threshold = 100 * 1024   # 100MB/s growth rate
    
    # Scoring
    sustained_score = min(memory_kb / high_memory_sustained_threshold, 2.0) if duration > 2.0 else 0.0
    rapid_growth_score = min(memory_duration_ratio / rapid_memory_growth_threshold, 2.0)
    
    # Check for memory patterns that indicate storage issues
    storage_anomaly_score = max(sustained_score, rapid_growth_score)
    anomaly_detected = storage_anomaly_score > 0.6
    confidence = min(storage_anomaly_score / 1.5, 1.0)
    
    return DetectionResult(
        algorithm_name="storage_anomaly",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.MEMORY_SPIKE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Storage analysis: {memory_kb}KB over {duration:.3f}s (ratio: {memory_duration_ratio:.0f})",
        contributing_features={
            'memory_kb': memory_kb,
            'duration': duration,
            'memory_duration_ratio': memory_duration_ratio,
            'sustained_score': sustained_score,
            'rapid_growth_score': rapid_growth_score
        },
        processing_time_ms=0.0
    )

# Execution Pattern Algorithms (6)


# Register with DetectorRegistry at import time
REGISTRY.register('storage_anomaly', 0.038462, detect)
