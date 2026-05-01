"""
SCAFAD Layer 0 — Detector: economic_abuse
Algorithm 26: Algorithm 26: Economic abuse detection

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
    """Algorithm 26: Economic abuse detection"""
    
    # Economic abuse indicators
    duration = telemetry.duration
    memory = telemetry.memory_spike_kb
    cpu = telemetry.cpu_utilization
    network_bytes = telemetry.network_io_bytes
    current_time = telemetry.timestamp
    
    # Resource abuse thresholds
    high_duration_threshold = 300.0  # 5 minutes
    high_memory_threshold = 1024 * 1024  # 1GB
    high_cpu_threshold = 95.0  # 95% CPU
    high_network_threshold = 100 * 1024 * 1024  # 100MB
    
    # Individual resource abuse scores
    duration_abuse_score = min(duration / high_duration_threshold, 2.0) if duration > high_duration_threshold else 0.0
    memory_abuse_score = min(memory / high_memory_threshold, 2.0) if memory > high_memory_threshold else 0.0
    cpu_abuse_score = min(cpu / high_cpu_threshold, 1.5) if cpu > high_cpu_threshold else 0.0
    network_abuse_score = min(network_bytes / high_network_threshold, 1.5) if network_bytes > high_network_threshold else 0.0
    
    # Frequency abuse detection
    frequency_abuse_score = 0.0
    if len(historical_data) >= 10:
        # Check invocation frequency in last hour
        hour_ago = current_time - 3600
        recent_hour_invocations = [
            t for t in historical_data
            if t.timestamp >= hour_ago
        ]
        
        hourly_frequency = len(recent_hour_invocations)
        
        # High frequency abuse thresholds
        if hourly_frequency > 1000:  # More than 1000 invocations per hour
            frequency_abuse_score = min(hourly_frequency / 1000.0, 2.0) - 1.0
    
    # Coordinated abuse pattern detection
    coordination_score = 0.0
    if frequency_abuse_score > 0:
        # Check if invocations follow suspicious patterns
        if len(historical_data) >= 20:
            recent_timestamps = [t.timestamp for t in list(historical_data)[-20:]]
            intervals = [recent_timestamps[i] - recent_timestamps[i-1] 
                       for i in range(1, len(recent_timestamps))]
            
            # Very regular intervals suggest automated abuse
            if len(intervals) > 5:
                avg_interval = np.mean(intervals)
                interval_std = np.std(intervals)
                
                if interval_std < avg_interval * 0.1 and avg_interval < 10:  # Very regular, frequent
                    coordination_score = 0.5
    
    # Economic cost calculation
    estimated_cost_factor = (duration * 0.001 +  # Duration cost factor
                           memory / (1024 * 1024) * 0.01 +  # Memory cost factor  
                           network_bytes / (1024 * 1024) * 0.001)  # Network cost factor
    
    cost_abuse_score = min(estimated_cost_factor / 10.0, 1.0) if estimated_cost_factor > 5.0 else 0.0
    
    # Combined economic abuse score
    economic_abuse_score = max(duration_abuse_score, memory_abuse_score, cpu_abuse_score, 
                             network_abuse_score, frequency_abuse_score, cost_abuse_score) + coordination_score * 0.3
    
    anomaly_detected = economic_abuse_score > 0.6
    confidence = min(economic_abuse_score, 1.0)
    
    return DetectionResult(
        algorithm_name="economic_abuse",
        anomaly_detected=anomaly_detected,
        confidence_score=confidence,
        anomaly_type=AnomalyType.ECONOMIC_ABUSE if anomaly_detected else AnomalyType.BENIGN,
        severity=confidence,
        explanation=f"Economic abuse analysis: duration {duration:.1f}s, memory {memory}KB, frequency score {frequency_abuse_score:.2f}",
        contributing_features={
            'duration_abuse_score': duration_abuse_score,
            'memory_abuse_score': memory_abuse_score,
            'cpu_abuse_score': cpu_abuse_score,
            'network_abuse_score': network_abuse_score,
            'frequency_abuse_score': frequency_abuse_score,
            'coordination_score': coordination_score,
            'cost_abuse_score': cost_abuse_score
        },
        processing_time_ms=0.0
    )

# =============================================================================
# Performance and Statistics Methods
# =============================================================================


# Register with DetectorRegistry at import time
REGISTRY.register('economic_abuse', 0.038462, detect)
