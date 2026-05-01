"""
SCAFAD Layer 0 — Detector: network_anomaly
Algorithm 13: Algorithm 13: Network anomaly detection

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
    """Algorithm 13: Network anomaly detection"""
    
    if len(historical_data) < 10:
        return DetectionResult(
            algorithm_name="network_anomaly",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for network analysis",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Get network statistics
    current_network = telemetry.network_io_bytes
    historical_network = [t.network_io_bytes for t in historical_data]
    
    # Statistical analysis
    mean_network = np.mean(historical_network)
    std_network = np.std(historical_network)
    median_network = np.percentile(historical_network, 50)
    p95_network = np.percentile(historical_network, 95)
    
    # Anomaly indicators
    if std_network > 0:
        z_score = abs(current_network - mean_network) / std_network
    else:
        z_score = 0.0
    
    percentile_score = 0.0
    if current_network > p95_network:
        percentile_score = min((current_network - p95_network) / (p95_network + 1), 2.0)
    
    # Check for zero network activity (suspicious for most functions)
    zero_network_penalty = 0.5 if current_network == 0 and mean_network > 1000 else 0.0
    
    # Combined network anomaly score
    network_anomaly_score = max(z_score / 3.0, percentile_score / 2.0, zero_network_penalty)
    anomaly_detected = network_anomaly_score > 0.4
    confidence = min(network_anomaly_score, 1.0)
    
    return DetectionResult(
        algorithm_name="network_anomaly",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.NETWORK_ANOMALY if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Network analysis: {current_network} bytes vs mean {mean_network:.0f} (z-score: {z_score:.2f})",
        contributing_features={
            'current_network': current_network,
            'mean_network': mean_network,
            'z_score': z_score,
            'percentile_score': percentile_score,
            'zero_penalty': zero_network_penalty
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('network_anomaly', 0.038462, detect)
