"""
SCAFAD Layer 0 — Detector: security_anomaly
Algorithm 24: Algorithm 24: Security anomaly detection

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
    """Algorithm 24: Security anomaly detection"""
    
    # Security anomaly indicators
    network_bytes = telemetry.network_io_bytes
    duration = telemetry.duration
    memory = telemetry.memory_spike_kb
    
    # Security threat patterns
    data_exfiltration_threshold = 50 * 1024 * 1024  # 50MB
    suspicious_duration_threshold = 60.0  # 1 minute
    memory_abuse_threshold = 500 * 1024  # 500MB
    
    # Scoring security threats
    exfiltration_score = min(network_bytes / data_exfiltration_threshold, 2.0) if network_bytes > data_exfiltration_threshold else 0.0
    
    suspicious_duration_score = min(duration / suspicious_duration_threshold, 1.5) if duration > suspicious_duration_threshold else 0.0
    
    memory_abuse_score = min(memory / memory_abuse_threshold, 1.0) if memory > memory_abuse_threshold else 0.0
    
    # Check for unusual execution patterns that might indicate security issues
    execution_phase = telemetry.execution_phase
    phase_anomaly_score = 0.0
    
    if execution_phase == ExecutionPhase.ERROR:
        # Errors can indicate attempted exploits
        phase_anomaly_score = 0.3
    
    # Analyze recent pattern for security threats
    if len(historical_data) >= 10:
        recent_network = [t.network_io_bytes for t in list(historical_data)[-10:]]
        avg_recent_network = np.mean(recent_network)
        
        if avg_recent_network > 0:
            network_spike_ratio = network_bytes / avg_recent_network
            network_spike_score = min((network_spike_ratio - 1.0) / 9.0, 0.5) if network_spike_ratio > 5.0 else 0.0
        else:
            network_spike_score = 0.5 if network_bytes > 1024 * 1024 else 0.0  # 1MB threshold when no historical baseline
    else:
        network_spike_score = 0.0
    
    # Combined security anomaly score
    security_score = max(exfiltration_score, suspicious_duration_score, memory_abuse_score, 
                       phase_anomaly_score, network_spike_score)
    
    anomaly_detected = security_score > 0.4
    confidence = min(security_score, 1.0)
    
    return DetectionResult(
        algorithm_name="security_anomaly",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.NETWORK_ANOMALY if network_bytes > data_exfiltration_threshold else AnomalyType.EXECUTION_FAILURE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Security analysis: network {network_bytes} bytes, duration {duration:.3f}s, memory {memory}KB",
        contributing_features={
            'exfiltration_score': exfiltration_score,
            'suspicious_duration_score': suspicious_duration_score,
            'memory_abuse_score': memory_abuse_score,
            'network_spike_score': network_spike_score,
            'phase_anomaly_score': phase_anomaly_score
        },
        processing_time_ms=0.0
    )


# Register with DetectorRegistry at import time
REGISTRY.register('security_anomaly', 0.038462, detect)
