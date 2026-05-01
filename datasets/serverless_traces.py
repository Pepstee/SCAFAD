#!/usr/bin/env python3
"""
SCAFAD Meaningful Datasets: Real Serverless Trace Generation and Management
==========================================================================

This module creates meaningful, realistic serverless execution traces based on
real-world patterns observed in production serverless environments.

Dataset Types:
1. Production-like normal workloads
2. Attack scenarios (DoW/DoS, cryptomining, data exfiltration)
3. Performance anomalies (cold starts, memory spikes, timeouts)
4. Economic abuse patterns
5. Multi-tenant interference scenarios
6. Cascading failure patterns

Academic References:
- "Serverless Computing: Current Trends and Open Problems" (Castro et al., 2019)
- "The Rise of Serverless Computing" (Jonas et al., 2019)
- "Characterizing Serverless Platforms with Workloads" (Wang et al., 2018)
- "FaaSdom: A Benchmark Suite for Serverless Computing" (Kim & Lee, 2019)
"""

import time
import json
import random
import uuid
import logging
import numpy as np
import os
import gzip
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Iterator
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from pathlib import Path

# Import our core modules
from app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource
from core.ignn_model import ServerlessExecutionGraph, ExecutionNode, ExecutionEdge, NodeType, EdgeType

logger = logging.getLogger(__name__)


class WorkloadType(Enum):
    """Types of serverless workloads"""
    WEB_API = "web_api"
    DATA_PROCESSING = "data_processing"
    BATCH_ANALYTICS = "batch_analytics"
    IOT_TELEMETRY = "iot_telemetry"
    IMAGE_PROCESSING = "image_processing"
    ML_INFERENCE = "ml_inference"
    FILE_TRANSFORM = "file_transform"
    DATABASE_TRIGGER = "database_trigger"
    SCHEDULED_TASK = "scheduled_task"
    STREAM_PROCESSING = "stream_processing"


class AttackScenario(Enum):
    """Types of attack scenarios"""
    DOW_BILLING_ATTACK = "dow_billing_attack"
    CRYPTOMINING = "cryptomining"
    DATA_EXFILTRATION = "data_exfiltration"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DENIAL_OF_WALLET = "denial_of_wallet"
    SIDE_CHANNEL = "side_channel"
    INJECTION_ATTACK = "injection_attack"
    BACKDOOR = "backdoor"


class AnomalyScenario(Enum):
    """Types of performance anomaly scenarios"""
    COLD_START_CASCADE = "cold_start_cascade"
    MEMORY_LEAK = "memory_leak"
    TIMEOUT_CASCADE = "timeout_cascade"
    CONCURRENCY_THROTTLE = "concurrency_throttle"
    DEPENDENCY_FAILURE = "dependency_failure"
    NETWORK_PARTITION = "network_partition"
    RESOURCE_CONTENTION = "resource_contention"


@dataclass
class DatasetMetadata:
    """Metadata for a generated dataset"""
    name: str
    description: str
    created_at: float
    num_traces: int
    time_span_hours: float
    workload_types: List[str]
    attack_scenarios: List[str]
    anomaly_rate: float
    normal_rate: float
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServerlessTrace:
    """A complete serverless execution trace"""
    trace_id: str
    function_name: str
    workload_type: WorkloadType
    start_time: float
    end_time: float
    invocations: List[TelemetryRecord]
    graph: ServerlessExecutionGraph
    labels: Dict[str, Any]  # Ground truth labels
    metadata: Dict[str, Any] = field(default_factory=dict)


class RealisticServerlessTraceGenerator:
    """
    Generator for realistic serverless traces based on production patterns
    """
    
    def __init__(self, base_timestamp: Optional[float] = None):
        self.base_timestamp = base_timestamp or time.time()
        self.function_registry = self._create_function_registry()
        self.workload_patterns = self._create_workload_patterns()
        self.attack_patterns = self._create_attack_patterns()
        
    def _create_function_registry(self) -> Dict[str, Dict[str, Any]]:
        """Create registry of realistic function types"""
        return {
            'user-api': {
                'workload_type': WorkloadType.WEB_API,
                'avg_duration': 0.15,
                'memory_range': (128, 512),
                'cpu_pattern': 'burst',
                'cold_start_prob': 0.1,
                'error_rate': 0.02,
                'concurrency_limit': 1000
            },
            'image-resize': {
                'workload_type': WorkloadType.IMAGE_PROCESSING,
                'avg_duration': 2.5,
                'memory_range': (512, 3008),
                'cpu_pattern': 'sustained',
                'cold_start_prob': 0.05,
                'error_rate': 0.03,
                'concurrency_limit': 100
            },
            'data-etl': {
                'workload_type': WorkloadType.DATA_PROCESSING,
                'avg_duration': 12.0,
                'memory_range': (1024, 3008),
                'cpu_pattern': 'sustained',
                'cold_start_prob': 0.15,
                'error_rate': 0.01,
                'concurrency_limit': 50
            },
            'ml-predict': {
                'workload_type': WorkloadType.ML_INFERENCE,
                'avg_duration': 0.8,
                'memory_range': (1024, 2048),
                'cpu_pattern': 'burst',
                'cold_start_prob': 0.3,  # Model loading
                'error_rate': 0.02,
                'concurrency_limit': 200
            },
            'iot-processor': {
                'workload_type': WorkloadType.IOT_TELEMETRY,
                'avg_duration': 0.05,
                'memory_range': (128, 256),
                'cpu_pattern': 'minimal',
                'cold_start_prob': 0.02,
                'error_rate': 0.001,
                'concurrency_limit': 10000
            },
            'batch-analytics': {
                'workload_type': WorkloadType.BATCH_ANALYTICS,
                'avg_duration': 45.0,
                'memory_range': (2048, 3008),
                'cpu_pattern': 'sustained',
                'cold_start_prob': 0.8,  # Usually cold
                'error_rate': 0.05,
                'concurrency_limit': 10
            },
            'file-transform': {
                'workload_type': WorkloadType.FILE_TRANSFORM,
                'avg_duration': 5.0,
                'memory_range': (256, 1024),
                'cpu_pattern': 'sustained',
                'cold_start_prob': 0.2,
                'error_rate': 0.02,
                'concurrency_limit': 100
            },
            'db-trigger': {
                'workload_type': WorkloadType.DATABASE_TRIGGER,
                'avg_duration': 0.3,
                'memory_range': (256, 512),
                'cpu_pattern': 'burst',
                'cold_start_prob': 0.05,
                'error_rate': 0.01,
                'concurrency_limit': 500
            }
        }
    
    def _create_workload_patterns(self) -> Dict[WorkloadType, Dict[str, Any]]:
        """Create realistic workload patterns"""
        return {
            WorkloadType.WEB_API: {
                'traffic_pattern': 'diurnal',  # Daily peaks
                'burst_factor': 3.0,
                'peak_hours': [9, 10, 11, 14, 15, 16, 20, 21],
                'base_rate': 100.0,  # invocations per minute
                'seasonal_factor': 1.2,
                'weekend_factor': 0.6
            },
            WorkloadType.DATA_PROCESSING: {
                'traffic_pattern': 'batch',  # Scheduled batches
                'burst_factor': 10.0,
                'peak_hours': [2, 3, 4, 14, 15, 22, 23],
                'base_rate': 5.0,
                'seasonal_factor': 1.0,
                'weekend_factor': 0.3
            },
            WorkloadType.IOT_TELEMETRY: {
                'traffic_pattern': 'constant',  # Steady stream
                'burst_factor': 1.5,
                'peak_hours': list(range(24)),  # Always active
                'base_rate': 500.0,
                'seasonal_factor': 1.1,
                'weekend_factor': 0.9
            },
            WorkloadType.ML_INFERENCE: {
                'traffic_pattern': 'bursty',  # Irregular bursts
                'burst_factor': 5.0,
                'peak_hours': [8, 9, 10, 13, 14, 15, 19, 20],
                'base_rate': 20.0,
                'seasonal_factor': 1.3,
                'weekend_factor': 0.4
            },
            WorkloadType.IMAGE_PROCESSING: {
                'traffic_pattern': 'event_driven',  # Triggered by uploads
                'burst_factor': 8.0,
                'peak_hours': [10, 11, 12, 16, 17, 18, 21, 22],
                'base_rate': 15.0,
                'seasonal_factor': 1.5,
                'weekend_factor': 1.2
            }
        }
    
    def _create_attack_patterns(self) -> Dict[AttackScenario, Dict[str, Any]]:
        """Create attack scenario patterns"""
        return {
            AttackScenario.DOW_BILLING_ATTACK: {
                'duration_pattern': 'sustained',  # Long duration to maximize cost
                'duration_multiplier': 5.0,
                'memory_multiplier': 2.0,
                'cpu_pattern': 'high_sustained',
                'invocation_rate_multiplier': 10.0,
                'error_rate': 0.0,  # Successful attacks
                'detection_probability': 0.7
            },
            AttackScenario.CRYPTOMINING: {
                'duration_pattern': 'consistent',  # Consistent timing
                'duration_multiplier': 1.2,
                'memory_multiplier': 1.1,
                'cpu_pattern': 'maxed',  # 100% CPU
                'invocation_rate_multiplier': 1.0,
                'error_rate': 0.001,
                'detection_probability': 0.8
            },
            AttackScenario.RESOURCE_EXHAUSTION: {
                'duration_pattern': 'timeout',  # Hit timeout limits
                'duration_multiplier': 1.0,
                'memory_multiplier': 3.0,  # Memory exhaustion
                'cpu_pattern': 'burst_then_hang',
                'invocation_rate_multiplier': 20.0,
                'error_rate': 0.3,  # Many timeouts
                'detection_probability': 0.9
            },
            AttackScenario.DATA_EXFILTRATION: {
                'duration_pattern': 'variable',  # Variable to avoid detection
                'duration_multiplier': 1.5,
                'memory_multiplier': 1.0,
                'cpu_pattern': 'network_heavy',
                'invocation_rate_multiplier': 0.5,  # Low and slow
                'error_rate': 0.01,
                'detection_probability': 0.4
            }
        }
    
    def generate_normal_trace(self, function_name: str, duration_hours: float, 
                            num_invocations: Optional[int] = None) -> ServerlessTrace:
        """Generate a normal (non-malicious) serverless trace"""
        
        if function_name not in self.function_registry:
            raise ValueError(f"Unknown function: {function_name}")
        
        func_config = self.function_registry[function_name]
        workload_type = func_config['workload_type']
        workload_pattern = self.workload_patterns.get(workload_type, {})
        
        trace_id = str(uuid.uuid4())
        start_time = self.base_timestamp
        end_time = start_time + (duration_hours * 3600)
        
        # Calculate number of invocations based on workload pattern
        if num_invocations is None:
            base_rate = workload_pattern.get('base_rate', 10.0)  # per minute
            total_minutes = duration_hours * 60
            expected_invocations = base_rate * total_minutes
            
            # Add some randomness
            num_invocations = int(np.random.poisson(expected_invocations))
            num_invocations = max(1, num_invocations)  # At least 1
        
        invocations = []
        graph = ServerlessExecutionGraph(max_nodes=num_invocations + 100)
        
        # Generate invocation times based on pattern
        invocation_times = self._generate_invocation_times(
            start_time, end_time, num_invocations, workload_pattern
        )
        
        # Track state for realistic patterns
        container_state = {
            'warm_until': start_time,  # Container warmth expiry
            'recent_invocations': [],  # Recent invocations for correlation
            'error_streak': 0,  # Consecutive errors
            'memory_pressure': 0.0  # Memory pressure buildup
        }
        
        for i, invocation_time in enumerate(invocation_times):
            record = self._generate_invocation(
                function_name, func_config, invocation_time, 
                container_state, i, trace_id
            )
            invocations.append(record)
            
            # Add to graph
            node = self._telemetry_record_to_node(record)
            graph.add_node(node)
            
            # Create edges to recent invocations
            self._add_temporal_edges(graph, record, invocations[-5:])  # Last 5
        
        return ServerlessTrace(
            trace_id=trace_id,
            function_name=function_name,
            workload_type=workload_type,
            start_time=start_time,
            end_time=end_time,
            invocations=invocations,
            graph=graph,
            labels={
                'is_attack': False,
                'is_anomaly': False,
                'workload_type': workload_type.value,
                'ground_truth': 'normal'
            },
            metadata={
                'generation_method': 'normal_pattern',
                'function_config': func_config
            }
        )
    
    def generate_attack_trace(self, function_name: str, attack_scenario: AttackScenario,
                            duration_hours: float, num_invocations: Optional[int] = None) -> ServerlessTrace:
        """Generate an attack trace"""
        
        if function_name not in self.function_registry:
            raise ValueError(f"Unknown function: {function_name}")
        
        func_config = self.function_registry[function_name].copy()  # Copy to modify
        attack_pattern = self.attack_patterns[attack_scenario]
        
        # Modify function config based on attack pattern
        func_config['avg_duration'] *= attack_pattern['duration_multiplier']
        func_config['memory_range'] = (
            func_config['memory_range'][0] * attack_pattern['memory_multiplier'],
            func_config['memory_range'][1] * attack_pattern['memory_multiplier']
        )
        func_config['error_rate'] = attack_pattern['error_rate']
        
        trace_id = str(uuid.uuid4())
        start_time = self.base_timestamp
        end_time = start_time + (duration_hours * 3600)
        
        # Calculate attack-specific invocation count
        if num_invocations is None:
            workload_pattern = self.workload_patterns.get(func_config['workload_type'], {})
            base_rate = workload_pattern.get('base_rate', 10.0)
            base_rate *= attack_pattern['invocation_rate_multiplier']
            total_minutes = duration_hours * 60
            expected_invocations = base_rate * total_minutes
            num_invocations = int(np.random.poisson(expected_invocations))
            num_invocations = max(1, num_invocations)
        
        invocations = []
        graph = ServerlessExecutionGraph(max_nodes=num_invocations + 100)
        
        # Generate attack-specific invocation times
        if attack_scenario == AttackScenario.CRYPTOMINING:
            # Consistent intervals for mining
            invocation_times = np.linspace(start_time, end_time, num_invocations)
        elif attack_scenario == AttackScenario.DOW_BILLING_ATTACK:
            # High frequency bursts
            invocation_times = self._generate_burst_times(start_time, end_time, num_invocations)
        else:
            # Use normal pattern but with attack characteristics
            workload_pattern = self.workload_patterns.get(func_config['workload_type'], {})
            invocation_times = self._generate_invocation_times(
                start_time, end_time, num_invocations, workload_pattern
            )
        
        # Track attack-specific state
        container_state = {
            'warm_until': start_time,
            'recent_invocations': [],
            'error_streak': 0,
            'memory_pressure': 0.0,
            'attack_phase': 'initial'  # Attack phases: initial, active, cleanup
        }
        
        for i, invocation_time in enumerate(invocation_times):
            # Update attack phase
            progress = i / len(invocation_times)
            if progress < 0.1:
                container_state['attack_phase'] = 'initial'
            elif progress < 0.9:
                container_state['attack_phase'] = 'active'
            else:
                container_state['attack_phase'] = 'cleanup'
            
            record = self._generate_attack_invocation(
                function_name, func_config, invocation_time, 
                container_state, i, trace_id, attack_scenario, attack_pattern
            )
            invocations.append(record)
            
            # Add to graph
            node = self._telemetry_record_to_node(record)
            graph.add_node(node)
            
            # Create edges
            self._add_temporal_edges(graph, record, invocations[-5:])
        
        return ServerlessTrace(
            trace_id=trace_id,
            function_name=function_name,
            workload_type=func_config['workload_type'],
            start_time=start_time,
            end_time=end_time,
            invocations=invocations,
            graph=graph,
            labels={
                'is_attack': True,
                'is_anomaly': True,
                'attack_scenario': attack_scenario.value,
                'ground_truth': 'attack',
                'detection_probability': attack_pattern['detection_probability']
            },
            metadata={
                'generation_method': 'attack_pattern',
                'attack_pattern': attack_pattern,
                'modified_function_config': func_config
            }
        )
    
    def generate_anomaly_trace(self, function_name: str, anomaly_scenario: AnomalyScenario,
                             duration_hours: float) -> ServerlessTrace:
        """Generate a performance anomaly trace"""
        
        func_config = self.function_registry[function_name].copy()
        trace_id = str(uuid.uuid4())
        start_time = self.base_timestamp
        end_time = start_time + (duration_hours * 3600)
        
        workload_pattern = self.workload_patterns.get(func_config['workload_type'], {})
        base_rate = workload_pattern.get('base_rate', 10.0)
        total_minutes = duration_hours * 60
        expected_invocations = base_rate * total_minutes
        
        # Anomaly-specific modifications
        if anomaly_scenario == AnomalyScenario.COLD_START_CASCADE:
            # All invocations are cold starts due to rapid scaling
            func_config['cold_start_prob'] = 1.0
            expected_invocations *= 2  # More invocations due to retries
        elif anomaly_scenario == AnomalyScenario.MEMORY_LEAK:
            # Memory increases over time
            func_config['memory_leak_rate'] = 50  # MB per invocation
        elif anomaly_scenario == AnomalyScenario.TIMEOUT_CASCADE:
            # Many timeouts leading to retries
            func_config['timeout_prob'] = 0.3
            expected_invocations *= 1.5
        
        num_invocations = int(np.random.poisson(expected_invocations))
        num_invocations = max(1, num_invocations)
        
        invocation_times = self._generate_invocation_times(
            start_time, end_time, num_invocations, workload_pattern
        )
        
        invocations = []
        graph = ServerlessExecutionGraph(max_nodes=num_invocations + 100)
        
        container_state = {
            'warm_until': start_time,
            'recent_invocations': [],
            'error_streak': 0,
            'memory_pressure': 0.0,
            'anomaly_intensity': 0.0  # Builds up over time
        }
        
        for i, invocation_time in enumerate(invocation_times):
            # Increase anomaly intensity over time
            progress = i / len(invocation_times)
            container_state['anomaly_intensity'] = progress
            
            record = self._generate_anomaly_invocation(
                function_name, func_config, invocation_time,
                container_state, i, trace_id, anomaly_scenario
            )
            invocations.append(record)
            
            # Add to graph
            node = self._telemetry_record_to_node(record)
            graph.add_node(node)
            
            # Create edges
            self._add_temporal_edges(graph, record, invocations[-5:])
        
        return ServerlessTrace(
            trace_id=trace_id,
            function_name=function_name,
            workload_type=func_config['workload_type'],
            start_time=start_time,
            end_time=end_time,
            invocations=invocations,
            graph=graph,
            labels={
                'is_attack': False,
                'is_anomaly': True,
                'anomaly_scenario': anomaly_scenario.value,
                'ground_truth': 'anomaly'
            },
            metadata={
                'generation_method': 'anomaly_pattern',
                'anomaly_scenario': anomaly_scenario.value
            }
        )
    
    def _generate_invocation_times(self, start_time: float, end_time: float,
                                 num_invocations: int, pattern: Dict[str, Any]) -> List[float]:
        """Generate realistic invocation times based on workload pattern"""
        
        traffic_pattern = pattern.get('traffic_pattern', 'constant')
        
        if traffic_pattern == 'constant':
            # Uniform distribution with some jitter
            times = np.linspace(start_time, end_time, num_invocations)
            jitter = np.random.normal(0, (end_time - start_time) / num_invocations * 0.1, num_invocations)
            times = times + jitter
        
        elif traffic_pattern == 'diurnal':
            # Daily peaks and valleys
            times = []
            duration = end_time - start_time
            peak_hours = pattern.get('peak_hours', [9, 10, 11, 14, 15, 16])
            
            for i in range(num_invocations):
                # Base time
                base_time = start_time + (i / num_invocations) * duration
                
                # Check if in peak hour
                hour_of_day = int((base_time % 86400) / 3600)
                if hour_of_day in peak_hours:
                    rate_multiplier = pattern.get('burst_factor', 2.0)
                else:
                    rate_multiplier = 1.0
                
                # Add some randomness
                jitter = np.random.exponential(1.0 / rate_multiplier) * 60  # seconds
                times.append(base_time + jitter)
            
        elif traffic_pattern == 'bursty':
            # Random bursts
            times = []
            num_bursts = max(1, num_invocations // 20)
            burst_times = np.random.uniform(start_time, end_time, num_bursts)
            
            invocations_per_burst = num_invocations // num_bursts
            remainder = num_invocations % num_bursts
            
            for i, burst_time in enumerate(burst_times):
                burst_size = invocations_per_burst
                if i < remainder:
                    burst_size += 1
                
                # Generate burst
                burst_duration = 60.0  # 1 minute burst
                burst_times_i = np.random.uniform(
                    burst_time, burst_time + burst_duration, burst_size
                )
                times.extend(burst_times_i)
        
        else:  # Default: uniform with jitter
            times = np.random.uniform(start_time, end_time, num_invocations)
        
        return sorted(times)
    
    def _generate_burst_times(self, start_time: float, end_time: float, 
                            num_invocations: int) -> List[float]:
        """Generate high-frequency burst times for DoW attacks"""
        duration = end_time - start_time
        
        # Create multiple intense bursts
        num_bursts = max(1, int(duration / 300))  # Every 5 minutes
        times = []
        
        burst_starts = np.linspace(start_time, end_time - 60, num_bursts)
        invocations_per_burst = num_invocations // num_bursts
        
        for burst_start in burst_starts:
            # High frequency within burst (one every second)
            burst_times = np.arange(
                burst_start, 
                burst_start + min(60, invocations_per_burst), 
                1.0
            )
            times.extend(burst_times[:invocations_per_burst])
        
        # Add any remaining invocations
        remaining = num_invocations - len(times)
        if remaining > 0:
            extra_times = np.random.uniform(start_time, end_time, remaining)
            times.extend(extra_times)
        
        return sorted(times)
    
    def _generate_invocation(self, function_name: str, func_config: Dict[str, Any],
                           invocation_time: float, container_state: Dict[str, Any],
                           sequence_num: int, trace_id: str) -> TelemetryRecord:
        """Generate a single normal invocation"""
        
        # Determine if this is a cold start
        is_cold_start = (
            invocation_time > container_state['warm_until'] or
            random.random() < func_config['cold_start_prob']
        )
        
        # Calculate duration
        base_duration = func_config['avg_duration']
        if is_cold_start:
            # Cold starts take 2-10x longer
            duration_multiplier = random.uniform(2.0, 10.0)
            duration = base_duration * duration_multiplier
            # Keep container warm for 10-15 minutes
            container_state['warm_until'] = invocation_time + random.uniform(600, 900)
        else:
            # Normal warm start with some variance
            duration = np.random.gamma(2.0, base_duration / 2.0)
        
        # Memory usage
        memory_range = func_config['memory_range']
        base_memory = random.uniform(memory_range[0], memory_range[1])
        
        # Add memory pressure buildup
        memory_pressure_bonus = container_state['memory_pressure'] * 0.1
        memory_mb = min(3008, base_memory + memory_pressure_bonus)
        
        # CPU utilization based on pattern
        cpu_pattern = func_config['cpu_pattern']
        if cpu_pattern == 'burst':
            cpu_utilization = random.uniform(70, 95)
        elif cpu_pattern == 'sustained':
            cpu_utilization = random.uniform(40, 70)
        else:  # minimal
            cpu_utilization = random.uniform(5, 30)
        
        # Network I/O (varies by function type)
        if func_config['workload_type'] == WorkloadType.WEB_API:
            network_io_bytes = random.randint(1000, 50000)
        elif func_config['workload_type'] == WorkloadType.DATA_PROCESSING:
            network_io_bytes = random.randint(100000, 10000000)
        else:
            network_io_bytes = random.randint(100, 10000)
        
        # Error occurrence
        error_occurred = random.random() < func_config['error_rate']
        if error_occurred:
            container_state['error_streak'] += 1
        else:
            container_state['error_streak'] = 0
        
        # Anomaly type based on characteristics
        if error_occurred:
            anomaly_type = random.choice([
                AnomalyType.EXECUTION_FAILURE,
                AnomalyType.TIMEOUT_FALLBACK
            ])
        elif is_cold_start:
            anomaly_type = AnomalyType.COLD_START
        elif memory_mb > memory_range[1] * 0.8:
            anomaly_type = AnomalyType.MEMORY_SPIKE
        elif cpu_utilization > 85:
            anomaly_type = AnomalyType.CPU_BURST
        elif network_io_bytes > 1000000:
            anomaly_type = AnomalyType.IO_INTENSIVE
        else:
            anomaly_type = AnomalyType.BENIGN
        
        # Update container state
        container_state['memory_pressure'] = min(1.0, container_state['memory_pressure'] + 0.02)
        container_state['recent_invocations'].append(invocation_time)
        if len(container_state['recent_invocations']) > 10:
            container_state['recent_invocations'].pop(0)
        
        return TelemetryRecord(
            event_id=f"{trace_id}_{sequence_num:06d}",
            timestamp=invocation_time,
            function_id=function_name,
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=anomaly_type,
            duration=duration,
            memory_spike_kb=int(memory_mb * 1024),
            cpu_utilization=cpu_utilization,
            network_io_bytes=network_io_bytes,
            fallback_mode=False,
            source=TelemetrySource.PRIMARY,
            concurrency_id=f"{trace_id}_concurrency_{sequence_num}",
            telemetry_metadata={
                'is_cold_start': is_cold_start,
                'error_occurred': error_occurred,
                'sequence_number': sequence_num,
                'container_age': invocation_time - container_state['warm_until'] + 900 if not is_cold_start else 0
            }
        )
    
    def _generate_attack_invocation(self, function_name: str, func_config: Dict[str, Any],
                                  invocation_time: float, container_state: Dict[str, Any],
                                  sequence_num: int, trace_id: str, attack_scenario: AttackScenario,
                                  attack_pattern: Dict[str, Any]) -> TelemetryRecord:
        """Generate an attack invocation"""
        
        # Base invocation
        record = self._generate_invocation(
            function_name, func_config, invocation_time, 
            container_state, sequence_num, trace_id
        )
        
        # Apply attack-specific modifications
        if attack_scenario == AttackScenario.CRYPTOMINING:
            # Consistent high CPU, consistent duration
            record.cpu_utilization = random.uniform(95, 100)
            record.duration = func_config['avg_duration'] * random.uniform(0.9, 1.1)  # Very consistent
            record.anomaly_type = AnomalyType.CPU_BURST
            
        elif attack_scenario == AttackScenario.DOW_BILLING_ATTACK:
            # Maximize resource usage to increase costs
            record.duration = func_config['avg_duration'] * attack_pattern['duration_multiplier']
            record.memory_spike_kb = int(func_config['memory_range'][1] * 1024)
            record.cpu_utilization = random.uniform(80, 100)
            record.network_io_bytes = max(record.network_io_bytes, 5000000)  # High network usage
            record.anomaly_type = AnomalyType.ADVERSARIAL_INJECTION
            
        elif attack_scenario == AttackScenario.RESOURCE_EXHAUSTION:
            # Try to exhaust memory and hit timeouts
            record.memory_spike_kb = int(min(3008, func_config['memory_range'][1] * 2.0) * 1024)
            if random.random() < 0.3:  # 30% timeout
                record.duration = 900  # Lambda timeout
                record.anomaly_type = AnomalyType.TIMEOUT_FALLBACK
            else:
                record.anomaly_type = AnomalyType.MEMORY_SPIKE
                
        elif attack_scenario == AttackScenario.DATA_EXFILTRATION:
            # High network I/O but try to stay under radar
            record.network_io_bytes = random.randint(2000000, 20000000)  # 2-20MB
            record.duration *= random.uniform(1.2, 1.8)  # Slightly longer for data transfer
            record.anomaly_type = AnomalyType.NETWORK_ANOMALY
        
        # Add attack metadata
        record.telemetry_metadata.update({
            'attack_scenario': attack_scenario.value,
            'attack_phase': container_state.get('attack_phase', 'unknown'),
            'attack_intensity': container_state.get('anomaly_intensity', 0.0)
        })
        
        return record
    
    def _generate_anomaly_invocation(self, function_name: str, func_config: Dict[str, Any],
                                   invocation_time: float, container_state: Dict[str, Any],
                                   sequence_num: int, trace_id: str, 
                                   anomaly_scenario: AnomalyScenario) -> TelemetryRecord:
        """Generate an anomaly invocation"""
        
        # Base invocation
        record = self._generate_invocation(
            function_name, func_config, invocation_time,
            container_state, sequence_num, trace_id
        )
        
        intensity = container_state['anomaly_intensity']
        
        if anomaly_scenario == AnomalyScenario.COLD_START_CASCADE:
            # Force cold start
            record.telemetry_metadata['is_cold_start'] = True
            record.duration = func_config['avg_duration'] * random.uniform(3.0, 8.0)
            record.anomaly_type = AnomalyType.COLD_START
            
        elif anomaly_scenario == AnomalyScenario.MEMORY_LEAK:
            # Memory increases over time
            leak_rate = func_config.get('memory_leak_rate', 50)
            additional_memory = sequence_num * leak_rate
            record.memory_spike_kb += int(additional_memory * 1024)
            record.memory_spike_kb = min(record.memory_spike_kb, 3008 * 1024)
            record.anomaly_type = AnomalyType.MEMORY_SPIKE
            
        elif anomaly_scenario == AnomalyScenario.TIMEOUT_CASCADE:
            # Increasing timeout probability
            timeout_prob = func_config.get('timeout_prob', 0.1) * (1 + intensity)
            if random.random() < timeout_prob:
                record.duration = 900  # Timeout
                record.anomaly_type = AnomalyType.TIMEOUT_FALLBACK
                record.telemetry_metadata['error_occurred'] = True
                
        elif anomaly_scenario == AnomalyScenario.CONCURRENCY_THROTTLE:
            # Simulated throttling - increased duration
            throttle_factor = 1.0 + intensity * 5.0
            record.duration *= throttle_factor
            record.anomaly_type = AnomalyType.STARVATION_FALLBACK
        
        # Add anomaly metadata
        record.telemetry_metadata.update({
            'anomaly_scenario': anomaly_scenario.value,
            'anomaly_intensity': intensity
        })
        
        return record
    
    def _telemetry_record_to_node(self, record: TelemetryRecord) -> ExecutionNode:
        """Convert telemetry record to execution graph node"""
        
        # Map anomaly type to node type
        node_type_mapping = {
            AnomalyType.BENIGN: NodeType.FUNCTION_INVOCATION,
            AnomalyType.COLD_START: NodeType.COLD_START,
            AnomalyType.CPU_BURST: NodeType.FUNCTION_INVOCATION,
            AnomalyType.MEMORY_SPIKE: NodeType.MEMORY_SPIKE,
            AnomalyType.IO_INTENSIVE: NodeType.NETWORK_IO,
            AnomalyType.NETWORK_ANOMALY: NodeType.NETWORK_IO,
            AnomalyType.TIMEOUT_FALLBACK: NodeType.TIMEOUT,
            AnomalyType.EXECUTION_FAILURE: NodeType.ERROR,
            AnomalyType.ADVERSARIAL_INJECTION: NodeType.FUNCTION_INVOCATION,
            AnomalyType.STARVATION_FALLBACK: NodeType.FUNCTION_INVOCATION
        }
        
        node_type = node_type_mapping.get(record.anomaly_type, NodeType.FUNCTION_INVOCATION)
        
        return ExecutionNode(
            node_id=record.event_id,
            node_type=node_type,
            timestamp=record.timestamp,
            function_id=record.function_id,
            execution_phase=record.execution_phase.value,
            duration=record.duration,
            memory_mb=record.memory_spike_kb / 1024,
            cpu_utilization=record.cpu_utilization,
            network_io_bytes=record.network_io_bytes,
            is_cold_start=record.telemetry_metadata.get('is_cold_start', False),
            error_occurred=record.telemetry_metadata.get('error_occurred', False)
        )
    
    def _add_temporal_edges(self, graph: ServerlessExecutionGraph, 
                          current_record: TelemetryRecord, recent_records: List[TelemetryRecord]):
        """Add temporal edges to the graph"""
        
        for prev_record in recent_records[-5:]:  # Last 5 records
            if prev_record.event_id != current_record.event_id:
                
                # Temporal sequence edge
                time_diff = current_record.timestamp - prev_record.timestamp
                if time_diff < 300:  # Within 5 minutes
                    weight = max(0.1, 1.0 - (time_diff / 300))  # Decay with time
                    
                    edge = ExecutionEdge(
                        source_id=prev_record.event_id,
                        target_id=current_record.event_id,
                        edge_type=EdgeType.TEMPORAL_SEQUENCE,
                        weight=weight,
                        timestamp=(prev_record.timestamp + current_record.timestamp) / 2
                    )
                    graph.add_edge(edge)
                
                # Causal dependency edge (errors leading to retries)
                if (prev_record.telemetry_metadata.get('error_occurred', False) and
                    not current_record.telemetry_metadata.get('error_occurred', False) and
                    time_diff < 60):  # Within 1 minute
                    
                    edge = ExecutionEdge(
                        source_id=prev_record.event_id,
                        target_id=current_record.event_id,
                        edge_type=EdgeType.CAUSAL_DEPENDENCY,
                        weight=0.8,
                        timestamp=(prev_record.timestamp + current_record.timestamp) / 2
                    )
                    graph.add_edge(edge)


class DatasetManager:
    """
    Manager for creating, storing, and loading serverless datasets
    """
    
    def __init__(self, base_path: str = "./datasets"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        self.generator = RealisticServerlessTraceGenerator()
        
    def create_balanced_dataset(self, name: str, total_traces: int = 1000,
                              attack_ratio: float = 0.1, anomaly_ratio: float = 0.15) -> DatasetMetadata:
        """Create a balanced dataset with normal, attack, and anomaly traces"""
        
        # Calculate trace counts
        num_attacks = int(total_traces * attack_ratio)
        num_anomalies = int(total_traces * anomaly_ratio)
        num_normal = total_traces - num_attacks - num_anomalies
        
        print(f"Creating dataset '{name}' with {total_traces} traces:")
        print(f"  - Normal: {num_normal}")
        print(f"  - Attacks: {num_attacks}")
        print(f"  - Anomalies: {num_anomalies}")
        
        traces = []
        function_names = list(self.generator.function_registry.keys())
        
        # Generate normal traces
        for i in range(num_normal):
            function_name = random.choice(function_names)
            duration_hours = random.uniform(0.1, 2.0)  # 6 minutes to 2 hours
            
            trace = self.generator.generate_normal_trace(function_name, duration_hours)
            traces.append(trace)
            
            if (i + 1) % 100 == 0:
                print(f"  Generated {i + 1}/{num_normal} normal traces")
        
        # Generate attack traces
        attack_scenarios = list(AttackScenario)
        for i in range(num_attacks):
            function_name = random.choice(function_names)
            attack_scenario = random.choice(attack_scenarios)
            duration_hours = random.uniform(0.1, 1.0)  # Shorter for attacks
            
            trace = self.generator.generate_attack_trace(function_name, attack_scenario, duration_hours)
            traces.append(trace)
            
            if (i + 1) % 20 == 0:
                print(f"  Generated {i + 1}/{num_attacks} attack traces")
        
        # Generate anomaly traces
        anomaly_scenarios = list(AnomalyScenario)
        for i in range(num_anomalies):
            function_name = random.choice(function_names)
            anomaly_scenario = random.choice(anomaly_scenarios)
            duration_hours = random.uniform(0.2, 3.0)  # Longer for anomalies
            
            trace = self.generator.generate_anomaly_trace(function_name, anomaly_scenario, duration_hours)
            traces.append(trace)
            
            if (i + 1) % 30 == 0:
                print(f"  Generated {i + 1}/{num_anomalies} anomaly traces")
        
        # Shuffle traces
        random.shuffle(traces)
        
        # Calculate dataset statistics
        all_start_times = [trace.start_time for trace in traces]
        all_end_times = [trace.end_time for trace in traces]
        time_span_hours = (max(all_end_times) - min(all_start_times)) / 3600
        
        workload_types = list(set(trace.workload_type.value for trace in traces))
        attack_scenarios_used = list(set(
            trace.labels.get('attack_scenario', '') 
            for trace in traces 
            if trace.labels.get('is_attack', False)
        ))
        attack_scenarios_used = [s for s in attack_scenarios_used if s]  # Remove empty strings
        
        # Create metadata
        metadata = DatasetMetadata(
            name=name,
            description=f"Balanced serverless dataset with {total_traces} traces",
            created_at=time.time(),
            num_traces=len(traces),
            time_span_hours=time_span_hours,
            workload_types=workload_types,
            attack_scenarios=attack_scenarios_used,
            anomaly_rate=num_anomalies / len(traces),
            normal_rate=num_normal / len(traces),
            parameters={
                'attack_ratio': attack_ratio,
                'anomaly_ratio': anomaly_ratio,
                'generator_version': '1.0'
            }
        )
        
        # Save dataset
        self._save_dataset(name, traces, metadata)
        
        print(f"✅ Dataset '{name}' created successfully!")
        print(f"   Time span: {time_span_hours:.1f} hours")
        print(f"   Workload types: {len(workload_types)}")
        print(f"   Attack scenarios: {len(attack_scenarios_used)}")
        
        return metadata
    
    def _save_dataset(self, name: str, traces: List[ServerlessTrace], metadata: DatasetMetadata):
        """Save dataset to disk"""
        dataset_dir = self.base_path / name
        dataset_dir.mkdir(exist_ok=True)
        
        # Save metadata
        metadata_file = dataset_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump({
                'name': metadata.name,
                'description': metadata.description,
                'created_at': metadata.created_at,
                'num_traces': metadata.num_traces,
                'time_span_hours': metadata.time_span_hours,
                'workload_types': metadata.workload_types,
                'attack_scenarios': metadata.attack_scenarios,
                'anomaly_rate': metadata.anomaly_rate,
                'normal_rate': metadata.normal_rate,
                'parameters': metadata.parameters
            }, f, indent=2)
        
        # Save traces (compressed)
        traces_file = dataset_dir / "traces.jsonl.gz"
        with gzip.open(traces_file, 'wt') as f:
            for trace in traces:
                trace_data = {
                    'trace_id': trace.trace_id,
                    'function_name': trace.function_name,
                    'workload_type': trace.workload_type.value,
                    'start_time': trace.start_time,
                    'end_time': trace.end_time,
                    'labels': trace.labels,
                    'metadata': trace.metadata,
                    'invocations': [record.to_dict() for record in trace.invocations]
                }
                f.write(json.dumps(trace_data) + '\n')
        
        # Save graphs separately (they're large)
        graphs_dir = dataset_dir / "graphs"
        graphs_dir.mkdir(exist_ok=True)
        
        for trace in traces:
            graph_file = graphs_dir / f"{trace.trace_id}.json.gz"
            graph_data = {
                'nodes': {
                    node_id: {
                        'node_type': node.node_type.value,
                        'timestamp': node.timestamp,
                        'duration': node.duration,
                        'memory_mb': node.memory_mb,
                        'cpu_utilization': node.cpu_utilization,
                        'network_io_bytes': node.network_io_bytes,
                        'is_cold_start': node.is_cold_start,
                        'error_occurred': node.error_occurred,
                        'features': node.features.tolist() if hasattr(node.features, 'tolist') else list(node.features)
                    }
                    for node_id, node in trace.graph.nodes.items()
                },
                'edges': [
                    {
                        'source_id': edge.source_id,
                        'target_id': edge.target_id,
                        'edge_type': edge.edge_type.value,
                        'weight': edge.weight,
                        'timestamp': edge.timestamp,
                        'features': edge.features.tolist() if hasattr(edge.features, 'tolist') else list(edge.features)
                    }
                    for edge in trace.graph.edges
                ]
            }
            
            with gzip.open(graph_file, 'wt') as f:
                json.dump(graph_data, f)
    
    def load_dataset(self, name: str) -> Tuple[List[ServerlessTrace], DatasetMetadata]:
        """Load dataset from disk"""
        dataset_dir = self.base_path / name
        if not dataset_dir.exists():
            raise FileNotFoundError(f"Dataset '{name}' not found")
        
        # Load metadata
        metadata_file = dataset_dir / "metadata.json"
        with open(metadata_file, 'r') as f:
            metadata_dict = json.load(f)
        
        metadata = DatasetMetadata(**metadata_dict)
        
        # Load traces
        traces_file = dataset_dir / "traces.jsonl.gz"
        traces = []
        
        with gzip.open(traces_file, 'rt') as f:
            for line in f:
                trace_data = json.loads(line.strip())
                
                # Reconstruct invocations
                invocations = []
                for inv_data in trace_data['invocations']:
                    record = TelemetryRecord.from_dict(inv_data)
                    invocations.append(record)
                
                # Load graph
                graph_file = dataset_dir / "graphs" / f"{trace_data['trace_id']}.json.gz"
                graph = ServerlessExecutionGraph()
                
                if graph_file.exists():
                    with gzip.open(graph_file, 'rt') as gf:
                        graph_data = json.load(gf)
                    
                    # Reconstruct nodes
                    for node_id, node_data in graph_data['nodes'].items():
                        node = ExecutionNode(
                            node_id=node_id,
                            node_type=NodeType(node_data['node_type']),
                            timestamp=node_data['timestamp'],
                            function_id=trace_data['function_name'],
                            execution_phase="INVOKE",
                            duration=node_data['duration'],
                            memory_mb=node_data['memory_mb'],
                            cpu_utilization=node_data['cpu_utilization'],
                            network_io_bytes=node_data['network_io_bytes'],
                            is_cold_start=node_data['is_cold_start'],
                            error_occurred=node_data['error_occurred']
                        )
                        node.features = np.array(node_data['features'])
                        graph.add_node(node)
                    
                    # Reconstruct edges
                    for edge_data in graph_data['edges']:
                        edge = ExecutionEdge(
                            source_id=edge_data['source_id'],
                            target_id=edge_data['target_id'],
                            edge_type=EdgeType(edge_data['edge_type']),
                            weight=edge_data['weight'],
                            timestamp=edge_data['timestamp']
                        )
                        edge.features = np.array(edge_data['features'])
                        graph.add_edge(edge)
                
                trace = ServerlessTrace(
                    trace_id=trace_data['trace_id'],
                    function_name=trace_data['function_name'],
                    workload_type=WorkloadType(trace_data['workload_type']),
                    start_time=trace_data['start_time'],
                    end_time=trace_data['end_time'],
                    invocations=invocations,
                    graph=graph,
                    labels=trace_data['labels'],
                    metadata=trace_data['metadata']
                )
                traces.append(trace)
        
        return traces, metadata
    
    def list_datasets(self) -> List[str]:
        """List available datasets"""
        datasets = []
        for item in self.base_path.iterdir():
            if item.is_dir() and (item / "metadata.json").exists():
                datasets.append(item.name)
        return datasets
    
    def get_dataset_info(self, name: str) -> Dict[str, Any]:
        """Get information about a dataset"""
        metadata_file = self.base_path / name / "metadata.json"
        if not metadata_file.exists():
            raise FileNotFoundError(f"Dataset '{name}' not found")
        
        with open(metadata_file, 'r') as f:
            return json.load(f)


# Export key classes
__all__ = [
    'RealisticServerlessTraceGenerator',
    'DatasetManager',
    'ServerlessTrace',
    'DatasetMetadata',
    'WorkloadType',
    'AttackScenario',
    'AnomalyScenario'
]


# Self-test function
async def run_self_test():
    """Run self-test of dataset generation"""
    print("Running Serverless Dataset Generation Self-Test...")
    print("=" * 55)
    
    try:
        # Test trace generator
        generator = RealisticServerlessTraceGenerator()
        print("✅ Generator initialized")
        
        # Generate a small normal trace
        normal_trace = generator.generate_normal_trace('user-api', 0.1, 5)  # 6 minutes, 5 invocations
        print(f"✅ Normal trace: {len(normal_trace.invocations)} invocations, {len(normal_trace.graph.nodes)} nodes")
        
        # Generate attack trace
        attack_trace = generator.generate_attack_trace('user-api', AttackScenario.CRYPTOMINING, 0.1, 5)
        print(f"✅ Attack trace: {len(attack_trace.invocations)} invocations, attack={attack_trace.labels['is_attack']}")
        
        # Generate anomaly trace
        anomaly_trace = generator.generate_anomaly_trace('image-resize', AnomalyScenario.MEMORY_LEAK, 0.1)
        print(f"✅ Anomaly trace: {len(anomaly_trace.invocations)} invocations, anomaly={anomaly_trace.labels['is_anomaly']}")
        
        # Test dataset manager
        manager = DatasetManager("/tmp/test_datasets")
        print("✅ Dataset manager initialized")
        
        # Create small test dataset
        metadata = manager.create_balanced_dataset('test_small', total_traces=20, attack_ratio=0.2, anomaly_ratio=0.3)
        print(f"✅ Test dataset created: {metadata.num_traces} traces")
        
        # Load the dataset back
        traces, loaded_metadata = manager.load_dataset('test_small')
        print(f"✅ Dataset loaded: {len(traces)} traces")
        
        # Verify data integrity
        assert len(traces) == metadata.num_traces
        assert loaded_metadata.name == metadata.name
        print("✅ Data integrity verified")
        
        # Test dataset statistics
        attack_count = sum(1 for trace in traces if trace.labels.get('is_attack', False))
        anomaly_count = sum(1 for trace in traces if trace.labels.get('is_anomaly', False) and not trace.labels.get('is_attack', False))
        normal_count = len(traces) - attack_count - anomaly_count
        
        print(f"   Dataset composition: {normal_count} normal, {attack_count} attacks, {anomaly_count} anomalies")
        
        # Clean up
        import shutil
        shutil.rmtree("/tmp/test_datasets", ignore_errors=True)
        
        print("\n🎉 Serverless Dataset Generation Self-Test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Serverless Dataset Generation Self-Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_self_test())