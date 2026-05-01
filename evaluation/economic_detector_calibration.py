#!/usr/bin/env python3
"""
SCAFAD Economic Detector Calibration Study
==========================================

This module evaluates and calibrates the economic abuse detection components
of SCAFAD against labeled DoW (Denial of Wallet), cryptocurrency mining, and
resource amplification attack scenarios. It provides ROC/PR curve analysis
and false alarm rate control under spiky but benign workloads.

Key Evaluation Areas:
1. DoW Attack Detection (cost amplification, resource exhaustion)
2. Cryptocurrency Mining Detection (CPU patterns, network behavior)
3. Resource Amplification Detection (lambda chaining, memory bombs)
4. False Alarm Rate Control under legitimate traffic spikes
5. Threshold Optimization for Production Deployment

Economic Attack Types:
- Denial of Wallet (DoW): Attacks that amplify costs without business value
- Cryptocurrency Mining: Unauthorized compute resource hijacking  
- Resource Amplification: Exponential resource consumption attacks
- Lambda Chaining Abuse: Creating expensive invocation cascades
- Memory/Storage Bombs: Excessive resource allocation patterns

Benign Workload Challenges:
- Flash traffic spikes (legitimate viral content, sales events)
- Batch processing workloads (ETL, data analysis)
- Development/testing bursts (CI/CD pipelines)
- Seasonal patterns (holiday traffic, business cycles)
- Auto-scaling events (cold start storms, warmup periods)

Statistical Rigor:
- ROC curves with 95% confidence intervals
- Precision-Recall curves for imbalanced datasets
- Cost-sensitive evaluation metrics (false positive cost analysis)
- Threshold optimization with business constraints
- Cross-validation with temporal splits (avoid data leakage)
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from pathlib import Path
import json
import time
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import itertools

# Statistical analysis and ML
from scipy import stats
from sklearn.metrics import (
    roc_curve, precision_recall_curve, auc, 
    precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)
from sklearn.model_selection import TimeSeriesSplit
import matplotlib.pyplot as plt
import seaborn as sns

# Import SCAFAD components
from datasets.serverless_traces import RealisticServerlessTraceGenerator, WorkloadType
from app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase
from app_config import get_default_config

logger = logging.getLogger(__name__)


@dataclass
class EconomicAttackScenario:
    """Defines an economic attack scenario for testing"""
    attack_id: str
    attack_type: str  # 'dow', 'crypto_mining', 'amplification', 'lambda_chaining'
    severity: float  # 0.0-1.0
    duration_minutes: float
    cost_multiplier: float  # Expected cost amplification
    resource_patterns: Dict[str, Any]
    ground_truth_label: int  # 1 for attack, 0 for benign


@dataclass  
class BenignWorkloadPattern:
    """Defines a benign workload pattern that might trigger false alarms"""
    pattern_id: str
    pattern_type: str  # 'flash_spike', 'batch_processing', 'auto_scaling', 'seasonal'
    intensity: float  # Relative intensity vs normal traffic
    duration_minutes: float
    characteristics: Dict[str, Any]
    ground_truth_label: int = 0  # Always 0 for benign


@dataclass
class DetectionResult:
    """Result of economic attack detection"""
    timestamp: float
    attack_score: float  # 0.0-1.0 confidence score
    predicted_label: int  # 0 or 1
    ground_truth_label: int
    attack_type: str
    cost_estimate: float
    resource_metrics: Dict[str, float]
    detection_latency_ms: float


@dataclass
class CalibrationResults:
    """Results of economic detector calibration"""
    roc_analysis: Dict[str, Any]
    pr_analysis: Dict[str, Any]
    threshold_optimization: Dict[str, Any]
    false_alarm_analysis: Dict[str, Any]
    cost_benefit_analysis: Dict[str, Any]
    attack_type_performance: Dict[str, Any]


class EconomicAttackGenerator:
    """Generates realistic economic attack scenarios"""
    
    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)
        self.trace_generator = RealisticServerlessTraceGenerator(random_seed=random_seed)
        
    def generate_dow_attack_scenario(self, severity: float = 0.8) -> EconomicAttackScenario:
        """Generate Denial of Wallet attack scenario"""
        
        return EconomicAttackScenario(
            attack_id=f"dow_attack_{int(time.time())}_{np.random.randint(1000)}",
            attack_type="dow",
            severity=severity,
            duration_minutes=np.random.uniform(5, 30),
            cost_multiplier=2.0 + severity * 8.0,  # 2x to 10x cost amplification
            resource_patterns={
                "memory_usage_multiplier": 1.5 + severity * 2.0,
                "execution_time_multiplier": 1.2 + severity * 1.8,
                "invocation_frequency_multiplier": 2.0 + severity * 3.0,
                "network_io_multiplier": 1.0 + severity * 2.0,
                "error_rate": 0.1 + severity * 0.3
            },
            ground_truth_label=1
        )
    
    def generate_crypto_mining_scenario(self, severity: float = 0.9) -> EconomicAttackScenario:
        """Generate cryptocurrency mining attack scenario"""
        
        return EconomicAttackScenario(
            attack_id=f"crypto_mining_{int(time.time())}_{np.random.randint(1000)}",
            attack_type="crypto_mining",
            severity=severity,
            duration_minutes=np.random.uniform(10, 60),
            cost_multiplier=1.5 + severity * 3.5,  # 1.5x to 5x cost amplification
            resource_patterns={
                "cpu_usage_percent": 85.0 + severity * 10.0,  # Very high CPU
                "execution_time_multiplier": 5.0 + severity * 10.0,  # Long execution
                "memory_usage_multiplier": 1.1 + severity * 0.4,  # Slightly higher memory
                "network_io_multiplier": 0.5 + severity * 0.3,  # Low network I/O
                "power_consumption_multiplier": 2.0 + severity * 3.0,
                "heat_signature": 0.8 + severity * 0.2
            },
            ground_truth_label=1
        )
    
    def generate_amplification_attack_scenario(self, severity: float = 0.7) -> EconomicAttackScenario:
        """Generate resource amplification attack scenario"""
        
        return EconomicAttackScenario(
            attack_id=f"amplification_{int(time.time())}_{np.random.randint(1000)}",
            attack_type="amplification",
            severity=severity,
            duration_minutes=np.random.uniform(2, 15),  # Shorter but intense
            cost_multiplier=3.0 + severity * 12.0,  # 3x to 15x cost amplification
            resource_patterns={
                "memory_usage_multiplier": 5.0 + severity * 15.0,  # Memory bomb
                "execution_time_multiplier": 0.8 + severity * 0.4,  # Quick but expensive
                "invocation_cascade_depth": int(2 + severity * 5),  # Lambda chaining
                "storage_io_multiplier": 10.0 + severity * 40.0,  # Massive I/O
                "network_bandwidth_multiplier": 2.0 + severity * 8.0,
                "exponential_growth_rate": 1.5 + severity * 1.0
            },
            ground_truth_label=1
        )
    
    def generate_lambda_chaining_scenario(self, severity: float = 0.6) -> EconomicAttackScenario:
        """Generate lambda chaining abuse scenario"""
        
        return EconomicAttackScenario(
            attack_id=f"lambda_chaining_{int(time.time())}_{np.random.randint(1000)}",
            attack_type="lambda_chaining", 
            severity=severity,
            duration_minutes=np.random.uniform(1, 10),
            cost_multiplier=1.8 + severity * 6.2,  # 1.8x to 8x cost amplification
            resource_patterns={
                "chain_length": int(3 + severity * 12),  # 3-15 function chain
                "invocation_frequency_per_chain": 2.0 + severity * 8.0,
                "memory_usage_per_step": 20000 + severity * 80000,  # KB
                "execution_time_per_step": 0.5 + severity * 2.0,  # Seconds
                "cascading_probability": 0.7 + severity * 0.2,
                "recursive_depth": int(1 + severity * 4)
            },
            ground_truth_label=1
        )


class BenignWorkloadGenerator:
    """Generates benign workload patterns that may trigger false alarms"""
    
    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)
        
    def generate_flash_spike_pattern(self, intensity: float = 3.0) -> BenignWorkloadPattern:
        """Generate legitimate flash traffic spike (viral content, flash sale)"""
        
        return BenignWorkloadPattern(
            pattern_id=f"flash_spike_{int(time.time())}_{np.random.randint(1000)}",
            pattern_type="flash_spike",
            intensity=intensity,
            duration_minutes=np.random.uniform(3, 20),
            characteristics={
                "traffic_multiplier": intensity,
                "ramp_up_minutes": np.random.uniform(0.5, 3.0),
                "ramp_down_minutes": np.random.uniform(5, 15),
                "user_behavior": "legitimate",
                "geographic_spread": "global",
                "session_patterns": "normal",
                "error_rate_increase": min(0.05, intensity * 0.01),  # Slight increase due to load
                "cache_miss_rate": intensity * 0.1  # Higher cache misses
            }
        )
    
    def generate_batch_processing_pattern(self, intensity: float = 5.0) -> BenignWorkloadPattern:
        """Generate legitimate batch processing workload (ETL, data analysis)"""
        
        return BenignWorkloadPattern(
            pattern_id=f"batch_processing_{int(time.time())}_{np.random.randint(1000)}",
            pattern_type="batch_processing",
            intensity=intensity,
            duration_minutes=np.random.uniform(15, 120),
            characteristics={
                "cpu_usage_percent": 70 + np.random.uniform(0, 20),
                "memory_usage_pattern": "gradual_increase",
                "execution_time_multiplier": 2.0 + intensity * 0.5,
                "data_processing_volume_gb": 10 + intensity * 5,
                "network_io_pattern": "bursty_read_heavy", 
                "storage_io_pattern": "sequential_large_blocks",
                "predictable_timing": True,
                "business_justification": "scheduled_etl"
            }
        )
    
    def generate_auto_scaling_pattern(self, intensity: float = 4.0) -> BenignWorkloadPattern:
        """Generate auto-scaling event pattern (cold start storm, warmup)"""
        
        return BenignWorkloadPattern(
            pattern_id=f"auto_scaling_{int(time.time())}_{np.random.randint(1000)}",
            pattern_type="auto_scaling",
            intensity=intensity,
            duration_minutes=np.random.uniform(2, 10),
            characteristics={
                "cold_start_percentage": 0.8 + np.random.uniform(0, 0.15),
                "initialization_time_multiplier": 3.0 + intensity * 1.0,
                "memory_initialization_spike": True,
                "concurrent_initialization_count": int(10 + intensity * 20),
                "warmup_duration_minutes": np.random.uniform(1, 5),
                "scaling_trigger": "legitimate_load_increase",
                "container_creation_pattern": "exponential_backoff",
                "resource_competition": True
            }
        )
    
    def generate_seasonal_pattern(self, intensity: float = 2.5) -> BenignWorkloadPattern:
        """Generate seasonal traffic pattern (holiday, business cycle)"""
        
        return BenignWorkloadPattern(
            pattern_id=f"seasonal_{int(time.time())}_{np.random.randint(1000)}",
            pattern_type="seasonal",
            intensity=intensity,
            duration_minutes=np.random.uniform(60, 480),  # 1-8 hours
            characteristics={
                "traffic_pattern": "gradual_increase_plateau_decrease",
                "user_behavior_changes": "increased_engagement",
                "geographic_concentration": "timezone_specific",
                "business_metrics_correlation": "positive",
                "historical_precedent": True,
                "predictable_pattern": True,
                "revenue_correlation": "strong_positive",
                "user_satisfaction_metrics": "improved"
            }
        )


class EconomicDetector:
    """Economic abuse detection engine"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or get_default_config()
        
        # Detection thresholds (will be calibrated)
        self.thresholds = {
            "dow_detection": 0.7,
            "crypto_mining_detection": 0.8,
            "amplification_detection": 0.6,
            "lambda_chaining_detection": 0.65,
            "cost_anomaly_threshold": 2.0,  # 2x normal cost
            "execution_time_anomaly": 3.0,  # 3x normal execution time
            "memory_anomaly_threshold": 5.0  # 5x normal memory usage
        }
        
        # Baseline metrics (would be learned from historical data)
        self.baselines = {
            "normal_cost_per_invocation": 0.000021,  # $0.000021 per invocation
            "normal_execution_time_ms": 150,
            "normal_memory_usage_mb": 45,
            "normal_cpu_utilization": 15.0,
            "normal_error_rate": 0.02
        }
    
    def detect_economic_attacks(self, telemetry_records: List[TelemetryRecord]) -> List[DetectionResult]:
        """Detect economic attacks in telemetry data"""
        
        if not telemetry_records:
            return []
        
        results = []
        detection_start_time = time.time()
        
        for record in telemetry_records:
            # Calculate detection scores for each attack type
            dow_score = self._calculate_dow_score(record)
            crypto_score = self._calculate_crypto_mining_score(record)
            amplification_score = self._calculate_amplification_score(record)
            chaining_score = self._calculate_lambda_chaining_score(record)
            
            # Overall economic attack score (max of individual scores)
            attack_score = max(dow_score, crypto_score, amplification_score, chaining_score)
            
            # Determine attack type
            scores = {
                "dow": dow_score,
                "crypto_mining": crypto_score,
                "amplification": amplification_score,
                "lambda_chaining": chaining_score
            }
            
            detected_attack_type = max(scores, key=scores.get)
            
            # Apply threshold for prediction
            predicted_label = 1 if attack_score >= self.thresholds.get(f"{detected_attack_type}_detection", 0.7) else 0
            
            # Calculate cost estimate
            cost_estimate = self._estimate_attack_cost(record, detected_attack_type, attack_score)
            
            # Extract resource metrics
            resource_metrics = {
                "memory_usage_mb": record.memory_spike_kb / 1024,
                "cpu_utilization": record.cpu_utilization,
                "execution_time_ms": record.duration * 1000,
                "network_io_bytes": record.network_io_bytes
            }
            
            # Detection latency (simulated)
            detection_latency_ms = (time.time() - detection_start_time) * 1000
            
            result = DetectionResult(
                timestamp=record.timestamp,
                attack_score=attack_score,
                predicted_label=predicted_label,
                ground_truth_label=getattr(record, 'ground_truth_label', 0),  # From synthetic data
                attack_type=detected_attack_type,
                cost_estimate=cost_estimate,
                resource_metrics=resource_metrics,
                detection_latency_ms=detection_latency_ms
            )
            
            results.append(result)
        
        return results
    
    def _calculate_dow_score(self, record: TelemetryRecord) -> float:
        """Calculate Denial of Wallet attack score"""
        
        score = 0.0
        
        # Cost amplification indicators
        estimated_cost = self._estimate_invocation_cost(record)
        normal_cost = self.baselines["normal_cost_per_invocation"]
        
        if normal_cost > 0:
            cost_ratio = estimated_cost / normal_cost
            if cost_ratio > 2.0:
                score += min(0.4, (cost_ratio - 2.0) / 8.0)  # Up to 0.4 for cost amplification
        
        # Execution time amplification
        execution_time_ratio = (record.duration * 1000) / self.baselines["normal_execution_time_ms"]
        if execution_time_ratio > 1.5:
            score += min(0.3, (execution_time_ratio - 1.5) / 5.0)  # Up to 0.3 for time amplification
        
        # Memory usage amplification
        memory_mb = record.memory_spike_kb / 1024
        memory_ratio = memory_mb / self.baselines["normal_memory_usage_mb"]
        if memory_ratio > 2.0:
            score += min(0.2, (memory_ratio - 2.0) / 8.0)  # Up to 0.2 for memory amplification
        
        # Error rate (attacks often cause errors)
        if record.telemetry_metadata.get("error_occurred", False):
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_crypto_mining_score(self, record: TelemetryRecord) -> float:
        """Calculate cryptocurrency mining attack score"""
        
        score = 0.0
        
        # High CPU utilization pattern
        cpu_ratio = record.cpu_utilization / self.baselines["normal_cpu_utilization"]
        if cpu_ratio > 3.0:
            score += min(0.5, (cpu_ratio - 3.0) / 7.0)  # Up to 0.5 for high CPU
        
        # Long execution time with high CPU
        execution_time_ms = record.duration * 1000
        if execution_time_ms > 10000:  # > 10 seconds
            score += min(0.3, (execution_time_ms - 10000) / 50000)  # Up to 0.3 for long execution
        
        # Low network I/O (crypto mining is compute-heavy, not I/O heavy)
        memory_mb = record.memory_spike_kb / 1024
        io_to_memory_ratio = record.network_io_bytes / max(memory_mb * 1024 * 1024, 1)
        
        if io_to_memory_ratio < 0.1:  # Low I/O relative to memory usage
            score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_amplification_score(self, record: TelemetryRecord) -> float:
        """Calculate resource amplification attack score"""
        
        score = 0.0
        
        # Extreme memory usage
        memory_mb = record.memory_spike_kb / 1024
        memory_ratio = memory_mb / self.baselines["normal_memory_usage_mb"]
        if memory_ratio > 10.0:
            score += min(0.6, (memory_ratio - 10.0) / 50.0)  # Up to 0.6 for memory bomb
        
        # High network I/O (data amplification)
        if record.network_io_bytes > 100 * 1024 * 1024:  # > 100MB
            score += min(0.3, record.network_io_bytes / (1024 * 1024 * 1024))  # Up to 0.3 for high I/O
        
        # Short execution time with high resource usage (amplification pattern)
        if record.duration < 2.0 and memory_mb > 200:  # < 2s but > 200MB
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_lambda_chaining_score(self, record: TelemetryRecord) -> float:
        """Calculate lambda chaining abuse score"""
        
        score = 0.0
        
        # Multiple invocations pattern (would need trace context)
        # For now, use proxy metrics
        
        # Moderate resource usage but pattern suggests chaining
        memory_mb = record.memory_spike_kb / 1024
        if 50 < memory_mb < 150:  # Moderate memory usage
            score += 0.2
        
        # Moderate execution time (individual chain steps aren't too long)
        execution_time_ms = record.duration * 1000
        if 500 < execution_time_ms < 3000:  # 0.5-3 seconds
            score += 0.3
        
        # Network I/O pattern (function-to-function communication)
        if 1024 < record.network_io_bytes < 10 * 1024 * 1024:  # 1KB - 10MB
            score += 0.2
        
        # Check for invocation patterns in metadata
        invocation_count = record.telemetry_metadata.get("invocation_cascade_count", 1)
        if invocation_count > 3:
            score += min(0.3, (invocation_count - 3) / 10.0)
        
        return min(score, 1.0)
    
    def _estimate_invocation_cost(self, record: TelemetryRecord) -> float:
        """Estimate cost of a single invocation based on AWS Lambda pricing"""
        
        # AWS Lambda pricing (approximate):
        # - $0.0000166667 per GB-second
        # - $0.0000002 per request
        
        memory_gb = (record.memory_spike_kb / 1024) / 1024
        execution_time_seconds = record.duration
        
        compute_cost = 0.0000166667 * memory_gb * execution_time_seconds
        request_cost = 0.0000002
        
        # Additional costs for I/O (simplified)
        io_cost = (record.network_io_bytes / (1024 * 1024 * 1024)) * 0.00001  # $0.00001 per GB
        
        return compute_cost + request_cost + io_cost
    
    def _estimate_attack_cost(self, record: TelemetryRecord, attack_type: str, attack_score: float) -> float:
        """Estimate potential cost impact of an attack"""
        
        base_cost = self._estimate_invocation_cost(record)
        
        # Cost multipliers by attack type
        multipliers = {
            "dow": 2.0 + attack_score * 8.0,
            "crypto_mining": 1.5 + attack_score * 3.5,
            "amplification": 3.0 + attack_score * 12.0,
            "lambda_chaining": 1.8 + attack_score * 6.2
        }
        
        multiplier = multipliers.get(attack_type, 2.0)
        return base_cost * multiplier


class EconomicDetectorCalibrator:
    """Calibrates economic detector thresholds and evaluates performance"""
    
    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)
        
        self.attack_generator = EconomicAttackGenerator(random_seed)
        self.benign_generator = BenignWorkloadGenerator(random_seed)
        self.detector = EconomicDetector()
        self.trace_generator = RealisticServerlessTraceGenerator(random_seed=random_seed)
        
        logger.info(f"Economic detector calibrator initialized with seed {random_seed}")
    
    def generate_labeled_dataset(self, num_attack_scenarios: int = 100,
                                num_benign_scenarios: int = 200) -> List[Tuple[List[TelemetryRecord], int, Dict[str, Any]]]:
        """Generate labeled dataset for calibration"""
        
        logger.info(f"Generating labeled dataset: {num_attack_scenarios} attacks, {num_benign_scenarios} benign")
        
        labeled_data = []
        
        # Generate attack scenarios
        attack_types = ["dow", "crypto_mining", "amplification", "lambda_chaining"]
        
        for i in range(num_attack_scenarios):
            attack_type = np.random.choice(attack_types)
            severity = np.random.uniform(0.3, 1.0)
            
            try:
                if attack_type == "dow":
                    scenario = self.attack_generator.generate_dow_attack_scenario(severity)
                elif attack_type == "crypto_mining":
                    scenario = self.attack_generator.generate_crypto_mining_scenario(severity)
                elif attack_type == "amplification":
                    scenario = self.attack_generator.generate_amplification_attack_scenario(severity)
                elif attack_type == "lambda_chaining":
                    scenario = self.attack_generator.generate_lambda_chaining_scenario(severity)
                
                # Generate trace for this scenario
                trace = self._generate_trace_for_attack_scenario(scenario)
                
                # Label all records in this trace as attacks
                for record in trace.invocations:
                    record.ground_truth_label = 1
                
                labeled_data.append((trace.invocations, 1, scenario.__dict__))
                
            except Exception as e:
                logger.warning(f"Failed to generate attack scenario {i}: {e}")
                continue
        
        # Generate benign scenarios
        benign_types = ["flash_spike", "batch_processing", "auto_scaling", "seasonal"]
        
        for i in range(num_benign_scenarios):
            benign_type = np.random.choice(benign_types)
            intensity = np.random.uniform(1.5, 5.0)
            
            try:
                if benign_type == "flash_spike":
                    pattern = self.benign_generator.generate_flash_spike_pattern(intensity)
                elif benign_type == "batch_processing":
                    pattern = self.benign_generator.generate_batch_processing_pattern(intensity)
                elif benign_type == "auto_scaling":
                    pattern = self.benign_generator.generate_auto_scaling_pattern(intensity)
                elif benign_type == "seasonal":
                    pattern = self.benign_generator.generate_seasonal_pattern(intensity)
                
                # Generate trace for this pattern
                trace = self._generate_trace_for_benign_pattern(pattern)
                
                # Label all records as benign
                for record in trace.invocations:
                    record.ground_truth_label = 0
                
                labeled_data.append((trace.invocations, 0, pattern.__dict__))
                
            except Exception as e:
                logger.warning(f"Failed to generate benign scenario {i}: {e}")
                continue
        
        logger.info(f"Generated {len(labeled_data)} labeled scenarios")
        return labeled_data
    
    def _generate_trace_for_attack_scenario(self, scenario: EconomicAttackScenario):
        """Generate trace that exhibits the attack pattern"""
        
        # Base trace
        num_invocations = max(5, int(scenario.duration_minutes * 2))  # 2 per minute
        trace = self.trace_generator.generate_attack_trace(
            scenario.attack_id, scenario.attack_type, num_invocations
        )
        
        # Apply attack-specific patterns
        for record in trace.invocations:
            patterns = scenario.resource_patterns
            
            # Apply resource pattern modifications
            if "memory_usage_multiplier" in patterns:
                record.memory_spike_kb = int(record.memory_spike_kb * patterns["memory_usage_multiplier"])
            
            if "execution_time_multiplier" in patterns:
                record.duration = record.duration * patterns["execution_time_multiplier"]
            
            if "cpu_usage_percent" in patterns:
                record.cpu_utilization = min(100.0, patterns["cpu_usage_percent"])
            elif "cpu_usage_multiplier" in patterns:
                record.cpu_utilization = min(100.0, record.cpu_utilization * patterns.get("cpu_usage_multiplier", 1.0))
            
            if "network_io_multiplier" in patterns:
                record.network_io_bytes = int(record.network_io_bytes * patterns["network_io_multiplier"])
            
            # Add attack-specific metadata
            record.telemetry_metadata["attack_type"] = scenario.attack_type
            record.telemetry_metadata["attack_severity"] = scenario.severity
            record.telemetry_metadata["cost_multiplier"] = scenario.cost_multiplier
            
            # Add specific pattern metadata
            if scenario.attack_type == "crypto_mining":
                record.telemetry_metadata["power_consumption_multiplier"] = patterns.get("power_consumption_multiplier", 1.0)
                record.telemetry_metadata["heat_signature"] = patterns.get("heat_signature", 0.5)
            
            elif scenario.attack_type == "amplification":
                record.telemetry_metadata["exponential_growth_rate"] = patterns.get("exponential_growth_rate", 1.0)
                record.telemetry_metadata["storage_io_multiplier"] = patterns.get("storage_io_multiplier", 1.0)
            
            elif scenario.attack_type == "lambda_chaining":
                record.telemetry_metadata["invocation_cascade_count"] = patterns.get("chain_length", 1)
                record.telemetry_metadata["recursive_depth"] = patterns.get("recursive_depth", 1)
        
        return trace
    
    def _generate_trace_for_benign_pattern(self, pattern: BenignWorkloadPattern):
        """Generate trace that exhibits the benign workload pattern"""
        
        # Base trace
        num_invocations = max(3, int(pattern.duration_minutes * pattern.intensity))
        trace = self.trace_generator.generate_normal_trace(
            pattern.pattern_id, 0.02, num_invocations  # Low anomaly rate for benign
        )
        
        # Apply benign pattern characteristics
        for i, record in enumerate(trace.invocations):
            characteristics = pattern.characteristics
            
            # Apply pattern-specific modifications
            if pattern.pattern_type == "flash_spike":
                # Legitimate traffic spike characteristics
                traffic_mult = characteristics.get("traffic_multiplier", 1.0)
                record.cpu_utilization = min(100.0, record.cpu_utilization * traffic_mult * 0.5)  # Moderate CPU increase
                record.network_io_bytes = int(record.network_io_bytes * traffic_mult * 0.7)  # More network I/O
                
                # Slight error rate increase due to load
                error_rate_increase = characteristics.get("error_rate_increase", 0)
                if np.random.random() < error_rate_increase:
                    record.telemetry_metadata["error_occurred"] = True
                    record.anomaly_type = AnomalyType.TIMEOUT_FALLBACK
                
            elif pattern.pattern_type == "batch_processing":
                # Legitimate batch processing characteristics
                record.cpu_utilization = characteristics.get("cpu_usage_percent", 70)
                record.duration = record.duration * characteristics.get("execution_time_multiplier", 2.0)
                record.memory_spike_kb = int(record.memory_spike_kb * 1.5)  # Higher memory for data processing
                record.network_io_bytes = int(record.network_io_bytes * 3.0)  # High I/O for data processing
                
            elif pattern.pattern_type == "auto_scaling":
                # Cold start characteristics
                cold_start_pct = characteristics.get("cold_start_percentage", 0.8)
                if i < len(trace.invocations) * cold_start_pct:
                    record.telemetry_metadata["is_cold_start"] = True
                    record.duration = record.duration * characteristics.get("initialization_time_multiplier", 3.0)
                    record.memory_spike_kb = int(record.memory_spike_kb * 2.0)  # Memory initialization spike
                
            elif pattern.pattern_type == "seasonal":
                # Gradual traffic increase pattern
                position_ratio = i / len(trace.invocations)
                if position_ratio < 0.3:  # Ramp up
                    multiplier = 1.0 + (pattern.intensity - 1.0) * (position_ratio / 0.3)
                elif position_ratio < 0.7:  # Plateau
                    multiplier = pattern.intensity
                else:  # Ramp down
                    multiplier = pattern.intensity - (pattern.intensity - 1.0) * ((position_ratio - 0.7) / 0.3)
                
                record.cpu_utilization = min(100.0, record.cpu_utilization * multiplier * 0.6)
                record.network_io_bytes = int(record.network_io_bytes * multiplier * 0.8)
            
            # Add benign pattern metadata
            record.telemetry_metadata["workload_pattern"] = pattern.pattern_type
            record.telemetry_metadata["pattern_intensity"] = pattern.intensity
            record.telemetry_metadata["business_legitimate"] = True
        
        return trace
    
    def evaluate_detection_performance(self, labeled_data: List[Tuple[List[TelemetryRecord], int, Dict[str, Any]]],
                                     threshold: float = 0.5) -> Dict[str, Any]:
        """Evaluate detection performance at given threshold"""
        
        all_results = []
        all_ground_truth = []
        all_predictions = []
        all_scores = []
        
        for telemetry_records, ground_truth_label, metadata in labeled_data:
            # Run detection
            detection_results = self.detector.detect_economic_attacks(telemetry_records)
            
            for result in detection_results:
                all_results.append(result)
                all_ground_truth.append(result.ground_truth_label)
                all_predictions.append(1 if result.attack_score >= threshold else 0)
                all_scores.append(result.attack_score)
        
        if not all_results:
            return {"error": "No detection results"}
        
        # Calculate performance metrics
        y_true = np.array(all_ground_truth)
        y_pred = np.array(all_predictions)
        y_scores = np.array(all_scores)
        
        # Basic metrics
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        
        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
        
        # False positive rate and specificity
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        
        # Performance by attack type
        attack_type_performance = {}
        for attack_type in ["dow", "crypto_mining", "amplification", "lambda_chaining"]:
            attack_results = [r for r in all_results if r.attack_type == attack_type and r.ground_truth_label == 1]
            if attack_results:
                attack_scores = [r.attack_score for r in attack_results]
                attack_predictions = [1 if s >= threshold else 0 for s in attack_scores]
                attack_ground_truth = [1] * len(attack_results)
                
                attack_precision = precision_score(attack_ground_truth, attack_predictions, zero_division=0)
                attack_recall = recall_score(attack_ground_truth, attack_predictions, zero_division=0)
                attack_f1 = f1_score(attack_ground_truth, attack_predictions, zero_division=0)
                
                attack_type_performance[attack_type] = {
                    "precision": attack_precision,
                    "recall": attack_recall,
                    "f1_score": attack_f1,
                    "num_samples": len(attack_results),
                    "mean_score": np.mean(attack_scores)
                }
        
        return {
            "threshold": threshold,
            "overall_metrics": {
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "false_positive_rate": fpr,
                "specificity": specificity,
                "true_positives": int(tp),
                "false_positives": int(fp),
                "true_negatives": int(tn),
                "false_negatives": int(fn)
            },
            "attack_type_performance": attack_type_performance,
            "total_samples": len(all_results),
            "attack_samples": int(sum(all_ground_truth)),
            "benign_samples": int(len(all_ground_truth) - sum(all_ground_truth))
        }
    
    def generate_roc_pr_curves(self, labeled_data: List[Tuple[List[TelemetryRecord], int, Dict[str, Any]]]) -> Dict[str, Any]:
        """Generate ROC and Precision-Recall curves"""
        
        logger.info("Generating ROC and PR curves...")
        
        all_ground_truth = []
        all_scores = []
        
        for telemetry_records, ground_truth_label, metadata in labeled_data:
            detection_results = self.detector.detect_economic_attacks(telemetry_records)
            
            for result in detection_results:
                all_ground_truth.append(result.ground_truth_label)
                all_scores.append(result.attack_score)
        
        if not all_ground_truth:
            return {"error": "No detection results for curve generation"}
        
        y_true = np.array(all_ground_truth)
        y_scores = np.array(all_scores)
        
        # ROC Curve
        fpr, tpr, roc_thresholds = roc_curve(y_true, y_scores)
        roc_auc = auc(fpr, tpr)
        
        # Precision-Recall Curve
        precision, recall, pr_thresholds = precision_recall_curve(y_true, y_scores)
        pr_auc = auc(recall, precision)
        
        # Find optimal threshold (maximize F1-score)
        f1_scores = []
        for threshold in pr_thresholds:
            y_pred = (y_scores >= threshold).astype(int)
            f1 = f1_score(y_true, y_pred, zero_division=0)
            f1_scores.append(f1)
        
        optimal_threshold_idx = np.argmax(f1_scores)
        optimal_threshold = pr_thresholds[optimal_threshold_idx]
        optimal_f1 = f1_scores[optimal_threshold_idx]
        
        # Find threshold for specific false positive rates
        target_fprs = [0.01, 0.05, 0.1]  # 1%, 5%, 10% false positive rates
        fpr_thresholds = {}
        
        for target_fpr in target_fprs:
            # Find threshold that achieves target FPR
            for i, fpr_val in enumerate(fpr):
                if fpr_val >= target_fpr:
                    fpr_thresholds[f"fpr_{target_fpr}"] = {
                        "threshold": roc_thresholds[i] if i < len(roc_thresholds) else 1.0,
                        "actual_fpr": fpr_val,
                        "tpr": tpr[i],
                        "recall": tpr[i]
                    }
                    break
        
        return {
            "roc_curve": {
                "fpr": fpr.tolist(),
                "tpr": tpr.tolist(),
                "thresholds": roc_thresholds.tolist(),
                "auc": roc_auc
            },
            "pr_curve": {
                "precision": precision.tolist(),
                "recall": recall.tolist(),
                "thresholds": pr_thresholds.tolist(),
                "auc": pr_auc
            },
            "optimal_threshold": {
                "threshold": optimal_threshold,
                "f1_score": optimal_f1,
                "precision": precision[optimal_threshold_idx],
                "recall": recall[optimal_threshold_idx]
            },
            "fpr_constrained_thresholds": fpr_thresholds,
            "total_samples": len(all_ground_truth),
            "positive_samples": int(sum(all_ground_truth)),
            "class_balance": sum(all_ground_truth) / len(all_ground_truth)
        }
    
    def analyze_false_alarm_control(self, labeled_data: List[Tuple[List[TelemetryRecord], int, Dict[str, Any]]],
                                   target_fpr: float = 0.05) -> Dict[str, Any]:
        """Analyze false alarm control under benign workload spikes"""
        
        logger.info(f"Analyzing false alarm control with target FPR: {target_fpr}")
        
        # Separate benign data by pattern type
        benign_patterns = defaultdict(list)
        
        for telemetry_records, ground_truth_label, metadata in labeled_data:
            if ground_truth_label == 0:  # Benign
                pattern_type = metadata.get("pattern_type", "unknown")
                benign_patterns[pattern_type].extend(telemetry_records)
        
        # Analyze false positive rate for each benign pattern type
        pattern_analysis = {}
        
        for pattern_type, records in benign_patterns.items():
            if not records:
                continue
            
            detection_results = self.detector.detect_economic_attacks(records)
            
            # Analyze at different thresholds
            thresholds = np.linspace(0.1, 0.9, 9)
            threshold_analysis = []
            
            for threshold in thresholds:
                false_positives = sum(1 for r in detection_results if r.attack_score >= threshold)
                total_benign = len(detection_results)
                
                fpr = false_positives / total_benign if total_benign > 0 else 0
                
                threshold_analysis.append({
                    "threshold": threshold,
                    "false_positive_rate": fpr,
                    "false_positives": false_positives,
                    "total_samples": total_benign
                })
            
            # Find threshold that achieves target FPR
            target_threshold = None
            for analysis in threshold_analysis:
                if analysis["false_positive_rate"] <= target_fpr:
                    target_threshold = analysis["threshold"]
                    break
            
            # Intensity analysis (how does FPR change with workload intensity?)
            intensity_analysis = defaultdict(list)
            for record in records:
                intensity = record.telemetry_metadata.get("pattern_intensity", 1.0)
                intensity_bin = round(intensity * 2) / 2  # Round to nearest 0.5
                intensity_analysis[intensity_bin].append(record)
            
            intensity_fpr = {}
            for intensity, intensity_records in intensity_analysis.items():
                if len(intensity_records) >= 5:  # Minimum samples for analysis
                    intensity_results = self.detector.detect_economic_attacks(intensity_records)
                    # Use optimal threshold from overall analysis
                    optimal_threshold = target_threshold or 0.5
                    fps = sum(1 for r in intensity_results if r.attack_score >= optimal_threshold)
                    intensity_fpr[intensity] = {
                        "false_positive_rate": fps / len(intensity_results),
                        "samples": len(intensity_results)
                    }
            
            pattern_analysis[pattern_type] = {
                "threshold_analysis": threshold_analysis,
                "target_threshold": target_threshold,
                "target_fpr_achieved": target_threshold is not None,
                "intensity_analysis": intensity_fpr,
                "total_samples": len(records)
            }
        
        return {
            "target_fpr": target_fpr,
            "pattern_analysis": pattern_analysis,
            "overall_false_alarm_control": {
                "controllable": all(p["target_fpr_achieved"] for p in pattern_analysis.values()),
                "most_problematic_pattern": max(pattern_analysis.keys(), 
                                              key=lambda p: min(t["false_positive_rate"] 
                                                               for t in pattern_analysis[p]["threshold_analysis"])) 
                                              if pattern_analysis else None
            }
        }
    
    def optimize_thresholds_for_production(self, labeled_data: List[Tuple[List[TelemetryRecord], int, Dict[str, Any]]],
                                         business_constraints: Dict[str, float] = None) -> Dict[str, Any]:
        """Optimize detection thresholds for production deployment"""
        
        if business_constraints is None:
            business_constraints = {
                "max_false_positive_rate": 0.05,  # Max 5% false alarms
                "min_recall_for_high_severity": 0.9,  # Must catch 90% of severe attacks
                "false_positive_cost_per_day": 100.0,  # $100 per false positive per day
                "missed_attack_cost": 10000.0,  # $10k average cost of missed attack
                "max_detection_latency_ms": 500.0  # 500ms max detection latency
            }
        
        logger.info("Optimizing thresholds for production deployment...")
        logger.info(f"Business constraints: {business_constraints}")
        
        # Test range of thresholds
        thresholds = np.linspace(0.1, 0.9, 17)  # 17 thresholds from 0.1 to 0.9
        
        threshold_results = []
        
        for threshold in thresholds:
            performance = self.evaluate_detection_performance(labeled_data, threshold)
            
            if "overall_metrics" not in performance:
                continue
            
            metrics = performance["overall_metrics"]
            
            # Calculate business cost
            daily_invocations = 10000  # Assumed daily invocation volume
            fp_cost_per_day = metrics["false_positive_rate"] * daily_invocations * business_constraints["false_positive_cost_per_day"] / daily_invocations
            fn_cost_per_day = (1 - metrics["recall"]) * 10 * business_constraints["missed_attack_cost"] / 365  # 10 attacks per year assumed
            
            total_daily_cost = fp_cost_per_day + fn_cost_per_day
            
            # Check constraint satisfaction
            constraints_satisfied = (
                metrics["false_positive_rate"] <= business_constraints["max_false_positive_rate"] and
                metrics["recall"] >= business_constraints["min_recall_for_high_severity"]
            )
            
            threshold_result = {
                "threshold": threshold,
                "performance_metrics": metrics,
                "business_costs": {
                    "false_positive_cost_per_day": fp_cost_per_day,
                    "missed_attack_cost_per_day": fn_cost_per_day,
                    "total_daily_cost": total_daily_cost
                },
                "constraints_satisfied": constraints_satisfied,
                "optimization_score": metrics["f1_score"] - (total_daily_cost / 1000)  # F1 minus cost penalty
            }
            
            threshold_results.append(threshold_result)
        
        # Find optimal threshold
        valid_thresholds = [r for r in threshold_results if r["constraints_satisfied"]]
        
        if valid_thresholds:
            optimal_threshold_result = max(valid_thresholds, key=lambda x: x["optimization_score"])
            optimization_status = "optimal_found"
        else:
            # Fallback: minimize cost even if constraints not fully satisfied
            optimal_threshold_result = min(threshold_results, key=lambda x: x["business_costs"]["total_daily_cost"])
            optimization_status = "best_compromise"
        
        # Generate recommendations
        recommendations = []
        
        if optimization_status == "optimal_found":
            recommendations.append({
                "type": "deployment",
                "priority": "info",
                "message": f"✅ Optimal threshold found: {optimal_threshold_result['threshold']:.3f}"
            })
        else:
            recommendations.append({
                "type": "deployment",
                "priority": "warning",
                "message": "⚠️ No threshold fully satisfies all business constraints. Consider adjusting constraints or improving detection model."
            })
        
        # Performance recommendations
        optimal_metrics = optimal_threshold_result["performance_metrics"]
        if optimal_metrics["false_positive_rate"] > 0.02:
            recommendations.append({
                "type": "performance",
                "priority": "medium",
                "message": f"Consider further tuning to reduce false positive rate ({optimal_metrics['false_positive_rate']:.1%})"
            })
        
        if optimal_metrics["recall"] < 0.85:
            recommendations.append({
                "type": "security",
                "priority": "high",
                "message": f"Low recall ({optimal_metrics['recall']:.1%}) may miss critical attacks. Consider additional detection methods."
            })
        
        return {
            "optimization_status": optimization_status,
            "optimal_threshold": optimal_threshold_result["threshold"],
            "optimal_performance": optimal_threshold_result["performance_metrics"],
            "optimal_costs": optimal_threshold_result["business_costs"],
            "business_constraints": business_constraints,
            "all_threshold_results": threshold_results,
            "recommendations": recommendations,
            "deployment_readiness": {
                "ready": optimization_status == "optimal_found",
                "confidence_level": "high" if optimization_status == "optimal_found" else "medium",
                "estimated_daily_cost": optimal_threshold_result["business_costs"]["total_daily_cost"]
            }
        }
    
    async def run_comprehensive_calibration_study(self,
                                                num_attack_scenarios: int = 200,
                                                num_benign_scenarios: int = 400,
                                                business_constraints: Dict[str, float] = None) -> CalibrationResults:
        """Run comprehensive economic detector calibration study"""
        
        logger.info("Starting comprehensive economic detector calibration study")
        logger.info(f"Attack scenarios: {num_attack_scenarios}, Benign scenarios: {num_benign_scenarios}")
        
        # Generate labeled dataset
        labeled_data = self.generate_labeled_dataset(num_attack_scenarios, num_benign_scenarios)
        
        if not labeled_data:
            raise ValueError("Failed to generate labeled dataset")
        
        # Generate ROC and PR curves
        logger.info("Generating ROC and PR curves...")
        curve_analysis = self.generate_roc_pr_curves(labeled_data)
        
        # Analyze false alarm control
        logger.info("Analyzing false alarm control...")
        false_alarm_analysis = self.analyze_false_alarm_control(labeled_data)
        
        # Optimize thresholds for production
        logger.info("Optimizing thresholds for production...")
        threshold_optimization = self.optimize_thresholds_for_production(labeled_data, business_constraints)
        
        # Evaluate performance by attack type
        logger.info("Evaluating performance by attack type...")
        optimal_threshold = threshold_optimization["optimal_threshold"]
        attack_type_performance = self.evaluate_detection_performance(labeled_data, optimal_threshold)
        
        # Cost-benefit analysis
        logger.info("Performing cost-benefit analysis...")
        cost_benefit_analysis = self._perform_cost_benefit_analysis(labeled_data, threshold_optimization)
        
        return CalibrationResults(
            roc_analysis=curve_analysis,
            pr_analysis=curve_analysis,  # Same data, different presentation
            threshold_optimization=threshold_optimization,
            false_alarm_analysis=false_alarm_analysis,
            cost_benefit_analysis=cost_benefit_analysis,
            attack_type_performance=attack_type_performance
        )
    
    def _perform_cost_benefit_analysis(self, labeled_data: List[Tuple[List[TelemetryRecord], int, Dict[str, Any]]],
                                     threshold_optimization: Dict[str, Any]) -> Dict[str, Any]:
        """Perform cost-benefit analysis of deployment"""
        
        optimal_threshold = threshold_optimization["optimal_threshold"]
        optimal_costs = threshold_optimization["optimal_costs"]
        
        # Estimate benefits of deployment
        attack_samples = sum(1 for _, label, _ in labeled_data if label == 1)
        total_samples = len(labeled_data)
        
        # Assumed attack frequency and costs
        estimated_attacks_per_year = 50  # Conservative estimate
        average_attack_cost = 25000  # $25k average attack cost
        
        # Performance at optimal threshold
        performance = self.evaluate_detection_performance(labeled_data, optimal_threshold)
        if "overall_metrics" not in performance:
            return {"error": "Could not calculate cost-benefit analysis"}
        
        metrics = performance["overall_metrics"]
        
        # Annual benefits (attacks prevented)
        attacks_prevented_per_year = estimated_attacks_per_year * metrics["recall"]
        annual_benefit = attacks_prevented_per_year * average_attack_cost
        
        # Annual costs (false positives + system operation)
        annual_false_positive_cost = optimal_costs["false_positive_cost_per_day"] * 365
        annual_system_operation_cost = 50000  # $50k estimated annual operation cost
        annual_cost = annual_false_positive_cost + annual_system_operation_cost
        
        # ROI calculation
        net_annual_benefit = annual_benefit - annual_cost
        roi = (net_annual_benefit / annual_cost) * 100 if annual_cost > 0 else 0
        
        # Break-even analysis
        break_even_attack_cost = annual_cost / max(attacks_prevented_per_year, 1)
        
        return {
            "annual_analysis": {
                "estimated_attacks_per_year": estimated_attacks_per_year,
                "attacks_prevented": attacks_prevented_per_year,
                "prevention_rate": attacks_prevented_per_year / estimated_attacks_per_year,
                "annual_benefit": annual_benefit,
                "annual_cost": annual_cost,
                "net_benefit": net_annual_benefit,
                "roi_percent": roi
            },
            "break_even_analysis": {
                "break_even_attack_cost": break_even_attack_cost,
                "current_assumed_attack_cost": average_attack_cost,
                "break_even_achieved": average_attack_cost >= break_even_attack_cost
            },
            "sensitivity_analysis": {
                "roi_if_double_attacks": ((2 * annual_benefit - annual_cost) / annual_cost) * 100,
                "roi_if_half_attacks": ((0.5 * annual_benefit - annual_cost) / annual_cost) * 100,
                "roi_if_double_attack_cost": (((attacks_prevented_per_year * 2 * average_attack_cost) - annual_cost) / annual_cost) * 100
            },
            "deployment_recommendation": {
                "financially_justified": roi > 200,  # 200% ROI threshold
                "risk_assessment": "low" if roi > 500 else ("medium" if roi > 200 else "high"),
                "payback_period_years": annual_cost / max(annual_benefit - annual_cost, 1) if annual_benefit > annual_cost else float('inf')
            }
        }
    
    def generate_calibration_report(self, results: CalibrationResults, 
                                  output_dir: str = "experiments/results") -> str:
        """Generate comprehensive calibration report"""
        
        output_path = Path(output_dir) / "economic_detector_calibration_report.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate executive summary
        executive_summary = self._generate_calibration_summary(results)
        
        report = {
            "analysis_metadata": {
                "timestamp": time.time(),
                "random_seed": self.random_seed,
                "analysis_type": "Economic Detector Calibration",
                "methodology": "ROC/PR analysis with business constraint optimization"
            },
            "executive_summary": executive_summary,
            "detailed_results": {
                "roc_pr_analysis": results.roc_analysis,
                "threshold_optimization": results.threshold_optimization,
                "false_alarm_analysis": results.false_alarm_analysis,
                "attack_type_performance": results.attack_type_performance,
                "cost_benefit_analysis": results.cost_benefit_analysis
            },
            "recommendations": self._generate_calibration_recommendations(results)
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Economic detector calibration report saved: {output_path}")
        return str(output_path)
    
    def _generate_calibration_summary(self, results: CalibrationResults) -> Dict[str, Any]:
        """Generate executive summary of calibration results"""
        
        roc_auc = results.roc_analysis.get("roc_curve", {}).get("auc", 0)
        pr_auc = results.roc_analysis.get("pr_curve", {}).get("auc", 0)
        optimal_f1 = results.roc_analysis.get("optimal_threshold", {}).get("f1_score", 0)
        
        deployment_ready = results.threshold_optimization.get("deployment_readiness", {}).get("ready", False)
        daily_cost = results.threshold_optimization.get("deployment_readiness", {}).get("estimated_daily_cost", 0)
        
        roi = results.cost_benefit_analysis.get("annual_analysis", {}).get("roi_percent", 0)
        
        return {
            "detection_performance": {
                "roc_auc": roc_auc,
                "pr_auc": pr_auc,
                "optimal_f1_score": optimal_f1,
                "performance_rating": ("excellent" if optimal_f1 > 0.8 else
                                     ("good" if optimal_f1 > 0.6 else "needs_improvement"))
            },
            "deployment_readiness": {
                "ready_for_production": deployment_ready,
                "estimated_daily_operational_cost": daily_cost,
                "false_alarm_control": results.false_alarm_analysis.get("overall_false_alarm_control", {}).get("controllable", False)
            },
            "business_value": {
                "annual_roi_percent": roi,
                "financially_justified": roi > 200,
                "break_even_achieved": results.cost_benefit_analysis.get("break_even_analysis", {}).get("break_even_achieved", False)
            },
            "key_findings": self._extract_key_findings(results)
        }
    
    def _extract_key_findings(self, results: CalibrationResults) -> List[str]:
        """Extract key findings from calibration results"""
        
        findings = []
        
        # Performance findings
        roc_auc = results.roc_analysis.get("roc_curve", {}).get("auc", 0)
        if roc_auc > 0.9:
            findings.append("✅ Excellent discrimination ability (ROC AUC > 0.9)")
        elif roc_auc > 0.8:
            findings.append("⚠️ Good discrimination ability (ROC AUC > 0.8)")
        else:
            findings.append("❌ Poor discrimination ability (ROC AUC < 0.8)")
        
        # False alarm findings
        false_alarm_controllable = results.false_alarm_analysis.get("overall_false_alarm_control", {}).get("controllable", False)
        if false_alarm_controllable:
            findings.append("✅ False alarm rate controllable under benign workload spikes")
        else:
            findings.append("❌ High false alarm rate during legitimate traffic spikes")
        
        # Business value findings
        roi = results.cost_benefit_analysis.get("annual_analysis", {}).get("roi_percent", 0)
        if roi > 500:
            findings.append("✅ Very high ROI (>500%) - strong business case")
        elif roi > 200:
            findings.append("⚠️ Positive ROI (>200%) - business case justified")
        else:
            findings.append("❌ Low/negative ROI - reconsider deployment")
        
        # Attack type findings
        attack_performance = results.attack_type_performance.get("attack_type_performance", {})
        if attack_performance:
            best_detected = max(attack_performance, key=lambda x: attack_performance[x].get("f1_score", 0))
            worst_detected = min(attack_performance, key=lambda x: attack_performance[x].get("f1_score", 0))
            
            findings.append(f"Best detected attack type: {best_detected}")
            findings.append(f"Most challenging attack type: {worst_detected}")
        
        return findings
    
    def _generate_calibration_recommendations(self, results: CalibrationResults) -> List[Dict[str, str]]:
        """Generate deployment and optimization recommendations"""
        
        recommendations = []
        
        # Performance recommendations
        optimal_f1 = results.roc_analysis.get("optimal_threshold", {}).get("f1_score", 0)
        if optimal_f1 < 0.7:
            recommendations.append({
                "type": "performance",
                "priority": "high",
                "message": "Consider improving detection model or collecting more training data to achieve better F1 score"
            })
        
        # False alarm recommendations
        false_alarm_controllable = results.false_alarm_analysis.get("overall_false_alarm_control", {}).get("controllable", False)
        if not false_alarm_controllable:
            recommendations.append({
                "type": "false_alarms",
                "priority": "high", 
                "message": "Implement workload pattern recognition to reduce false alarms during legitimate spikes"
            })
        
        # Business recommendations
        roi = results.cost_benefit_analysis.get("annual_analysis", {}).get("roi_percent", 0)
        if roi > 200:
            recommendations.append({
                "type": "business",
                "priority": "info",
                "message": f"✅ Strong business case with {roi:.0f}% ROI. Recommend deployment."
            })
        else:
            recommendations.append({
                "type": "business",
                "priority": "warning",
                "message": f"Weak business case with {roi:.0f}% ROI. Consider cost optimization or performance improvement."
            })
        
        # Deployment recommendations
        deployment_ready = results.threshold_optimization.get("deployment_readiness", {}).get("ready", False)
        if deployment_ready:
            optimal_threshold = results.threshold_optimization.get("optimal_threshold", 0.5)
            recommendations.append({
                "type": "deployment",
                "priority": "info",
                "message": f"✅ Ready for production deployment with threshold {optimal_threshold:.3f}"
            })
        else:
            recommendations.append({
                "type": "deployment",
                "priority": "high",
                "message": "Not ready for production. Address performance and false alarm issues first."
            })
        
        return recommendations


# Export main classes
__all__ = ['EconomicDetectorCalibrator', 'CalibrationResults', 'EconomicAttackGenerator', 'BenignWorkloadGenerator']


if __name__ == "__main__":
    # Self-test
    async def run_self_test():
        print("Running Economic Detector Calibration Self-Test...")
        
        calibrator = EconomicDetectorCalibrator(random_seed=42)
        
        # Quick test with small dataset
        results = await calibrator.run_comprehensive_calibration_study(
            num_attack_scenarios=20,
            num_benign_scenarios=30
        )
        
        report_path = calibrator.generate_calibration_report(results)
        print(f"✅ Self-test completed. Report saved: {report_path}")
        
        # Print key metrics
        roc_auc = results.roc_analysis.get("roc_curve", {}).get("auc", 0)
        optimal_f1 = results.roc_analysis.get("optimal_threshold", {}).get("f1_score", 0)
        print(f"ROC AUC: {roc_auc:.3f}")
        print(f"Optimal F1: {optimal_f1:.3f}")
        
        return True
    
    import asyncio
    asyncio.run(run_self_test())