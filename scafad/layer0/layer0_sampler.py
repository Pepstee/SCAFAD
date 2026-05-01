"""
SCAFAD Layer 0: Execution-aware Sampling Module
==============================================

Implements the Sampler that:
- Profiles runtime (cold start, warm start, high-latency paths)
- Increases sampling/verbosity on suspected cold starts or anomalies
- Learns per-function baseline execution profiles over time
- Allows tuning in app_config.py and logs effective sample rate per invocation

Academic References:
- Adaptive sampling for distributed systems (Lamport et al.)
- Runtime profiling and anomaly detection (Fonseca et al.)
- Learning-based sampling strategies (Barham et al.)
"""

import time
import json
import logging
import asyncio
import hashlib
import statistics
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import threading
import random

# Import configuration
from .app_config import Layer0Config, TelemetryConfig

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Core Enumerations
# =============================================================================

class ExecutionPhase(Enum):
    """Execution phases for sampling decisions"""
    COLD_START = "cold_start"
    WARM_START = "warm_start"
    HOT_EXECUTION = "hot_execution"
    ANOMALY_DETECTED = "anomaly_detected"
    HIGH_LATENCY = "high_latency"
    MEMORY_PRESSURE = "memory_pressure"
    CPU_INTENSIVE = "cpu_intensive"

class SamplingStrategy(Enum):
    """Sampling strategies"""
    ADAPTIVE = "adaptive"           # Dynamic sampling based on conditions
    FIXED_RATE = "fixed_rate"       # Fixed sampling rate
    THRESHOLD_BASED = "threshold_based"  # Sample based on thresholds
    LEARNING_BASED = "learning_based"    # ML-based sampling decisions

class AnomalyType(Enum):
    """Types of anomalies that affect sampling"""
    LATENCY_SPIKE = "latency_spike"
    MEMORY_SPIKE = "memory_spike"
    CPU_SPIKE = "cpu_spike"
    ERROR_RATE_INCREASE = "error_rate_increase"
    THROUGHPUT_DROP = "throughput_drop"
    COLD_START_BURST = "cold_start_burst"

# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class ExecutionProfile:
    """Baseline execution profile for a function"""
    function_id: str
    invocation_count: int = 0
    cold_start_count: int = 0
    warm_start_count: int = 0
    hot_execution_count: int = 0
    
    # Latency statistics
    latency_samples: List[float] = field(default_factory=list)
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Memory statistics
    memory_samples: List[float] = field(default_factory=list)
    avg_memory_mb: float = 0.0
    max_memory_mb: float = 0.0
    
    # CPU statistics
    cpu_samples: List[float] = field(default_factory=list)
    avg_cpu_utilization: float = 0.0
    max_cpu_utilization: float = 0.0
    
    # Anomaly tracking
    anomaly_count: int = 0
    last_anomaly_time: float = 0.0
    anomaly_types: Set[AnomalyType] = field(default_factory=set)
    
    # Sampling history
    sampling_decisions: List[Tuple[float, float, str]] = field(default_factory=list)
    effective_sample_rate: float = 1.0
    
    # Timestamps
    first_invocation: float = 0.0
    last_invocation: float = 0.0
    
    def __post_init__(self):
        if not self.first_invocation:
            self.first_invocation = time.time()

@dataclass
class SamplingDecision:
    """Result of a sampling decision"""
    should_sample: bool
    sample_rate: float
    reason: str
    confidence: float
    execution_phase: ExecutionPhase
    anomaly_detected: bool = False
    anomaly_type: Optional[AnomalyType] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SamplingMetrics:
    """Metrics for sampling operations"""
    total_decisions: int = 0
    sampling_decisions: int = 0
    non_sampling_decisions: int = 0
    cold_start_samples: int = 0
    anomaly_samples: int = 0
    high_latency_samples: int = 0
    average_sample_rate: float = 1.0
    total_sample_rate: float = 0.0
    learning_accuracy: float = 0.0

@dataclass
class AnomalyThresholds:
    """Thresholds for anomaly detection"""
    latency_threshold_p95_multiplier: float = 2.0
    memory_threshold_p95_multiplier: float = 1.5
    cpu_threshold_p95_multiplier: float = 2.0
    error_rate_threshold: float = 0.1
    throughput_drop_threshold: float = 0.5

# =============================================================================
# Sampler Implementation
# =============================================================================

class Sampler:
    """
    Execution-aware sampling for telemetry collection
    
    This component is responsible for:
    1. Profiling runtime characteristics
    2. Detecting anomalies and cold starts
    3. Learning baseline execution profiles
    4. Making intelligent sampling decisions
    """
    
    def __init__(self, config: Layer0Config):
        self.config = config
        self.telemetry_config = config.telemetry
        
        # Execution profiles
        self.execution_profiles: Dict[str, ExecutionProfile] = {}
        self.global_profile: ExecutionProfile = ExecutionProfile("global")
        
        # Sampling configuration
        self.sampling_strategy = SamplingStrategy.ADAPTIVE
        self.base_sample_rate = 0.1  # 10% base sampling
        self.min_sample_rate = 0.01  # 1% minimum
        self.max_sample_rate = 1.0   # 100% maximum
        
        # Anomaly detection
        self.anomaly_thresholds = AnomalyThresholds()
        self.anomaly_detection_enabled = True
        self.cold_start_detection_enabled = True
        
        # Learning parameters
        self.learning_rate = 0.1
        self.min_samples_for_learning = 10
        self.profile_ttl_seconds = 86400  # 24 hours
        
        # Metrics
        self.metrics = SamplingMetrics()
        
        # Background workers
        self.profile_cleanup_worker: Optional[threading.Thread] = None
        self.running = False
        
        # Start background workers
        self._start_background_workers()
        
        logger.info("Sampler initialized with adaptive sampling strategy")
    
    def _start_background_workers(self):
        """Start background worker threads"""
        self.running = True
        
        # Start profile cleanup worker
        self.profile_cleanup_worker = threading.Thread(
            target=self._profile_cleanup_worker,
            name="ProfileCleanupWorker",
            daemon=True
        )
        self.profile_cleanup_worker.start()
        
        logger.info("Started profile cleanup worker")
    
    def should_sample(self, function_id: str, 
                     execution_context: Dict[str, Any]) -> SamplingDecision:
        """
        Determine if telemetry should be sampled for this execution
        
        Args:
            function_id: Unique identifier for the function
            execution_context: Context information about the execution
            
        Returns:
            Sampling decision with reasoning
        """
        start_time = time.time()
        
        try:
            # Get or create execution profile
            profile = self._get_or_create_profile(function_id)
            
            # Update profile with current execution
            self._update_profile(profile, execution_context)
            
            # Detect execution phase
            execution_phase = self._detect_execution_phase(profile, execution_context)
            
            # Detect anomalies
            anomaly_detected, anomaly_type = self._detect_anomalies(profile, execution_context)
            
            # Make sampling decision
            decision = self._make_sampling_decision(
                profile, execution_phase, anomaly_detected, anomaly_type
            )
            
            # Update metrics
            self._update_sampling_metrics(decision)
            
            # Log decision
            self._log_sampling_decision(function_id, decision, execution_context)
            
            return decision
            
        except Exception as e:
            logger.error(f"Sampling decision failed for {function_id}: {e}")
            # Fallback to base sampling rate
            return SamplingDecision(
                should_sample=random.random() < self.base_sample_rate,
                sample_rate=self.base_sample_rate,
                reason="fallback_due_to_error",
                confidence=0.0,
                execution_phase=ExecutionPhase.HOT_EXECUTION
            )
    
    def _get_or_create_profile(self, function_id: str) -> ExecutionProfile:
        """Get existing profile or create new one"""
        if function_id not in self.execution_profiles:
            self.execution_profiles[function_id] = ExecutionProfile(function_id)
        
        return self.execution_profiles[function_id]
    
    def _update_profile(self, profile: ExecutionProfile, 
                       execution_context: Dict[str, Any]):
        """Update execution profile with new data"""
        current_time = time.time()
        
        # Update invocation counts
        profile.invocation_count += 1
        profile.last_invocation = current_time
        
        # Update latency statistics
        if 'duration_ms' in execution_context:
            latency = execution_context['duration_ms']
            profile.latency_samples.append(latency)
            
            # Keep only recent samples (last 1000)
            if len(profile.latency_samples) > 1000:
                profile.latency_samples = profile.latency_samples[-1000:]
            
            # Update statistics
            if profile.latency_samples:
                profile.avg_latency_ms = statistics.mean(profile.latency_samples)
                profile.p50_latency_ms = statistics.median(profile.latency_samples)
                profile.p95_latency_ms = statistics.quantiles(profile.latency_samples, n=20)[18]  # 95th percentile
                profile.p99_latency_ms = statistics.quantiles(profile.latency_samples, n=100)[98]  # 99th percentile
        
        # Update memory statistics
        if 'memory_usage_mb' in execution_context:
            memory = execution_context['memory_usage_mb']
            profile.memory_samples.append(memory)
            
            if len(profile.memory_samples) > 1000:
                profile.memory_samples = profile.memory_samples[-1000:]
            
            if profile.memory_samples:
                profile.avg_memory_mb = statistics.mean(profile.memory_samples)
                profile.max_memory_mb = max(profile.max_memory_mb, memory)
        
        # Update CPU statistics
        if 'cpu_utilization' in execution_context:
            cpu = execution_context['cpu_utilization']
            profile.cpu_samples.append(cpu)
            
            if len(profile.cpu_samples) > 1000:
                profile.cpu_samples = profile.cpu_samples[-1000:]
            
            if profile.cpu_samples:
                profile.avg_cpu_utilization = statistics.mean(profile.cpu_samples)
                profile.max_cpu_utilization = max(profile.max_cpu_utilization, cpu)
        
        # Update global profile
        self._update_global_profile(execution_context)
    
    def _update_global_profile(self, execution_context: Dict[str, Any]):
        """Update global execution profile"""
        current_time = time.time()
        
        self.global_profile.invocation_count += 1
        self.global_profile.last_invocation = current_time
        
        if not self.global_profile.first_invocation:
            self.global_profile.first_invocation = current_time
        
        # Update global statistics
        if 'duration_ms' in execution_context:
            latency = execution_context['duration_ms']
            self.global_profile.latency_samples.append(latency)
            
            if len(self.global_profile.latency_samples) > 10000:
                self.global_profile.latency_samples = self.global_profile.latency_samples[-10000:]
            
            if self.global_profile.latency_samples:
                self.global_profile.avg_latency_ms = statistics.mean(self.global_profile.latency_samples)
                self.global_profile.p95_latency_ms = statistics.quantiles(self.global_profile.latency_samples, n=20)[18]
    
    def _detect_execution_phase(self, profile: ExecutionProfile, 
                               execution_context: Dict[str, Any]) -> ExecutionPhase:
        """Detect the current execution phase"""
        
        # Check for cold start indicators
        if self.cold_start_detection_enabled:
            if self._is_cold_start(profile, execution_context):
                profile.cold_start_count += 1
                return ExecutionPhase.COLD_START
            
            if self._is_warm_start(profile, execution_context):
                profile.warm_start_count += 1
                return ExecutionPhase.WARM_START
        
        # Check for high latency
        if 'duration_ms' in execution_context:
            latency = execution_context['duration_ms']
            if (profile.p95_latency_ms > 0 and 
                latency > profile.p95_latency_ms * 1.5):
                return ExecutionPhase.HIGH_LATENCY
        
        # Check for memory pressure
        if 'memory_usage_mb' in execution_context:
            memory = execution_context['memory_usage_mb']
            if (profile.avg_memory_mb > 0 and 
                memory > profile.avg_memory_mb * 1.3):
                return ExecutionPhase.MEMORY_PRESSURE
        
        # Check for CPU intensive execution
        if 'cpu_utilization' in execution_context:
            cpu = execution_context['cpu_utilization']
            if cpu > 80.0:  # High CPU threshold
                return ExecutionPhase.CPU_INTENSIVE
        
        # Default to hot execution
        profile.hot_execution_count += 1
        return ExecutionPhase.HOT_EXECUTION
    
    def _is_cold_start(self, profile: ExecutionProfile, 
                       execution_context: Dict[str, Any]) -> bool:
        """Determine if this is a cold start"""
        current_time = time.time()
        
        # Check time since last invocation
        if profile.last_invocation > 0:
            time_since_last = current_time - profile.last_invocation
            if time_since_last > 300:  # 5 minutes threshold
                return True
        
        # Check for cold start indicators in context
        if execution_context.get('cold_start', False):
            return True
        
        # Check for memory initialization patterns
        if 'memory_usage_mb' in execution_context:
            memory = execution_context['memory_usage_mb']
            if profile.avg_memory_mb > 0:
                # If memory usage is significantly different from average, might be cold start
                memory_ratio = memory / profile.avg_memory_mb
                if memory_ratio < 0.5 or memory_ratio > 2.0:
                    return True
        
        return False
    
    def _is_warm_start(self, profile: ExecutionProfile, 
                       execution_context: Dict[str, Any]) -> bool:
        """Determine if this is a warm start"""
        current_time = time.time()
        
        if profile.last_invocation > 0:
            time_since_last = current_time - profile.last_invocation
            # Warm start: between 30 seconds and 5 minutes
            if 30 <= time_since_last <= 300:
                return True
        
        return False
    
    def _detect_anomalies(self, profile: ExecutionProfile, 
                          execution_context: Dict[str, Any]) -> Tuple[bool, Optional[AnomalyType]]:
        """Detect anomalies in execution"""
        if not self.anomaly_detection_enabled:
            return False, None
        
        anomalies_detected = []
        
        # Check latency anomalies
        if 'duration_ms' in execution_context:
            latency = execution_context['duration_ms']
            if (profile.p95_latency_ms > 0 and 
                latency > profile.p95_latency_ms * self.anomaly_thresholds.latency_threshold_p95_multiplier):
                anomalies_detected.append(AnomalyType.LATENCY_SPIKE)
        
        # Check memory anomalies
        if 'memory_usage_mb' in execution_context:
            memory = execution_context['memory_usage_mb']
            if (profile.avg_memory_mb > 0 and 
                memory > profile.avg_memory_mb * self.anomaly_thresholds.memory_threshold_p95_multiplier):
                anomalies_detected.append(AnomalyType.MEMORY_SPIKE)
        
        # Check CPU anomalies
        if 'cpu_utilization' in execution_context:
            cpu = execution_context['cpu_utilization']
            if (profile.avg_cpu_utilization > 0 and 
                cpu > profile.avg_cpu_utilization * self.anomaly_thresholds.cpu_threshold_p95_multiplier):
                anomalies_detected.append(AnomalyType.CPU_SPIKE)
        
        # Check error rate anomalies
        if 'error_occurred' in execution_context:
            if execution_context['error_occurred']:
                # Calculate error rate from recent invocations
                recent_invocations = profile.invocation_count - max(0, profile.invocation_count - 100)
                if recent_invocations > 0:
                    error_rate = 1.0 / recent_invocations  # Simplified
                    if error_rate > self.anomaly_thresholds.error_rate_threshold:
                        anomalies_detected.append(AnomalyType.ERROR_RATE_INCREASE)
        
        # Update profile with anomalies
        if anomalies_detected:
            profile.anomaly_count += 1
            profile.last_anomaly_time = time.time()
            profile.anomaly_types.update(anomalies_detected)
            
            # Return the most significant anomaly
            return True, anomalies_detected[0]
        
        return False, None
    
    def _make_sampling_decision(self, profile: ExecutionProfile, 
                               execution_phase: ExecutionPhase,
                               anomaly_detected: bool,
                               anomaly_type: Optional[AnomalyType]) -> SamplingDecision:
        """Make sampling decision based on execution context"""
        
        if self.sampling_strategy == SamplingStrategy.FIXED_RATE:
            return self._fixed_rate_sampling()
        
        elif self.sampling_strategy == SamplingStrategy.THRESHOLD_BASED:
            return self._threshold_based_sampling(execution_phase, anomaly_detected)
        
        elif self.sampling_strategy == SamplingStrategy.LEARNING_BASED:
            return self._learning_based_sampling(profile, execution_phase, anomaly_detected)
        
        else:  # ADAPTIVE
            return self._adaptive_sampling(profile, execution_phase, anomaly_detected, anomaly_type)
    
    def _fixed_rate_sampling(self) -> SamplingDecision:
        """Fixed rate sampling strategy"""
        should_sample = random.random() < self.base_sample_rate
        
        return SamplingDecision(
            should_sample=should_sample,
            sample_rate=self.base_sample_rate,
            reason="fixed_rate_sampling",
            confidence=1.0,
            execution_phase=ExecutionPhase.HOT_EXECUTION
        )
    
    def _threshold_based_sampling(self, execution_phase: ExecutionPhase,
                                anomaly_detected: bool) -> SamplingDecision:
        """Threshold-based sampling strategy"""
        sample_rate = self.base_sample_rate
        
        # Increase sampling for cold starts
        if execution_phase == ExecutionPhase.COLD_START:
            sample_rate = min(1.0, sample_rate * 5.0)
        
        # Increase sampling for anomalies
        if anomaly_detected:
            sample_rate = min(1.0, sample_rate * 3.0)
        
        # Increase sampling for high latency
        if execution_phase == ExecutionPhase.HIGH_LATENCY:
            sample_rate = min(1.0, sample_rate * 2.0)
        
        should_sample = random.random() < sample_rate
        
        return SamplingDecision(
            should_sample=should_sample,
            sample_rate=sample_rate,
            reason="threshold_based_sampling",
            confidence=0.8,
            execution_phase=execution_phase,
            anomaly_detected=anomaly_detected
        )
    
    def _learning_based_sampling(self, profile: ExecutionProfile,
                                execution_phase: ExecutionPhase,
                                anomaly_detected: bool) -> SamplingDecision:
        """Learning-based sampling strategy"""
        # This is a simplified learning approach
        # In a full implementation, this would use ML models
        
        sample_rate = self.base_sample_rate
        
        # Learn from historical sampling decisions
        if profile.sampling_decisions:
            recent_decisions = [d for d in profile.sampling_decisions 
                              if time.time() - d[0] < 3600]  # Last hour
            
            if recent_decisions:
                # Adjust based on recent sampling patterns
                avg_recent_rate = statistics.mean([d[1] for d in recent_decisions])
                sample_rate = (sample_rate + avg_recent_rate) / 2.0
        
        # Adjust based on execution phase
        if execution_phase == ExecutionPhase.COLD_START:
            sample_rate = min(1.0, sample_rate * 4.0)
        elif execution_phase == ExecutionPhase.WARM_START:
            sample_rate = min(1.0, sample_rate * 2.0)
        
        # Adjust based on anomalies
        if anomaly_detected:
            sample_rate = min(1.0, sample_rate * 2.5)
        
        should_sample = random.random() < sample_rate
        
        return SamplingDecision(
            should_sample=should_sample,
            sample_rate=sample_rate,
            reason="learning_based_sampling",
            confidence=0.7,
            execution_phase=execution_phase,
            anomaly_detected=anomaly_detected
        )
    
    def _adaptive_sampling(self, profile: ExecutionProfile,
                          execution_phase: ExecutionPhase,
                          anomaly_detected: bool,
                          anomaly_type: Optional[AnomalyType]) -> SamplingDecision:
        """Adaptive sampling strategy"""
        sample_rate = self.base_sample_rate
        confidence = 0.6
        reason = "adaptive_sampling"
        
        # Base adjustments for execution phase
        if execution_phase == ExecutionPhase.COLD_START:
            sample_rate = min(1.0, sample_rate * 5.0)
            reason = "cold_start_detected"
            confidence = 0.9
        elif execution_phase == ExecutionPhase.WARM_START:
            sample_rate = min(1.0, sample_rate * 2.5)
            reason = "warm_start_detected"
            confidence = 0.8
        elif execution_phase == ExecutionPhase.HIGH_LATENCY:
            sample_rate = min(1.0, sample_rate * 3.0)
            reason = "high_latency_detected"
            confidence = 0.8
        elif execution_phase == ExecutionPhase.MEMORY_PRESSURE:
            sample_rate = min(1.0, sample_rate * 2.0)
            reason = "memory_pressure_detected"
            confidence = 0.7
        elif execution_phase == ExecutionPhase.CPU_INTENSIVE:
            sample_rate = min(1.0, sample_rate * 2.0)
            reason = "cpu_intensive_detected"
            confidence = 0.7
        
        # Anomaly-based adjustments
        if anomaly_detected:
            sample_rate = min(1.0, sample_rate * 3.0)
            reason = f"anomaly_detected_{anomaly_type.value if anomaly_type else 'unknown'}"
            confidence = 0.9
        
        # Profile-based adjustments
        if profile.invocation_count > self.min_samples_for_learning:
            # Adjust based on historical patterns
            if profile.anomaly_count > 0:
                anomaly_frequency = profile.anomaly_count / profile.invocation_count
                if anomaly_frequency > 0.1:  # High anomaly rate
                    sample_rate = min(1.0, sample_rate * 1.5)
                    reason += "_high_anomaly_rate"
            
            # Adjust based on latency variance
            if profile.latency_samples and len(profile.latency_samples) > 10:
                latency_variance = statistics.variance(profile.latency_samples)
                if latency_variance > (profile.avg_latency_ms * 0.5) ** 2:  # High variance
                    sample_rate = min(1.0, sample_rate * 1.3)
                    reason += "_high_latency_variance"
        
        # Ensure sample rate is within bounds
        sample_rate = max(self.min_sample_rate, min(self.max_sample_rate, sample_rate))
        
        # Make sampling decision
        should_sample = random.random() < sample_rate
        
        # Update profile with decision
        profile.sampling_decisions.append((
            time.time(),
            sample_rate,
            reason
        ))
        
        # Keep only recent decisions
        if len(profile.sampling_decisions) > 1000:
            profile.sampling_decisions = profile.sampling_decisions[-1000:]
        
        # Update effective sample rate
        if profile.sampling_decisions:
            recent_rates = [d[1] for d in profile.sampling_decisions[-100:]]
            profile.effective_sample_rate = statistics.mean(recent_rates)
        
        return SamplingDecision(
            should_sample=should_sample,
            sample_rate=sample_rate,
            reason=reason,
            confidence=confidence,
            execution_phase=execution_phase,
            anomaly_detected=anomaly_detected,
            anomaly_type=anomaly_type
        )
    
    def _update_sampling_metrics(self, decision: SamplingDecision):
        """Update sampling metrics"""
        self.metrics.total_decisions += 1
        
        if decision.should_sample:
            self.metrics.sampling_decisions += 1
        else:
            self.metrics.non_sampling_decisions += 1
        
        # Update phase-specific metrics
        if decision.execution_phase == ExecutionPhase.COLD_START:
            self.metrics.cold_start_samples += 1
        elif decision.anomaly_detected:
            self.metrics.anomaly_samples += 1
        elif decision.execution_phase == ExecutionPhase.HIGH_LATENCY:
            self.metrics.high_latency_samples += 1
        
        # Update average sample rate
        self.metrics.total_sample_rate += decision.sample_rate
        self.metrics.average_sample_rate = (
            self.metrics.total_sample_rate / self.metrics.total_decisions
        )
    
    def _log_sampling_decision(self, function_id: str, decision: SamplingDecision,
                              execution_context: Dict[str, Any]):
        """Log sampling decision for monitoring"""
        log_data = {
            'function_id': function_id,
            'timestamp': time.time(),
            'should_sample': decision.should_sample,
            'sample_rate': decision.sample_rate,
            'reason': decision.reason,
            'confidence': decision.confidence,
            'execution_phase': decision.execution_phase.value,
            'anomaly_detected': decision.anomaly_detected,
            'anomaly_type': decision.anomaly_type.value if decision.anomaly_type else None,
            'execution_context': {
                'duration_ms': execution_context.get('duration_ms'),
                'memory_usage_mb': execution_context.get('memory_usage_mb'),
                'cpu_utilization': execution_context.get('cpu_utilization'),
                'cold_start': execution_context.get('cold_start', False)
            }
        }
        
        logger.debug(f"Sampling decision: {json.dumps(log_data, default=str)}")
    
    def get_sampling_summary(self) -> Dict[str, Any]:
        """Get summary of sampling operations"""
        return {
            'total_decisions': self.metrics.total_decisions,
            'sampling_decisions': self.metrics.sampling_decisions,
            'non_sampling_decisions': self.metrics.non_sampling_decisions,
            'cold_start_samples': self.metrics.cold_start_samples,
            'anomaly_samples': self.metrics.anomaly_samples,
            'high_latency_samples': self.metrics.high_latency_samples,
            'average_sample_rate': self.metrics.average_sample_rate,
            'learning_accuracy': self.metrics.learning_accuracy,
            'active_profiles': len(self.execution_profiles),
            'global_profile': {
                'invocation_count': self.global_profile.invocation_count,
                'avg_latency_ms': self.global_profile.avg_latency_ms,
                'p95_latency_ms': self.global_profile.p95_latency_ms
            }
        }
    
    def get_function_profile(self, function_id: str) -> Optional[Dict[str, Any]]:
        """Get execution profile for a specific function"""
        if function_id not in self.execution_profiles:
            return None
        
        profile = self.execution_profiles[function_id]
        
        return {
            'function_id': profile.function_id,
            'invocation_count': profile.invocation_count,
            'cold_start_count': profile.cold_start_count,
            'warm_start_count': profile.warm_start_count,
            'hot_execution_count': profile.hot_execution_count,
            'latency_stats': {
                'avg_ms': profile.avg_latency_ms,
                'p50_ms': profile.p50_latency_ms,
                'p95_ms': profile.p95_latency_ms,
                'p99_ms': profile.p99_latency_ms
            },
            'memory_stats': {
                'avg_mb': profile.avg_memory_mb,
                'max_mb': profile.max_memory_mb
            },
            'cpu_stats': {
                'avg_utilization': profile.avg_cpu_utilization,
                'max_utilization': profile.max_cpu_utilization
            },
            'anomaly_stats': {
                'total_count': profile.anomaly_count,
                'last_anomaly_time': profile.last_anomaly_time,
                'types': [t.value for t in profile.anomaly_types]
            },
            'sampling_stats': {
                'effective_sample_rate': profile.effective_sample_rate,
                'recent_decisions': len(profile.sampling_decisions)
            },
            'timing': {
                'first_invocation': profile.first_invocation,
                'last_invocation': profile.last_invocation
            }
        }
    
    def set_sampling_strategy(self, strategy: SamplingStrategy):
        """Change sampling strategy"""
        old_strategy = self.sampling_strategy
        self.sampling_strategy = strategy
        
        logger.info(f"Sampling strategy changed from {old_strategy.value} to {strategy.value}")
    
    def set_base_sample_rate(self, rate: float):
        """Set base sampling rate"""
        if not (0.0 <= rate <= 1.0):
            raise ValueError("Sample rate must be between 0.0 and 1.0")
        
        old_rate = self.base_sample_rate
        self.base_sample_rate = rate
        
        logger.info(f"Base sample rate changed from {old_rate:.3f} to {rate:.3f}")
    
    def get_sampling_rate(self, function_id: str = None, execution_state: str = None) -> float:
        """Get the current sampling rate for a function"""
        if function_id and function_id in self.execution_profiles:
            profile = self.execution_profiles[function_id]
            # Return effective sample rate from profile
            return profile.effective_sample_rate
        
        # Return base sample rate if no function-specific profile
        return self.base_sample_rate
    
    def update_latency_metrics(self, function_id: str, latency_ms: float):
        """Update latency metrics for a function"""
        if function_id not in self.execution_profiles:
            self.execution_profiles[function_id] = ExecutionProfile(function_id=function_id)
        
        profile = self.execution_profiles[function_id]
        profile.latency_samples.append(latency_ms)
        
        # Keep only last 100 samples
        if len(profile.latency_samples) > 100:
            profile.latency_samples = profile.latency_samples[-100:]
        
        # Update statistics
        if profile.latency_samples:
            profile.avg_latency_ms = statistics.mean(profile.latency_samples)
            profile.p50_latency_ms = statistics.median(profile.latency_samples)
            if len(profile.latency_samples) >= 5:
                profile.p95_latency_ms = sorted(profile.latency_samples)[int(len(profile.latency_samples) * 0.95)]
                profile.p99_latency_ms = sorted(profile.latency_samples)[int(len(profile.latency_samples) * 0.99)]
    
    def update_error_metrics(self, function_id: str, error_count: int, total_executions: int):
        """Update error metrics for a function"""
        if function_id not in self.execution_profiles:
            self.execution_profiles[function_id] = ExecutionProfile(function_id=function_id)
        
        profile = self.execution_profiles[function_id]
        
        # Calculate error rate
        error_rate = error_count / total_executions if total_executions > 0 else 0.0
        
        # Update anomaly detection
        if error_rate > 0.1:  # 10% error rate threshold
            profile.anomaly_count += 1
            profile.anomaly_types.add(AnomalyType.ERROR_RATE_INCREASE)
            profile.last_anomaly_time = time.time()
        
        # Adjust sampling rate based on error rate
        if error_rate > 0.2:  # High error rate - sample more
            profile.effective_sample_rate = min(1.0, profile.effective_sample_rate * 1.5)
        elif error_rate < 0.05:  # Low error rate - sample less
            profile.effective_sample_rate = max(0.1, profile.effective_sample_rate * 0.8)
    
    def determine_sampling_strategy(self, requests_per_second: float) -> str:
        """Determine sampling strategy based on load"""
        if requests_per_second > 1000:
            return "aggressive"  # High load - sample more aggressively
        elif requests_per_second > 100:
            return "adaptive"    # Medium load - adaptive sampling
        else:
            return "conservative"  # Low load - conservative sampling
    
    def set_sampling_policy(self, policy: str):
        """Set sampling policy"""
        if policy == "aggressive":
            self.base_sample_rate = 0.8
        elif policy == "conservative":
            self.base_sample_rate = 0.2
        elif policy == "adaptive":
            self.base_sample_rate = 0.5
        else:
            logger.warning(f"Unknown sampling policy: {policy}")
    
    def _profile_cleanup_worker(self):
        """Background worker for cleaning up old profiles"""
        while self.running:
            try:
                time.sleep(300)  # Run every 5 minutes
                
                current_time = time.time()
                profiles_to_remove = []
                
                for function_id, profile in self.execution_profiles.items():
                    # Remove profiles older than TTL
                    if (current_time - profile.last_invocation > 
                        self.profile_ttl_seconds):
                        profiles_to_remove.append(function_id)
                
                # Remove old profiles
                for function_id in profiles_to_remove:
                    del self.execution_profiles[function_id]
                
                if profiles_to_remove:
                    logger.debug(f"Cleaned up {len(profiles_to_remove)} old profiles")
                
            except Exception as e:
                logger.error(f"Profile cleanup worker error: {e}")
    
    def shutdown(self):
        """Shutdown the sampler"""
        logger.info("Shutting down Sampler...")
        
        self.running = False
        
        if self.profile_cleanup_worker:
            self.profile_cleanup_worker.join(timeout=5.0)
        
        logger.info("Sampler shutdown complete")

# =============================================================================
# Factory Functions
# =============================================================================

def create_sampler(config: Layer0Config = None) -> Sampler:
    """Create a new Sampler instance"""
    if config is None:
        from .app_config import get_default_config
        config = get_default_config()
    
    return Sampler(config)

# =============================================================================
# Testing and Validation
# =============================================================================

def test_sampler():
    """Test the Sampler functionality"""
    from .app_config import create_testing_config
    
    config = create_testing_config()
    sampler = Sampler(config)
    
    print("Testing Sampler...")
    
    # Test different execution contexts
    test_contexts = [
        {
            'duration_ms': 100.0,
            'memory_usage_mb': 128.0,
            'cpu_utilization': 45.0,
            'cold_start': False
        },
        {
            'duration_ms': 50.0,
            'memory_usage_mb': 64.0,
            'cpu_utilization': 25.0,
            'cold_start': True
        },
        {
            'duration_ms': 500.0,
            'memory_usage_mb': 256.0,
            'cpu_utilization': 85.0,
            'cold_start': False
        }
    ]
    
    for i, context in enumerate(test_contexts):
        decision = sampler.should_sample(f"test-function-{i}", context)
        print(f"\nTest {i+1}:")
        print(f"  Should Sample: {decision.should_sample}")
        print(f"  Sample Rate: {decision.sample_rate:.3f}")
        print(f"  Reason: {decision.reason}")
        print(f"  Execution Phase: {decision.execution_phase.value}")
        print(f"  Anomaly Detected: {decision.anomaly_detected}")
    
    # Get summary
    summary = sampler.get_sampling_summary()
    print(f"\nSampling Summary:")
    print(f"  Total Decisions: {summary['total_decisions']}")
    print(f"  Sampling Decisions: {summary['sampling_decisions']}")
    print(f"  Average Sample Rate: {summary['average_sample_rate']:.3f}")
    print(f"  Active Profiles: {summary['active_profiles']}")
    
    # Get function profile
    profile = sampler.get_function_profile("test-function-0")
    if profile:
        print(f"\nFunction Profile:")
        print(f"  Invocation Count: {profile['invocation_count']}")
        print(f"  Cold Start Count: {profile['cold_start_count']}")
        print(f"  Effective Sample Rate: {profile['sampling_stats']['effective_sample_rate']:.3f}")
    
    # Shutdown
    sampler.shutdown()

# Alias for compatibility with tests
ExecutionAwareSampler = Sampler

if __name__ == "__main__":
    # Run test if executed directly
    test_sampler()
