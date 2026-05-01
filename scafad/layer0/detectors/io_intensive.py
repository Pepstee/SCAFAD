"""
SCAFAD Layer 0 — Detector: io_intensive
Algorithm 12: Algorithm 12: I/O intensive operation detection

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
    """Algorithm 12: I/O intensive operation detection"""
    
    # Analyze network I/O patterns
    network_bytes = telemetry.network_io_bytes
    duration = telemetry.duration
    
    # Calculate I/O rate
    io_rate = network_bytes / max(duration, 0.001)  # Bytes per second
    
    # I/O intensity thresholds
    high_io_threshold = 1024 * 1024  # 1MB/s
    duration_correlation_threshold = 2.0  # Long duration with high I/O
    
    # Scoring
    io_intensity_score = min(io_rate / high_io_threshold, 2.0)
    duration_penalty = min(duration / duration_correlation_threshold, 1.5) if duration > 1.0 else 1.0
    
    combined_score = io_intensity_score * duration_penalty
    anomaly_detected = combined_score > 1.2
    confidence = min(combined_score / 2.0, 1.0)
    
    return DetectionResult(
        algorithm_name="io_intensive",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.IO_INTENSIVE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"I/O analysis: {io_rate:.0f} bytes/s over {duration:.3f}s",
        contributing_features={
            'io_rate': io_rate,
            'network_bytes': network_bytes,
            'duration': duration,
            'io_intensity_score': io_intensity_score
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('io_intensive', 0.038462, detect)
