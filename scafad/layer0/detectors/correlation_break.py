"""
SCAFAD Layer 0 -- Detector: correlation_break
Algorithm 4: Correlation break detection between metrics

WP-3.7: Extracted from layer0_core.py monolith.
Part of the DetectorRegistry decomposition (C-1 layered contract architecture).
"""
from __future__ import annotations

import math
import logging
from collections import deque

import numpy as np

from layer0.layer0_core import (
    DetectionResult,
    DetectionConfig,
    AnomalyType,
    HAS_SKLEARN,
)
from layer0.app_telemetry import TelemetryRecord
from layer0.detectors.registry import REGISTRY

logger = logging.getLogger(__name__)


def _simple_correlation(x, y):
    """Simple correlation coefficient calculation"""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x)))
    
    sum_sq_x = sum((x[i] - mean_x) ** 2 for i in range(len(x)))
    sum_sq_y = sum((y[i] - mean_y) ** 2 for i in range(len(y)))
    
    denominator = math.sqrt(sum_sq_x * sum_sq_y)
    
    return numerator / denominator if denominator > 0 else 0.0



def detect(
    telemetry: TelemetryRecord,
    historical_data: deque,
    ml_models: dict,
    config: DetectionConfig,
) -> DetectionResult:
    """Algorithm 4: Correlation break detection between metrics"""
    
    if len(historical_data) < 30:
        return DetectionResult(
            algorithm_name="correlation_break",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation="Insufficient data for correlation analysis",
            contributing_features={},
            processing_time_ms=0.0
        )
    
    # Extract feature pairs for correlation analysis
    durations = [t.duration for t in historical_data]
    memories = [t.memory_spike_kb for t in historical_data]
    cpus = [t.cpu_utilization for t in historical_data]
    
    # Calculate historical correlations
    try:
        if HAS_SKLEARN:
            duration_memory_corr = np.corrcoef(durations, memories)[0, 1]
            duration_cpu_corr = np.corrcoef(durations, cpus)[0, 1]
            memory_cpu_corr = np.corrcoef(memories, cpus)[0, 1]
        else:
            # Simple correlation fallback
            duration_memory_corr = _simple_correlation(durations, memories)
            duration_cpu_corr = _simple_correlation(durations, cpus)
            memory_cpu_corr = _simple_correlation(memories, cpus)
        
        # Calculate current point's deviation from expected correlations
        current_duration = telemetry.duration
        current_memory = telemetry.memory_spike_kb
        current_cpu = telemetry.cpu_utilization
        
        # Predict expected values based on correlations
        if len(durations) > 1:
            duration_mean = np.mean(durations[:-1])  # Exclude current
            memory_mean = np.mean(memories[:-1])
            cpu_mean = np.mean(cpus[:-1])
            
            # Expected memory based on duration correlation
            expected_memory = memory_mean + duration_memory_corr * (current_duration - duration_mean)
            memory_deviation = abs(current_memory - expected_memory) / (memory_mean + 1)
            
            # Expected CPU based on duration correlation  
            expected_cpu = cpu_mean + duration_cpu_corr * (current_duration - duration_mean)
            cpu_deviation = abs(current_cpu - expected_cpu) / (cpu_mean + 1)
            
            # Overall correlation break score
            correlation_break_score = max(memory_deviation, cpu_deviation)
            anomaly_detected = correlation_break_score > 0.5
            confidence = min(correlation_break_score, 1.0)
        else:
            correlation_break_score = 0.0
            anomaly_detected = False
            confidence = 0.0
        
        return DetectionResult(
            algorithm_name="correlation_break",
            anomaly_detected=anomaly_detected,
            confidence_score=confidence,
            anomaly_type=AnomalyType.EXECUTION_FAILURE if anomaly_detected else AnomalyType.BENIGN,
            severity=confidence,
            explanation=f"Correlation analysis: break score {correlation_break_score:.3f}",
            contributing_features={
                'duration_memory_corr': duration_memory_corr,
                'duration_cpu_corr': duration_cpu_corr,
                'memory_cpu_corr': memory_cpu_corr,
                'break_score': correlation_break_score
            },
            processing_time_ms=0.0
        )
        
    except Exception as e:
        logger.error(f"Correlation analysis failed: {e}")
        return DetectionResult(
            algorithm_name="correlation_break",
            anomaly_detected=False,
            confidence_score=0.0,
            anomaly_type=AnomalyType.BENIGN,
            severity=0.0,
            explanation=f"Correlation analysis error: {str(e)}",
            contributing_features={},
            processing_time_ms=0.0
        )



REGISTRY.register('correlation_break', 0.038462, detect)
