"""
SCAFAD Layer 0: Telemetry Management Module
==========================================

Core telemetry data structures, multi-channel emission system, and telemetry generation.
Handles the complete lifecycle of telemetry records from creation to emission.

Academic References:
- Multi-channel telemetry for fault tolerance (Lamport et al.)
- Structured observability in distributed systems (Fonseca et al.)
- Telemetry completeness verification (Barham et al.)
"""

import time
import json
import uuid
import hashlib
import asyncio
import logging
import random
import string
import sys
from typing import Dict, List, Optional, Any, Union, AsyncIterator, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
import warnings
from pathlib import Path
from collections import defaultdict

# Import configuration
from .app_config import Layer0Config, TelemetryConfig, VerbosityLevel

# Optional async file operations
try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Core Enumerations
# =============================================================================

class AnomalyType(Enum):
    """Comprehensive enumeration of anomaly types detected by SCAFAD"""
    
    # Normal operations
    BENIGN = "benign"
    
    # Execution anomalies
    COLD_START = "cold_start"
    CPU_BURST = "cpu_burst"
    CPU_SPIKE = "cpu_spike"
    MEMORY_SPIKE = "memory_spike"
    MEMORY_LEAK = "memory_leak"
    LATENCY_SPIKE = "latency_spike"
    IO_INTENSIVE = "io_intensive"
    NETWORK_ANOMALY = "network_anomaly"
    TIMEOUT_ANOMALY = "timeout_anomaly"

    # System anomalies
    EXECUTION_FAILURE = "execution_failure"
    ERROR_RATE_INCREASE = "error_rate_increase"
    STARVATION_FALLBACK = "starvation_fallback"
    TIMEOUT_FALLBACK = "timeout_fallback"
    SCHEMA_VIOLATION = "schema_violation"
    
    # Security anomalies
    ADVERSARIAL_INJECTION = "adversarial_injection"
    BILLING_ABUSE = "billing_abuse"
    ECONOMIC_ABUSE = "economic_abuse"
    DOS_AMPLIFICATION = "dos_amplification"
    CRYPTOMINING = "cryptomining"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    
    # Silent failures
    SILENT_CORRUPTION = "silent_corruption"
    SEMANTIC_FAILURE = "semantic_failure"
    OUTPUT_CORRUPTION = "output_corruption"
    INVARIANT_VIOLATION = "invariant_violation"
    
    @property
    def severity_level(self) -> int:
        """Get severity level (0-10, higher is more severe)"""
        severity_map = {
            self.BENIGN: 0,
            self.COLD_START: 2,
            self.CPU_BURST: 3,
            self.CPU_SPIKE: 3,
            self.MEMORY_SPIKE: 3,
            self.MEMORY_LEAK: 5,
            self.LATENCY_SPIKE: 3,
            self.IO_INTENSIVE: 2,
            self.NETWORK_ANOMALY: 4,
            self.TIMEOUT_ANOMALY: 4,
            self.EXECUTION_FAILURE: 6,
            self.ERROR_RATE_INCREASE: 5,
            self.STARVATION_FALLBACK: 5,
            self.TIMEOUT_FALLBACK: 5,
            self.SCHEMA_VIOLATION: 4,
            self.ADVERSARIAL_INJECTION: 9,
            self.BILLING_ABUSE: 8,
            self.ECONOMIC_ABUSE: 8,
            self.DOS_AMPLIFICATION: 9,
            self.CRYPTOMINING: 7,
            self.DATA_EXFILTRATION: 10,
            self.PRIVILEGE_ESCALATION: 10,
            self.SILENT_CORRUPTION: 8,
            self.SEMANTIC_FAILURE: 7,
            self.OUTPUT_CORRUPTION: 6,
            self.INVARIANT_VIOLATION: 5
        }
        return severity_map.get(self, 5)
    
    @property
    def category(self) -> str:
        """Get anomaly category"""
        if self in [self.BENIGN]:
            return "normal"
        elif self in [self.COLD_START, self.CPU_BURST, self.CPU_SPIKE, self.MEMORY_SPIKE,
                     self.MEMORY_LEAK, self.LATENCY_SPIKE, self.IO_INTENSIVE]:
            return "performance"
        elif self in [self.NETWORK_ANOMALY, self.TIMEOUT_ANOMALY, self.EXECUTION_FAILURE,
                     self.ERROR_RATE_INCREASE]:
            return "execution"
        elif self in [self.STARVATION_FALLBACK, self.TIMEOUT_FALLBACK, self.SCHEMA_VIOLATION]:
            return "system"
        elif self in [self.ADVERSARIAL_INJECTION, self.BILLING_ABUSE, self.ECONOMIC_ABUSE,
                     self.DOS_AMPLIFICATION, self.CRYPTOMINING, self.DATA_EXFILTRATION,
                     self.PRIVILEGE_ESCALATION]:
            return "security"
        elif self in [self.SILENT_CORRUPTION, self.SEMANTIC_FAILURE, self.OUTPUT_CORRUPTION, 
                     self.INVARIANT_VIOLATION]:
            return "silent_failure"
        else:
            return "unknown"


class ExecutionPhase(Enum):
    """Function execution phases with detailed lifecycle tracking"""
    
    INIT = "init"
    INVOKE = "invoke"
    SHUTDOWN = "shutdown"
    ERROR = "error"
    TIMEOUT = "timeout"
    
    @property
    def label(self) -> str:
        """Human-readable label"""
        labels = {
            self.INIT: "Initialization",
            self.INVOKE: "Invocation",
            self.SHUTDOWN: "Shutdown",
            self.ERROR: "Error Handling",
            self.TIMEOUT: "Timeout Recovery"
        }
        return labels.get(self, "Unknown")
    
    @property
    def expected_duration_range(self) -> Tuple[float, float]:
        """Expected duration range in seconds (min, max)"""
        ranges = {
            self.INIT: (0.05, 2.0),
            self.INVOKE: (0.01, 15.0),
            self.SHUTDOWN: (0.001, 0.1),
            self.ERROR: (0.001, 1.0),
            self.TIMEOUT: (0.001, 0.5)
        }
        return ranges.get(self, (0.0, 30.0))


class TelemetrySource(Enum):
    """Source of telemetry generation"""
    
    PRIMARY = "primary"
    SCAFAD_LAYER0 = "scafad-layer0"
    ADVERSARIAL_SIMULATOR = "adversarial-simulator"
    FALLBACK_GENERATOR = "fallback-generator"
    ECONOMIC_DETECTOR = "economic-detector"
    GRAPH_BUILDER = "graph-builder"
    PROVENANCE_TRACKER = "provenance-tracker"
    SILENT_FAILURE_DETECTOR = "silent-failure-detector"
    FORMAL_VERIFIER = "formal-verifier"
    EXTERNAL_INJECTOR = "external-injector"

    @property
    def trust_level(self) -> float:
        """Trust level of the source (0.0-1.0)"""
        trust_levels = {
            self.SCAFAD_LAYER0: 1.0,
            self.ADVERSARIAL_SIMULATOR: 0.7,  # Lower trust for simulated data
            self.FALLBACK_GENERATOR: 0.5,      # Fallback has limited information
            self.ECONOMIC_DETECTOR: 0.9,
            self.GRAPH_BUILDER: 0.9,
            self.PROVENANCE_TRACKER: 0.95,
            self.SILENT_FAILURE_DETECTOR: 0.8,
            self.FORMAL_VERIFIER: 0.95,
            self.EXTERNAL_INJECTOR: 0.3,        # Lowest trust for external sources
            self.PRIMARY: 1.0
        }
        return trust_levels.get(self, 0.5)


# =============================================================================
# Core Telemetry Data Structure
# =============================================================================

@dataclass
class TelemetryRecord:
    """
    Core telemetry record with comprehensive metadata and extensibility
    
    This is the fundamental data structure for all Layer 0 telemetry.
    Designed for academic rigor, production reliability, and extensibility.
    """
    
    # Required core fields
    event_id: str
    timestamp: float
    function_id: str
    execution_phase: ExecutionPhase
    anomaly_type: AnomalyType
    
    # Execution metrics
    duration: float
    memory_spike_kb: int
    cpu_utilization: float
    network_io_bytes: int
    
    # Operational metadata
    fallback_mode: bool
    source: TelemetrySource
    concurrency_id: str
    
    # Advanced metadata (optional with defaults)
    container_id: Optional[str] = None
    region: Optional[str] = None
    runtime_version: Optional[str] = None
    
    # Contextual information
    trigger_type: Optional[str] = None
    payload_size_bytes: int = 0
    payload_hash: Optional[str] = None
    
    # Analysis results
    provenance_id: Optional[str] = None
    graph_node_id: Optional[str] = None
    parent_chain: List[str] = field(default_factory=list)
    causal_depth: int = 0
    
    # Risk assessment scores
    adversarial_score: float = 0.0
    economic_risk_score: float = 0.0
    silent_failure_probability: float = 0.0
    completeness_score: float = 1.0
    
    # Quality metrics
    confidence_level: float = 1.0
    data_quality_score: float = 1.0
    schema_version: str = "v4.2"
    
    # Emission metadata
    emission_timestamp: Optional[float] = None
    emission_channels: List[str] = field(default_factory=list)
    emission_attempts: int = 0
    
    # Extensibility
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    
    # CRITICAL FIX #3: Cryptographic integrity
    signature: Optional[str] = None
    signature_algorithm: str = "HMAC-SHA256"
    content_hash: Optional[str] = None
    
    def __post_init__(self):
        """Post-initialization validation and enrichment"""
        
        # Validate required fields
        if not self.event_id:
            raise ValueError("event_id is required")
        if  not self.function_id:
            raise ValueError("function_id is required")
        
        # Type conversion and validation
        if isinstance(self.execution_phase, str):
            self.execution_phase = ExecutionPhase(self.execution_phase)
        if isinstance(self.anomaly_type, str):
            self.anomaly_type = AnomalyType(self.anomaly_type)
        if isinstance(self.source, str):
            self.source = TelemetrySource(self.source)
        
        # Ensure numeric fields are properly typed
        self.duration = float(self.duration)
        self.memory_spike_kb = int(self.memory_spike_kb)
        self.cpu_utilization = float(self.cpu_utilization)
        self.network_io_bytes = int(self.network_io_bytes)
        
        # Validate ranges
        self._validate_ranges()
        
        # Generate derived fields if not provided
        if not self.payload_hash and self.payload_size_bytes > 0:
            self.payload_hash = self._generate_payload_hash()
        
        # Set emission timestamp if not set
        if self.emission_timestamp is None:
            self.emission_timestamp = time.time()
    
    def _validate_ranges(self):
        """Validate field ranges and relationships"""
        
        if self.duration < 0:
            logger.warning(f"Negative duration: {self.duration}")
            self.duration = 0.0
        
        if self.memory_spike_kb < 0:
            logger.warning(f"Negative memory usage: {self.memory_spike_kb}")
            self.memory_spike_kb = 0
        
        if not (0.0 <= self.cpu_utilization <= 100.0):
            logger.warning(f"CPU utilization out of range: {self.cpu_utilization}")
            self.cpu_utilization = max(0.0, min(100.0, self.cpu_utilization))
        
        if self.network_io_bytes < 0:
            logger.warning(f"Negative network I/O: {self.network_io_bytes}")
            self.network_io_bytes = 0
        
        # Validate score ranges
        score_fields = ['adversarial_score', 'economic_risk_score', 'silent_failure_probability',
                       'completeness_score', 'confidence_level', 'data_quality_score']
        
        for field_name in score_fields:
            value = getattr(self, field_name)
            if not (0.0 <= value <= 1.0):
                logger.warning(f"{field_name} out of range: {value}")
                setattr(self, field_name, max(0.0, min(1.0, value)))
    
    def _generate_payload_hash(self) -> str:
        """Generate hash for payload tracking"""
        hash_input = f"{self.function_id}:{self.payload_size_bytes}:{self.timestamp}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with proper serialization"""
        data = asdict(self)
        
        # Convert enums to string values
        data['execution_phase'] = self.execution_phase.value
        data['anomaly_type'] = self.anomaly_type.value
        data['source'] = self.source.value
        
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)
    
    def compute_overall_risk_score(self) -> float:
        """Compute weighted overall risk score"""
        weights = {
            'anomaly_severity': 0.3,
            'adversarial': 0.25,
            'economic': 0.2,
            'silent_failure': 0.15,
            'confidence_penalty': 0.1
        }
        
        # Normalize anomaly severity to 0-1 scale
        anomaly_severity = self.anomaly_type.severity_level / 10.0
        
        # Confidence penalty (lower confidence = higher risk)
        confidence_penalty = 1.0 - self.confidence_level
        
        risk_score = (
            weights['anomaly_severity'] * anomaly_severity +
            weights['adversarial'] * self.adversarial_score +
            weights['economic'] * self.economic_risk_score +
            weights['silent_failure'] * self.silent_failure_probability +
            weights['confidence_penalty'] * confidence_penalty
        )
        
        return min(1.0, risk_score)
    
    def is_critical(self) -> bool:
        """Determine if this telemetry represents a critical event"""
        return (
            self.anomaly_type.severity_level >= 8 or
            self.compute_overall_risk_score() >= 0.8 or
            self.anomaly_type.category in ['security', 'silent_failure']
        )
    
    def get_emission_priority(self) -> int:
        """Get emission priority (0=lowest, 10=highest)"""
        if self.is_critical():
            return 10
        elif self.fallback_mode:
            return 8
        elif self.anomaly_type != AnomalyType.BENIGN:
            return 6
        else:
            return 3
    
    def add_custom_field(self, key: str, value: Any) -> None:
        """Add custom field with validation"""
        if not isinstance(key, str):
            raise ValueError("Custom field key must be string")
        
        self.custom_fields[key] = value
    
    def add_tag(self, key: str, value: str) -> None:
        """Add tag for categorization and filtering"""
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Tags must be strings")
        
        self.tags[key] = value
    
    @property
    def telemetry_id(self) -> str:
        """Alias for event_id for backward compatibility"""
        return self.event_id
    
    def mark_emission_attempt(self, channel: str, success: bool = True) -> None:
        """Mark emission attempt to a channel"""
        self.emission_attempts += 1
        
        if success and channel not in self.emission_channels:
            self.emission_channels.append(channel)
    
    def clone_with_updates(self, **updates) -> 'TelemetryRecord':
        """Create a copy with field updates"""
        data = self.to_dict()
        data.update(updates)
        
        # Handle enum conversions
        if 'execution_phase' in updates and isinstance(updates['execution_phase'], str):
            data['execution_phase'] = ExecutionPhase(updates['execution_phase'])
        if 'anomaly_type' in updates and isinstance(updates['anomaly_type'], str):
            data['anomaly_type'] = AnomalyType(updates['anomaly_type'])
        if 'source' in updates and isinstance(updates['source'], str):
            data['source'] = TelemetrySource(updates['source'])
        
        return TelemetryRecord(**data)
    
    def sign_record(self, secret_key: str) -> None:
        """
        CRITICAL FIX #3: Sign telemetry record for integrity verification
        
        Args:
            secret_key: Secret key for HMAC signing
        """
        # Generate content hash for verification
        self.content_hash = self._compute_content_hash()
        
        # Create signature
        if secret_key:
            self.signature = self._generate_hmac_signature(secret_key)
        else:
            logger.warning("No secret key provided for telemetry signing")
    
    def verify_signature(self, secret_key: str) -> bool:
        """
        Verify telemetry record signature
        
        Args:
            secret_key: Secret key for verification
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.signature or not self.content_hash:
            return False
        
        # Verify content hash
        expected_hash = self._compute_content_hash()
        if expected_hash != self.content_hash:
            logger.warning(f"Content hash mismatch for record {self.event_id}")
            return False
        
        # Verify signature
        expected_signature = self._generate_hmac_signature(secret_key)
        if expected_signature != self.signature:
            logger.warning(f"Signature verification failed for record {self.event_id}")
            return False
        
        return True
    
    def _compute_content_hash(self) -> str:
        """Compute SHA-256 hash of record content"""
        # Create deterministic content representation
        content_data = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "function_id": self.function_id,
            "execution_phase": self.execution_phase.value,
            "anomaly_type": self.anomaly_type.value,
            "duration": self.duration,
            "memory_spike_kb": self.memory_spike_kb,
            "cpu_utilization": self.cpu_utilization,
            "network_io_bytes": self.network_io_bytes,
            "source": self.source.value
        }
        
        # Create canonical JSON representation
        canonical_json = json.dumps(content_data, sort_keys=True, separators=(',', ':'))
        
        # Compute SHA-256 hash
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    
    def _generate_hmac_signature(self, secret_key: str) -> str:
        """Generate HMAC-SHA256 signature"""
        import hmac
        
        # Use content hash as message
        message = self.content_hash.encode('utf-8')
        key = secret_key.encode('utf-8')
        
        # Generate HMAC-SHA256
        signature = hmac.new(key, message, hashlib.sha256).hexdigest()
        
        return signature


# =============================================================================
# Telemetry Generation Engine
# =============================================================================

class TelemetryGenerator:
    """
    Advanced telemetry generation with realistic patterns and edge cases
    """
    
    def __init__(self, config: TelemetryConfig):
        self.config = config
        self.execution_profiles = self._load_execution_profiles()
        self.generation_history = []
        
    def _load_execution_profiles(self) -> Dict[str, Dict]:
        """Load execution profiles for different function types"""
        return {
            'lightweight': {
                'base_duration': 0.05,
                'duration_variance': 0.02,
                'base_memory_kb': 8192,
                'memory_variance': 2048,
                'base_cpu': 15.0,
                'cpu_variance': 5.0,
                'base_network_bytes': 512,
                'network_variance': 256
            },
            'standard': {
                'base_duration': 0.2,
                'duration_variance': 0.1,
                'base_memory_kb': 16384,
                'memory_variance': 4096,
                'base_cpu': 30.0,
                'cpu_variance': 10.0,
                'base_network_bytes': 2048,
                'network_variance': 1024
            },
            'intensive': {
                'base_duration': 0.8,
                'duration_variance': 0.3,
                'base_memory_kb': 65536,
                'memory_variance': 16384,
                'base_cpu': 60.0,
                'cpu_variance': 20.0,
                'base_network_bytes': 8192,
                'network_variance': 4096
            },
            'ml_inference': {
                'base_duration': 1.2,
                'duration_variance': 0.4,
                'base_memory_kb': 131072,
                'memory_variance': 32768,
                'base_cpu': 80.0,
                'cpu_variance': 15.0,
                'base_network_bytes': 16384,
                'network_variance': 8192
            }
        }
    
    async def create_normal_telemetry(self, event: Dict, context: Any) -> TelemetryRecord:
        """Generate normal telemetry based on execution context"""
        
        # Determine execution profile
        profile_name = self._determine_profile(event, context)
        profile = self.execution_profiles.get(profile_name, self.execution_profiles['standard'])
        
        # Extract basic information
        event_id = getattr(context, 'aws_request_id', str(uuid.uuid4()))
        function_id = getattr(context, 'function_name', event.get('function_id', 'unknown'))
        execution_phase = ExecutionPhase(event.get('execution_phase', 'invoke'))
        anomaly_type = AnomalyType(event.get('anomaly', 'benign'))
        
        # Generate realistic metrics
        metrics = self._generate_realistic_metrics(profile, anomaly_type, execution_phase)
        
        # Determine fallback mode
        fallback_mode = self._should_enter_fallback_mode(event, metrics)
        
        # Extract payload information
        payload_info = self._analyze_payload(event)
        
        # Create telemetry record
        telemetry = TelemetryRecord(
            event_id=event_id,
            timestamp=time.time(),
            function_id=function_id,
            execution_phase=execution_phase,
            anomaly_type=anomaly_type,
            duration=metrics['duration'],
            memory_spike_kb=metrics['memory_kb'],
            cpu_utilization=metrics['cpu_percent'],
            network_io_bytes=metrics['network_bytes'],
            fallback_mode=fallback_mode,
            source=TelemetrySource.SCAFAD_LAYER0,
            concurrency_id=event.get('concurrency_id', self._generate_concurrency_id()),
            container_id=self._get_container_id(),
            region=self._get_region(),
            runtime_version=self._get_runtime_version(),
            trigger_type=payload_info['trigger_type'],
            payload_size_bytes=payload_info['size_bytes'],
            payload_hash=payload_info['hash'],
            confidence_level=self._calculate_confidence_level(metrics, fallback_mode)
        )
        
        # Add contextual tags
        self._add_contextual_tags(telemetry, event, context, profile_name)
        
        # Record generation history
        self.generation_history.append({
            'timestamp': telemetry.timestamp,
            'anomaly_type': anomaly_type.value,
            'profile': profile_name,
            'fallback': fallback_mode
        })
        
        return telemetry
    
    def _determine_profile(self, event: Dict, context: Any) -> str:
        """Determine execution profile based on context"""
        
        # Check explicit profile specification
        if 'function_profile_id' in event:
            profile = event['function_profile_id']
            if profile in self.execution_profiles:
                return profile
        
        # Infer from function name
        function_name = getattr(context, 'function_name', '').lower()
        
        if any(keyword in function_name for keyword in ['ml', 'model', 'inference', 'predict']):
            return 'ml_inference'
        elif any(keyword in function_name for keyword in ['process', 'transform', 'compute']):
            return 'intensive'
        elif any(keyword in function_name for keyword in ['auth', 'validate', 'check']):
            return 'lightweight'
        else:
            return 'standard'
    
    def _generate_realistic_metrics(self, profile: Dict, anomaly_type: AnomalyType, 
                                  execution_phase: ExecutionPhase) -> Dict:
        """Generate realistic execution metrics with proper correlations"""
        
        # Base metrics from profile
        duration = max(0.001, random.gauss(profile['base_duration'], profile['duration_variance']))
        memory_kb = max(1024, int(random.gauss(profile['base_memory_kb'], profile['memory_variance'])))
        cpu_percent = max(0.0, min(100.0, random.gauss(profile['base_cpu'], profile['cpu_variance'])))
        network_bytes = max(0, int(random.gauss(profile['base_network_bytes'], profile['network_variance'])))
        
        # Apply execution phase adjustments
        if execution_phase == ExecutionPhase.INIT:
            duration *= random.uniform(1.5, 3.0)  # Init takes longer
            memory_kb = int(memory_kb * random.uniform(0.6, 0.8))  # Less memory during init
            cpu_percent *= random.uniform(0.7, 1.2)
        elif execution_phase == ExecutionPhase.SHUTDOWN:
            duration *= random.uniform(0.1, 0.3)  # Shutdown is fast
            memory_kb = int(memory_kb * random.uniform(0.3, 0.6))  # Memory cleanup
            cpu_percent *= random.uniform(0.2, 0.5)
        
        # Apply anomaly-specific adjustments
        if anomaly_type == AnomalyType.COLD_START:
            duration *= random.uniform(2.0, 5.0)
            memory_kb = int(memory_kb * random.uniform(1.5, 2.5))
            cpu_percent *= random.uniform(1.2, 1.8)
        elif anomaly_type == AnomalyType.CPU_BURST:
            cpu_percent = random.uniform(80.0, 98.0)
            duration *= random.uniform(1.2, 2.0)
        elif anomaly_type == AnomalyType.MEMORY_SPIKE:
            memory_kb = int(memory_kb * random.uniform(3.0, 8.0))
            duration *= random.uniform(1.1, 1.5)
        elif anomaly_type == AnomalyType.IO_INTENSIVE:
            network_bytes = int(network_bytes * random.uniform(5.0, 20.0))
            duration *= random.uniform(1.5, 4.0)
        elif anomaly_type == AnomalyType.TIMEOUT_ANOMALY:
            duration = random.uniform(self.config.timeout_threshold_seconds * 0.9, 
                                    self.config.timeout_threshold_seconds * 2.0)
        
        # Ensure realistic correlations
        if cpu_percent > 80.0:
            # High CPU usage typically increases duration
            duration *= random.uniform(1.1, 1.4)
        
        if memory_kb > profile['base_memory_kb'] * 2:
            # High memory usage may increase duration
            duration *= random.uniform(1.05, 1.2)
        
        return {
            'duration': duration,
            'memory_kb': memory_kb,
            'cpu_percent': cpu_percent,
            'network_bytes': network_bytes
        }
    
    def _should_enter_fallback_mode(self, event: Dict, metrics: Dict) -> bool:
        """Determine if fallback mode should be activated"""
        
        # Explicit fallback request
        if event.get('force_starvation', False) or event.get('simulate_failure', False):
            return True
        
        # Timeout condition
        if metrics['duration'] > self.config.timeout_threshold_seconds:
            return True
        
        # Memory limit exceeded
        if metrics['memory_kb'] > self.config.max_memory_spike_mb * 1024:
            return True
        
        # Random failure simulation (very low probability)
        if random.random() < 0.001:  # 0.1% chance
            return True
        
        return False
    
    def _analyze_payload(self, event: Dict) -> Dict:
        """Analyze event payload for telemetry metadata"""
        
        payload_str = json.dumps(event, default=str, sort_keys=True)
        payload_bytes = len(payload_str.encode('utf-8'))
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()[:16]
        
        # Determine trigger type
        trigger_type = self._identify_trigger_type(event)
        
        return {
            'size_bytes': payload_bytes,
            'hash': payload_hash,
            'trigger_type': trigger_type
        }
    
    def _identify_trigger_type(self, event: Dict) -> str:
        """Identify the trigger type from event structure"""
        
        if 'Records' in event:
            records = event['Records']
            if records and isinstance(records, list):
                first_record = records[0]
                event_source = first_record.get('eventSource', '')
                
                if 's3' in event_source.lower():
                    return 'S3'
                elif 'dynamodb' in event_source.lower():
                    return 'DynamoDB'
                elif 'kinesis' in event_source.lower():
                    return 'Kinesis'
                elif 'sns' in event_source.lower():
                    return 'SNS'
                elif 'sqs' in event_source.lower():
                    return 'SQS'
                else:
                    return 'EventBridge'
        
        elif 'httpMethod' in event or 'requestContext' in event:
            return 'API_Gateway'
        elif 'source' in event and event['source'].startswith('aws.'):
            return 'CloudWatch_Events'
        elif 'time' in event and 'source' in event:
            return 'Scheduled_Event'
        elif event.get('test_mode', False):
            return 'Test_Invocation'
        else:
            return 'Direct_Invocation'
    
    def _generate_concurrency_id(self) -> str:
        """Generate concurrency identifier"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    def _get_container_id(self) -> Optional[str]:
        """Get container identifier"""
        import os
        return os.environ.get('AWS_LAMBDA_LOG_STREAM_NAME', f"container-{random.randint(1000, 9999)}")
    
    def _get_region(self) -> Optional[str]:
        """Get AWS region"""
        import os
        return os.environ.get('AWS_REGION', 'us-east-1')
    
    def _get_runtime_version(self) -> Optional[str]:
        """Get runtime version"""
        import sys
        return f"python{sys.version_info.major}.{sys.version_info.minor}"
    
    def _calculate_confidence_level(self, metrics: Dict, fallback_mode: bool) -> float:
        """Calculate confidence level of the telemetry"""
        
        confidence = 1.0
        
        # Reduce confidence for fallback mode
        if fallback_mode:
            confidence *= 0.7
        
        # Reduce confidence for extreme values
        if metrics['cpu_percent'] > 95.0:
            confidence *= 0.9
        
        if metrics['duration'] > 10.0:
            confidence *= 0.8
        
        return max(0.1, confidence)
    
    def _add_contextual_tags(self, telemetry: TelemetryRecord, event: Dict, 
                           context: Any, profile_name: str) -> None:
        """Add contextual tags to telemetry"""
        
        telemetry.add_tag('profile', profile_name)
        telemetry.add_tag('trigger_type', telemetry.trigger_type or 'unknown')
        
        # Add execution context tags
        if hasattr(context, 'memory_limit_in_mb'):
            telemetry.add_tag('memory_limit_mb', str(context.memory_limit_in_mb))
        
        # Add test mode tag
        if event.get('test_mode', False):
            telemetry.add_tag('test_mode', 'true')
        
        # Add environment tags
        import os
        if 'AWS_LAMBDA_FUNCTION_VERSION' in os.environ:
            telemetry.add_tag('function_version', os.environ['AWS_LAMBDA_FUNCTION_VERSION'])
    
    async def create_fallback_telemetry(self, event: Dict, context: Any, 
                                      error: Exception) -> TelemetryRecord:
        """Generate minimal fallback telemetry when normal generation fails"""
        
        # Extract minimal required information
        event_id = getattr(context, 'aws_request_id', str(uuid.uuid4()))
        function_id = getattr(context, 'function_name', event.get('function_id', 'unknown'))
        
        # Create minimal telemetry record
        telemetry = TelemetryRecord(
            event_id=event_id,
            timestamp=time.time(),
            function_id=function_id,
            execution_phase=ExecutionPhase.ERROR,
            anomaly_type=AnomalyType.EXECUTION_FAILURE,
            duration=0.0,
            memory_spike_kb=1024,  # Minimal memory estimate
            cpu_utilization=0.0,
            network_io_bytes=0,
            fallback_mode=True,
            source=TelemetrySource.FALLBACK_GENERATOR,
            concurrency_id='ERR',
            confidence_level=0.3,  # Low confidence for fallback
            data_quality_score=0.2  # Poor quality due to fallback
        )
        
        # Add error information as custom fields
        telemetry.add_custom_field('error_type', type(error).__name__)
        telemetry.add_custom_field('error_message', str(error)[:200])  # Truncate long messages
        telemetry.add_custom_field('fallback_reason', 'generation_failure')
        
        # Add fallback tag
        telemetry.add_tag('fallback_mode', 'true')
        telemetry.add_tag('error_type', type(error).__name__)
        
        return telemetry


# =============================================================================
# Multi-Channel Telemetry Emission System
# =============================================================================

class TelemetryChannel:
    """Base class for telemetry emission channels"""
    
    def __init__(self, name: str, config: TelemetryConfig):
        self.name = name
        self.config = config
        self.emission_count = 0
        self.failure_count = 0
        self.last_emission_time = None
        self.avg_emission_latency = 0.0
    
    async def emit(self, telemetry: TelemetryRecord) -> bool:
        """Emit telemetry record. Returns True if successful."""
        start_time = time.time()
        
        try:
            success = await self._do_emit(telemetry)
            
            if success:
                self.emission_count += 1
                self.last_emission_time = time.time()
                
                # Update average latency
                latency = time.time() - start_time
                if self.emission_count == 1:
                    self.avg_emission_latency = latency
                else:
                    # Exponential moving average
                    alpha = 0.1
                    self.avg_emission_latency = (alpha * latency + 
                                               (1 - alpha) * self.avg_emission_latency)
            else:
                self.failure_count += 1
            
            return success
            
        except Exception as e:
            logger.error(f"Channel {self.name} emission failed: {e}")
            self.failure_count += 1
            return False
    
    async def _do_emit(self, telemetry: TelemetryRecord) -> bool:
        """Subclasses must implement actual emission logic"""
        raise NotImplementedError
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get channel health metrics"""
        total_attempts = self.emission_count + self.failure_count
        success_rate = self.emission_count / total_attempts if total_attempts > 0 else 0.0
        
        return {
            'name': self.name,
            'emission_count': self.emission_count,
            'failure_count': self.failure_count,
            'success_rate': success_rate,
            'avg_latency_ms': self.avg_emission_latency * 1000,
            'last_emission_time': self.last_emission_time
        }


class PrimaryTelemetryChannel(TelemetryChannel):
    """Primary telemetry channel (structured JSON output)"""
    
    def __init__(self, config: TelemetryConfig):
        super().__init__('primary', config)
        self.enable_compression = False
        self.enable_encryption = False
    
    async def _do_emit(self, telemetry: TelemetryRecord) -> bool:
        """Emit to primary channel with structured format"""
        
        # Convert to emission format
        emission_data = self._format_for_emission(telemetry)
        
        # Apply compression if enabled
        if self.enable_compression:
            emission_data = self._compress_data(emission_data)
        
        # Apply encryption if enabled
        if self.enable_encryption:
            emission_data = self._encrypt_data(emission_data)
        
        # Emit (in production, this would go to Kinesis/Kafka/etc.)
        self._safe_print(json.dumps(emission_data))
        
        return True
    
    def _format_for_emission(self, telemetry: TelemetryRecord) -> Dict[str, Any]:
        """Format telemetry for emission"""
        
        base_data = telemetry.to_dict()
        
        # Add emission metadata
        base_data['emission_metadata'] = {
            'channel': self.name,
            'emission_timestamp': time.time(),
            'format_version': '1.0',
            'compression': self.enable_compression,
            'encryption': self.enable_encryption
        }
        
        return base_data
    
    def _compress_data(self, data: Dict) -> Dict:
        """Apply compression (placeholder)"""
        # In production, would use actual compression
        data['_compressed'] = True
        return data
    
    def _encrypt_data(self, data: Dict) -> Dict:
        """Apply encryption (placeholder)"""
        # In production, would use actual encryption
        data['_encrypted'] = True
        return data
    
    def _safe_print(self, message: str):
        """Safe print with error handling"""
        try:
            print(message)
        except Exception:
            # Fallback to stderr
            print(message, file=sys.stderr)


class CloudWatchChannel(TelemetryChannel):
    """CloudWatch Logs fallback channel"""
    
    def __init__(self, config: TelemetryConfig):
        super().__init__('cloudwatch', config)
        self.log_group = '/aws/lambda/scafad-layer0'
        self.structured_logging = True
    
    async def _do_emit(self, telemetry: TelemetryRecord) -> bool:
        """Emit to CloudWatch with structured logging"""
        
        if self.structured_logging:
            # Structured CloudWatch log
            log_entry = {
                'timestamp': telemetry.timestamp,
                'level': self._get_log_level(telemetry),
                'event_type': 'scafad_telemetry',
                'function_id': telemetry.function_id,
                'event_id': telemetry.event_id,
                'anomaly_type': telemetry.anomaly_type.value,
                'anomaly_category': telemetry.anomaly_type.category,
                'severity_level': telemetry.anomaly_type.severity_level,
                'execution_phase': telemetry.execution_phase.value,
                'duration_ms': telemetry.duration * 1000,
                'memory_kb': telemetry.memory_spike_kb,
                'cpu_percent': telemetry.cpu_utilization,
                'network_bytes': telemetry.network_io_bytes,
                'fallback_mode': telemetry.fallback_mode,
                'risk_score': telemetry.compute_overall_risk_score(),
                'is_critical': telemetry.is_critical(),
                'source': telemetry.source.value,
                'confidence': telemetry.confidence_level
            }
            
            self._safe_print(f"[CLOUDWATCH] {json.dumps(log_entry)}")
        else:
            # Simple log message
            message = (
                f"SCAFAD: {telemetry.function_id} | {telemetry.anomaly_type.value} | "
                f"{telemetry.duration*1000:.1f}ms | {telemetry.memory_spike_kb}KB"
            )
            self._safe_print(f"[CLOUDWATCH] {message}")
        
        return True
    
    def _get_log_level(self, telemetry: TelemetryRecord) -> str:
        """Determine appropriate log level"""
        if telemetry.is_critical():
            return 'ERROR'
        elif telemetry.anomaly_type != AnomalyType.BENIGN:
            return 'WARN'
        else:
            return 'INFO'
    
    def _safe_print(self, message: str):
        """Safe print with error handling"""
        try:
            print(message)
        except Exception:
            print(message, file=sys.stderr)


class SideTraceChannel(TelemetryChannel):
    """Human-readable side trace channel for debugging"""
    
    def __init__(self, config: TelemetryConfig):
        super().__init__('side_trace', config)
        self.verbosity = VerbosityLevel.NORMAL
    
    async def _do_emit(self, telemetry: TelemetryRecord) -> bool:
        """Emit human-readable trace"""
        
        if not self._should_emit_trace(telemetry):
            return True  # Skip emission but consider it successful
        
        trace_message = self._format_trace_message(telemetry)
        self._safe_print(trace_message)
        
        return True
    
    def _should_emit_trace(self, telemetry: TelemetryRecord) -> bool:
        """Determine if trace should be emitted based on verbosity and content"""
        
        # Always emit critical events
        if telemetry.is_critical():
            return True
        
        # Emit anomalies based on verbosity
        if telemetry.anomaly_type != AnomalyType.BENIGN:
            return self.verbosity in [VerbosityLevel.HIGH, VerbosityLevel.DEBUG]
        
        # Emit fallback mode
        if telemetry.fallback_mode:
            return True
        
        # Emit init and error phases
        if telemetry.execution_phase in [ExecutionPhase.INIT, ExecutionPhase.ERROR]:
            return self.verbosity in [VerbosityLevel.HIGH, VerbosityLevel.DEBUG]
        
        # Debug mode emits everything
        return self.verbosity == VerbosityLevel.DEBUG
    
    def _format_trace_message(self, telemetry: TelemetryRecord) -> str:
        """Format human-readable trace message"""
        
        # Base trace components
        timestamp_str = datetime.fromtimestamp(telemetry.timestamp).strftime('%H:%M:%S.%f')[:-3]
        
        # Risk indicator
        risk_score = telemetry.compute_overall_risk_score()
        if risk_score >= 0.8:
            risk_indicator = "🔴"
        elif risk_score >= 0.5:
            risk_indicator = "🟡"
        else:
            risk_indicator = "🟢"
        
        # Anomaly indicator
        anomaly_indicator = "⚠️" if telemetry.anomaly_type != AnomalyType.BENIGN else "✅"
        
        # Fallback indicator
        fallback_indicator = "🔄" if telemetry.fallback_mode else ""
        
        # Build trace message
        base_message = (
            f"[SCAFAD_TRACE] {timestamp_str} {risk_indicator}{anomaly_indicator}{fallback_indicator} "
            f"func={telemetry.function_id} "
            f"phase={telemetry.execution_phase.value} "
            f"anomaly={telemetry.anomaly_type.value} "
            f"duration={telemetry.duration*1000:.1f}ms "
            f"memory={telemetry.memory_spike_kb}KB "
            f"cpu={telemetry.cpu_utilization:.1f}%"
        )
        
        # Add additional details for high verbosity
        if self.verbosity in [VerbosityLevel.HIGH, VerbosityLevel.DEBUG]:
            additional_details = (
                f" risk={risk_score:.3f} "
                f"confidence={telemetry.confidence_level:.3f} "
                f"source={telemetry.source.value}"
            )
            base_message += additional_details
        
        # Add custom fields for debug mode
        if self.verbosity == VerbosityLevel.DEBUG and telemetry.custom_fields:
            custom_str = " custom=" + json.dumps(telemetry.custom_fields, separators=(',', ':'))
            base_message += custom_str
        
        return base_message
    
    def _safe_print(self, message: str):
        """Safe print with error handling"""
        try:
            print(message)
        except Exception:
            print(message, file=sys.stderr)


class MetricsChannel(TelemetryChannel):
    """Structured metrics channel for monitoring systems"""
    
    def __init__(self, config: TelemetryConfig):
        super().__init__('metrics', config)
        self.metric_aggregation = {}
        self.last_aggregation_time = time.time()
        self.aggregation_interval = 60  # seconds
    
    async def _do_emit(self, telemetry: TelemetryRecord) -> bool:
        """Emit structured metrics"""
        
        # Extract metrics
        metrics = self._extract_metrics(telemetry)
        
        # Update aggregation
        self._update_aggregation(metrics)
        
        # Emit individual metrics
        for metric_name, metric_value in metrics.items():
            metric_record = {
                'metric_name': f"scafad.layer0.{metric_name}",
                'value': metric_value,
                'timestamp': telemetry.timestamp,
                'unit': self._get_metric_unit(metric_name),
                'dimensions': {
                    'function_id': telemetry.function_id,
                    'anomaly_type': telemetry.anomaly_type.value,
                    'execution_phase': telemetry.execution_phase.value,
                    'source': telemetry.source.value
                }
            }
            
            self._safe_print(f"[METRICS] {json.dumps(metric_record)}")
        
        # Emit aggregated metrics if interval elapsed
        if time.time() - self.last_aggregation_time > self.aggregation_interval:
            await self._emit_aggregated_metrics()
        
        return True
    
    def _extract_metrics(self, telemetry: TelemetryRecord) -> Dict[str, Union[float, int]]:
        """Extract metrics from telemetry record"""
        
        return {
            'duration_ms': telemetry.duration * 1000,
            'memory_kb': telemetry.memory_spike_kb,
            'cpu_utilization': telemetry.cpu_utilization,
            'network_io_bytes': telemetry.network_io_bytes,
            'risk_score': telemetry.compute_overall_risk_score(),
            'confidence_level': telemetry.confidence_level,
            'anomaly_severity': telemetry.anomaly_type.severity_level,
            'is_critical': int(telemetry.is_critical()),
            'is_fallback': int(telemetry.fallback_mode),
            'emission_priority': telemetry.get_emission_priority()
        }
    
    def _get_metric_unit(self, metric_name: str) -> str:
        """Get appropriate unit for metric"""
        
        unit_mapping = {
            'duration_ms': 'Milliseconds',
            'memory_kb': 'Kilobytes',
            'cpu_utilization': 'Percent',
            'network_io_bytes': 'Bytes',
            'risk_score': 'None',
            'confidence_level': 'None',
            'anomaly_severity': 'None',
            'is_critical': 'Count',
            'is_fallback': 'Count',
            'emission_priority': 'None'
        }
        
        return unit_mapping.get(metric_name, 'None')
    
    def _update_aggregation(self, metrics: Dict[str, Union[float, int]]):
        """Update metric aggregations"""
        
        for metric_name, value in metrics.items():
            if metric_name not in self.metric_aggregation:
                self.metric_aggregation[metric_name] = {
                    'count': 0,
                    'sum': 0,
                    'min': float('inf'),
                    'max': float('-inf'),
                    'avg': 0
                }
            
            agg = self.metric_aggregation[metric_name]
            agg['count'] += 1
            agg['sum'] += value
            agg['min'] = min(agg['min'], value)
            agg['max'] = max(agg['max'], value)
            agg['avg'] = agg['sum'] / agg['count']
    
    async def _emit_aggregated_metrics(self):
        """Emit aggregated metrics"""
        
        aggregation_period = time.time() - self.last_aggregation_time
        
        for metric_name, agg in self.metric_aggregation.items():
            
            # Emit aggregated statistics
            for stat_name, stat_value in agg.items():
                if stat_name == 'count':
                    continue
                
                aggregated_metric = {
                    'metric_name': f"scafad.layer0.{metric_name}.{stat_name}",
                    'value': stat_value,
                    'timestamp': time.time(),
                    'unit': self._get_metric_unit(metric_name),
                    'dimensions': {
                        'aggregation_period_s': aggregation_period,
                        'sample_count': agg['count']
                    }
                }
                
                self._safe_print(f"[METRICS_AGG] {json.dumps(aggregated_metric)}")
        
        # Reset aggregation
        self.metric_aggregation = {}
        self.last_aggregation_time = time.time()
    
    def _safe_print(self, message: str):
        """Safe print with error handling"""
        try:
            print(message)
        except Exception:
            print(message, file=sys.stderr)


# =============================================================================
# Multi-Channel Telemetry Manager
# =============================================================================

class MultiChannelTelemetry:
    """
    Orchestrates telemetry emission across multiple channels with fallback logic
    """
    
    def __init__(self, config: Layer0Config):
        self.config = config
        self.telemetry_config = config.telemetry
        self.generator = TelemetryGenerator(self.telemetry_config)
        
        # Initialize channels
        self.channels = {}
        self._initialize_channels()
        
        # Emission statistics
        self.emission_stats = {
            'total_emissions': 0,
            'successful_emissions': 0,
            'failed_emissions': 0,
            'fallback_emissions': 0,
            'channel_failures': defaultdict(int)
        }
        
        # Priority queue for emission
        self.emission_queue = asyncio.PriorityQueue()
        self.emission_worker_running = False
        
        # Channel health tracking
        self.channel_health = {}
        self.performance_history = []
    
    def _initialize_channels(self):
        """Initialize emission channels based on configuration"""
        
        if self.telemetry_config.enable_primary_channel:
            self.channels['primary'] = PrimaryTelemetryChannel(self.telemetry_config)
        
        if self.telemetry_config.enable_cloudwatch_fallback:
            self.channels['cloudwatch'] = CloudWatchChannel(self.telemetry_config)
        
        if self.telemetry_config.enable_side_trace:
            side_trace = SideTraceChannel(self.telemetry_config)
            side_trace.verbosity = self.config.verbosity_level
            self.channels['side_trace'] = side_trace
        
        if self.telemetry_config.enable_metrics_channel:
            self.channels['metrics'] = MetricsChannel(self.telemetry_config)
        
        logger.info(f"Initialized {len(self.channels)} telemetry channels: {list(self.channels.keys())}")
    
    async def emit_telemetry(self, telemetry: TelemetryRecord) -> Dict[str, Any]:
        """
        Emit telemetry through all configured channels with intelligent fallback
        """
        
        self.emission_stats['total_emissions'] += 1
        
        emission_results = {}
        successful_channels = []
        failed_channels = []
        
        # Determine emission strategy based on priority
        priority = telemetry.get_emission_priority()
        
        if priority >= 8:  # High priority - immediate emission
            emission_results = await self._emit_immediate(telemetry)
        else:  # Normal priority - route through queue (I-10)
            emission_results = await self._emit_with_queue(telemetry)
        
        # Analyze results
        for channel_name, result in emission_results.items():
            if result['success']:
                successful_channels.append(channel_name)
                telemetry.mark_emission_attempt(channel_name, success=True)
            else:
                failed_channels.append(channel_name)
                telemetry.mark_emission_attempt(channel_name, success=False)
                self.emission_stats['channel_failures'][channel_name] += 1
        
        # Update statistics
        if successful_channels:
            self.emission_stats['successful_emissions'] += 1
        else:
            self.emission_stats['failed_emissions'] += 1
        
        return {
            'total_channels': len(self.channels),
            'successful_channels': len(successful_channels),
            'failed_channels': len(failed_channels),
            'successful_channel_names': successful_channels,
            'failed_channel_names': failed_channels,
            'emission_results': emission_results,
            'overall_success': len(successful_channels) > 0
        }
    
    async def _emit_with_queue(self, telemetry: TelemetryRecord) -> Dict[str, Dict]:
        """
        Emit using the priority queue for normal-priority records (I-10).

        Places the record on the emission_queue and processes it, giving the
        scheduler an opportunity to batch or re-order before committing to channels.
        Falls back to immediate emission if the queue is unavailable.
        """
        try:
            await self.emission_queue.put((telemetry.get_emission_priority(), telemetry))
            _, queued_record = await self.emission_queue.get()
            return await self._emit_immediate(queued_record)
        except Exception:  # noqa: BLE001
            # Queue unavailable — degrade gracefully to direct emission
            return await self._emit_immediate(telemetry)

    async def _emit_immediate(self, telemetry: TelemetryRecord) -> Dict[str, Dict]:
        """Emit immediately to all channels with intelligent failover"""
        
        results = {}
        
        # Priority order for channel attempts
        channel_priority = ['primary', 'cloudwatch', 'side_trace', 'metrics']
        
        # Try primary channel first (most important)
        primary_success = False
        if 'primary' in self.channels:
            results['primary'] = await self._emit_to_channel('primary', telemetry)
            primary_success = results['primary']['success']
        
        # If primary fails, immediately attempt failover
        if not primary_success:
            logger.warning("Primary channel emission failed, triggering failover sequence")
            await self._trigger_failover_sequence(telemetry, results)
        
        # Attempt remaining channels based on configuration
        for channel_name in channel_priority[1:]:
            if channel_name in self.channels and channel_name not in results:
                results[channel_name] = await self._emit_to_channel(channel_name, telemetry)
        
        return results
    
    async def _trigger_failover_sequence(self, telemetry: TelemetryRecord, existing_results: Dict):
        """Trigger intelligent failover sequence when primary channel fails"""
        
        self.emission_stats['fallback_emissions'] += 1
        
        # Mark telemetry as in fallback mode
        telemetry.fallback_mode = True
        telemetry.add_custom_field('failover_triggered', True)
        telemetry.add_custom_field('failover_timestamp', time.time())
        
        # Try CloudWatch as immediate fallback
        if 'cloudwatch' in self.channels:
            logger.info("Attempting CloudWatch fallback emission")
            cloudwatch_result = await self._emit_to_channel('cloudwatch', telemetry, priority=True)
            existing_results['cloudwatch'] = cloudwatch_result
            
            if cloudwatch_result['success']:
                logger.info("CloudWatch failover emission successful")
                telemetry.add_custom_field('failover_success_channel', 'cloudwatch')
                return
        
        # If CloudWatch also fails, try side trace
        if 'side_trace' in self.channels:
            logger.info("Attempting side trace failover emission")  
            side_trace_result = await self._emit_to_channel('side_trace', telemetry, priority=True)
            existing_results['side_trace'] = side_trace_result
            
            if side_trace_result['success']:
                logger.info("Side trace failover emission successful")
                telemetry.add_custom_field('failover_success_channel', 'side_trace')
                return
        
        # Last resort: local file backup
        logger.error("All channels failed, attempting local file backup")
        backup_result = await self._emit_to_local_backup(telemetry)
        existing_results['local_backup'] = backup_result
        
        if backup_result['success']:
            telemetry.add_custom_field('failover_success_channel', 'local_backup')
        else:
            logger.critical("Complete telemetry emission failure - all channels failed")
            telemetry.add_custom_field('complete_emission_failure', True)
    
    async def _emit_to_local_backup(self, telemetry: TelemetryRecord) -> Dict[str, Any]:
        """Emergency local file backup when all channels fail"""
        
        try:
            backup_file = Path("telemetry_backup.jsonl")
            telemetry_data = {
                'timestamp': telemetry.timestamp,
                'event_id': telemetry.event_id,
                'function_id': telemetry.function_id,
                'anomaly_type': telemetry.anomaly_type.value,
                'fallback_mode': True,
                'backup_emission': True,
                'telemetry_record': telemetry.to_dict()
            }
            
            # Append to backup file
            with open(backup_file, 'a') as f:
                f.write(json.dumps(telemetry_data) + '\n')
            
            logger.info(f"Telemetry backed up locally to {backup_file}")
            
            return {
                'success': True,
                'channel': 'local_backup',
                'backup_file': str(backup_file),
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Local backup emission failed: {e}")
            return {
                'success': False,
                'channel': 'local_backup', 
                'error': str(e),
                'timestamp': time.time()
            }
    
    async def handle_channel_failure(self, channel_name: str) -> bool:
        """Handle individual channel failures with monitoring and recovery"""
        
        logger.warning(f"Channel failure detected: {channel_name}")
        
        # Increment failure counter
        self.emission_stats['channel_failures'][channel_name] += 1
        
        # Check if channel needs to be disabled
        failure_threshold = 5  # Disable after 5 consecutive failures
        if self.emission_stats['channel_failures'][channel_name] >= failure_threshold:
            logger.error(f"Channel {channel_name} exceeded failure threshold, disabling temporarily")
            await self._disable_channel_temporarily(channel_name)
            return False
        
        # Attempt channel health check
        if hasattr(self.channels.get(channel_name), 'health_check'):
            try:
                health_status = await self.channels[channel_name].health_check()
                if health_status['healthy']:
                    logger.info(f"Channel {channel_name} health check passed, resetting failure count")
                    self.emission_stats['channel_failures'][channel_name] = 0
                    return True
            except Exception as e:
                logger.error(f"Health check failed for channel {channel_name}: {e}")
        
        return True
    
    async def _disable_channel_temporarily(self, channel_name: str):
        """Temporarily disable a failing channel"""
        
        if channel_name in self.channels:
            # Store reference for potential recovery
            disabled_channel = self.channels.pop(channel_name)
            
            # Schedule recovery attempt in 5 minutes
            asyncio.create_task(self._schedule_channel_recovery(channel_name, disabled_channel, 300))
            
            logger.warning(f"Channel {channel_name} temporarily disabled, recovery scheduled in 5 minutes")
    
    async def _schedule_channel_recovery(self, channel_name: str, channel_instance: Any, delay_seconds: int):
        """Schedule channel recovery after temporary disable"""
        
        await asyncio.sleep(delay_seconds)
        
        try:
            # Attempt to restore channel
            if hasattr(channel_instance, 'health_check'):
                health_status = await channel_instance.health_check()
                if health_status['healthy']:
                    self.channels[channel_name] = channel_instance
                    self.emission_stats['channel_failures'][channel_name] = 0
                    logger.info(f"Channel {channel_name} successfully recovered and re-enabled")
                else:
                    logger.warning(f"Channel {channel_name} recovery failed - health check unsuccessful")
                    # Schedule another recovery attempt in 10 minutes
                    asyncio.create_task(self._schedule_channel_recovery(channel_name, channel_instance, 600))
            else:
                # No health check available, restore anyway
                self.channels[channel_name] = channel_instance
                self.emission_stats['channel_failures'][channel_name] = 0
                logger.info(f"Channel {channel_name} restored (no health check available)")
        
        except Exception as e:
            logger.error(f"Channel recovery failed for {channel_name}: {e}")
            # Schedule another recovery attempt in 15 minutes
            asyncio.create_task(self._schedule_channel_recovery(channel_name, channel_instance, 900))
    
    def monitor_channel_health(self) -> Dict[str, Any]:
        """Monitor health of all channels and return status"""
        
        channel_health = {}
        
        for channel_name, channel in self.channels.items():
            failure_count = self.emission_stats['channel_failures'][channel_name]
            
            health_status = {
                'channel_name': channel_name,
                'active': True,
                'failure_count': failure_count,
                'health_score': max(0.0, 1.0 - (failure_count / 10.0)),  # Decreases with failures
                'last_failure': None
            }
            
            # Add channel-specific health information
            if hasattr(channel, 'get_health_info'):
                try:
                    channel_health_info = channel.get_health_info()
                    health_status.update(channel_health_info)
                except Exception as e:
                    health_status['health_check_error'] = str(e)
            
            channel_health[channel_name] = health_status
        
        return {
            'overall_health': self._calculate_overall_health(channel_health),
            'channel_details': channel_health,
            'total_channels': len(self.channels),
            'active_channels': len([c for c in channel_health.values() if c['active']]),
            'emission_stats': self.emission_stats.copy()
        }
    
    def _calculate_overall_health(self, channel_health: Dict) -> float:
        """Calculate overall telemetry system health score"""
        
        if not channel_health:
            return 0.0
        
        health_scores = [ch['health_score'] for ch in channel_health.values()]
        average_health = sum(health_scores) / len(health_scores)
        
        # Bonus for having multiple healthy channels
        healthy_channels = len([ch for ch in channel_health.values() if ch['health_score'] > 0.7])
        redundancy_bonus = min(0.2, healthy_channels * 0.05)
        
        return min(1.0, average_health + redundancy_bonus)
    
    async def _emit_to_channel(self, channel_name: str, telemetry: TelemetryRecord, priority: bool = False) -> Dict[str, Any]:
        """Emit telemetry to a specific channel with error handling"""
        
        if channel_name not in self.channels:
            return {
                'success': False,
                'error': f'Channel {channel_name} not available',
                'channel': channel_name,
                'timestamp': time.time()
            }
        
        try:
            channel = self.channels[channel_name]
            
            # Attempt emission
            if hasattr(channel, 'emit_async'):
                result = await channel.emit_async(telemetry, priority=priority)
            elif hasattr(channel, 'emit'):
                result = await channel.emit(telemetry)
            else:
                # Fallback for simple channels
                result = {'success': True, 'timestamp': time.time()}
            
            # Ensure result has required fields
            if isinstance(result, bool):
                result = {'success': result, 'timestamp': time.time()}
            
            result['channel'] = channel_name
            return result
            
        except Exception as e:
            logger.error(f"Channel {channel_name} emission failed: {e}")
            await self.handle_channel_failure(channel_name)
            
            return {
                'success': False,
                'error': str(e),
                'channel': channel_name,
                'timestamp': time.time()
            }
    
    async def create_normal_telemetry(self, event: Dict, context: Any) -> TelemetryRecord:
        """Create normal telemetry record (wrapper for generator)"""
        return await self.generator.create_normal_telemetry(event, context)
    
    async def create_fallback_telemetry(self, event: Dict, context: Any, error: Exception) -> TelemetryRecord:
        """Create minimal fallback telemetry when processing fails"""
        
        try:
            # Create minimal telemetry with error information
            fallback_telemetry = TelemetryRecord(
                event_id=f"fallback_{int(time.time())}_{random.randint(1000, 9999)}",
                timestamp=time.time(),
                function_id=getattr(context, 'function_name', 'unknown'),
                execution_phase=ExecutionPhase.ERROR,
                anomaly_type=AnomalyType.EXECUTION_FAILURE,
                duration=0.001,  # Minimal duration
                memory_spike_kb=1024,  # Minimal memory
                cpu_utilization=0.0,
                network_io_bytes=0,
                fallback_mode=True,
                source=TelemetrySource.FALLBACK_GENERATOR,
                concurrency_id=f"fallback_{int(time.time() * 1000)}",
            )
            
            # Add error context
            fallback_telemetry.add_custom_field('error_message', str(error))
            fallback_telemetry.add_custom_field('error_type', type(error).__name__)
            fallback_telemetry.add_custom_field('original_event', json.dumps(event)[:500])  # Truncate
            
            return fallback_telemetry
            
        except Exception as fallback_error:
            logger.error(f"Fallback telemetry creation failed: {fallback_error}")
            
            # Ultra-minimal fallback
            return TelemetryRecord(
                event_id=f"emergency_{int(time.time())}",
                timestamp=time.time(),
                function_id="emergency_fallback",
                execution_phase=ExecutionPhase.ERROR,
                anomaly_type=AnomalyType.EXECUTION_FAILURE,
                duration=0.001,
                memory_spike_kb=1024,
                cpu_utilization=0.0,
                network_io_bytes=0,
                fallback_mode=True,
                source=TelemetrySource.FALLBACK_GENERATOR,
                concurrency_id=f"emergency_{int(time.time() * 1000)}",
            )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current telemetry system performance metrics"""
        
        total_emissions = self.emission_stats['total_emissions']
        if total_emissions == 0:
            return self.emission_stats
        
        return {
            **self.emission_stats,
            'success_rate': self.emission_stats['successful_emissions'] / total_emissions,
            'fallback_rate': self.emission_stats['fallback_emissions'] / total_emissions,
            'channel_health_score': sum(self.channel_health.values()) / len(self.channel_health) if self.channel_health else 0.0,
            'average_latency_ms': sum(self.performance_history) / len(self.performance_history) * 1000 if self.performance_history else 0.0,
            'healthy_channels': [name for name, health in self.channel_health.items() if health > 0.7],
            'degraded_channels': [name for name, health in self.channel_health.items() if 0.3 <= health <= 0.7],
            'failed_channels': [name for name, health in self.channel_health.items() if health < 0.3]
        }


# =============================================================================
# Fallback Telemetry Processor  
# =============================================================================

class FallbackTelemetryProcessor:
    """
    Emergency telemetry processing when all channels fail
    """
    
    def __init__(self, config: TelemetryConfig):
        self.config = config
        self.local_buffer = []
        self.buffer_limit = 1000
        self.emergency_file = Path("emergency_telemetry.jsonl")
        
    async def process_emergency_telemetry(self, telemetry: TelemetryRecord) -> Dict[str, Any]:
        """Process telemetry when all standard channels are down"""
        
        try:
            # Add to local buffer
            telemetry_data = telemetry.to_dict()
            telemetry_data['emergency_processed'] = True
            telemetry_data['emergency_timestamp'] = time.time()
            
            self.local_buffer.append(telemetry_data)
            
            # Manage buffer size
            if len(self.local_buffer) > self.buffer_limit:
                await self._flush_emergency_buffer()
            
            # Try to write to emergency file
            await self._write_to_emergency_file(telemetry_data)
            
            return {
                'success': True,
                'method': 'emergency_processing',
                'buffer_size': len(self.local_buffer),
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Emergency telemetry processing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'method': 'emergency_processing',
                'timestamp': time.time()
            }
    
    async def _write_to_emergency_file(self, telemetry_data: Dict):
        """Write telemetry to emergency file"""
        try:
            if HAS_AIOFILES:
                async with aiofiles.open(self.emergency_file, 'a') as f:
                    await f.write(json.dumps(telemetry_data) + '\n')
            else:
                # Fallback to synchronous file operations
                with open(self.emergency_file, 'a') as f:
                    f.write(json.dumps(telemetry_data) + '\n')
        except Exception as e:
            logger.warning(f"Failed to write to emergency file: {e}")
    
    async def _flush_emergency_buffer(self):
        """Flush emergency buffer when limit is reached"""
        if not self.local_buffer:
            return
        
        try:
            # Remove oldest entries to maintain buffer limit
            excess = len(self.local_buffer) - self.buffer_limit
            if excess > 0:
                self.local_buffer = self.local_buffer[excess:]
                
            logger.info(f"Emergency buffer flushed, maintaining {len(self.local_buffer)} entries")
            
        except Exception as e:
            logger.error(f"Buffer flush failed: {e}")
    
    def get_emergency_stats(self) -> Dict[str, Any]:
        """Get emergency processing statistics"""
        return {
            'buffer_size': len(self.local_buffer),
            'buffer_limit': self.buffer_limit,
            'emergency_file_exists': self.emergency_file.exists(),
            'emergency_file_size': self.emergency_file.stat().st_size if self.emergency_file.exists() else 0
        }
    
    async def _emit_to_channel_with_timeout(self, channel_name: str, telemetry: TelemetryRecord) -> Dict[str, Any]:
        """Emit to specific channel with timeout and error handling"""
        
        if channel_name not in self.channels:
            return {'success': False, 'error': f'Channel {channel_name} not found'}
        
        channel = self.channels[channel_name]
        start_time = time.time()
        
        try:
            # Apply timeout
            success = await asyncio.wait_for(
                channel.emit(telemetry),
                timeout=self.telemetry_config.emission_timeout_ms / 1000
            )
            
            emission_time = time.time() - start_time
            
            return {
                'success': success,
                'emission_time_ms': emission_time * 1000,
                'channel_health': channel.get_health_metrics()
            }
            
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': f'Emission timeout after {self.telemetry_config.emission_timeout_ms}ms'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'emission_time_ms': (time.time() - start_time) * 1000
            }
    
    async def _emit_to_channel_safe(self, channel_name: str, telemetry: TelemetryRecord) -> Dict[str, Any]:
        """Safe wrapper for channel emission that never raises exceptions"""
        try:
            return await self._emit_to_channel(channel_name, telemetry)
        except Exception as e:
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}
    
    async def create_normal_telemetry(self, event: Dict, context: Any) -> TelemetryRecord:
        """Create normal telemetry record"""
        return await self.generator.create_normal_telemetry(event, context)
    
    async def create_fallback_telemetry(self, event: Dict, context: Any, 
                                      error: Exception) -> TelemetryRecord:
        """Create fallback telemetry record"""
        self.emission_stats['fallback_emissions'] += 1
        return await self.generator.create_fallback_telemetry(event, context, error)
    
    def get_emission_statistics(self) -> Dict[str, Any]:
        """Get comprehensive emission statistics"""
        
        total = self.emission_stats['total_emissions']
        
        stats = {
            **self.emission_stats,
            'success_rate': (self.emission_stats['successful_emissions'] / total) if total > 0 else 0.0,
            'failure_rate': (self.emission_stats['failed_emissions'] / total) if total > 0 else 0.0,
            'fallback_rate': (self.emission_stats['fallback_emissions'] / total) if total > 0 else 0.0,
            'channel_health': {name: channel.get_health_metrics() 
                             for name, channel in self.channels.items()}
        }
        
        return stats
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get configuration summary"""
        return {
            'enabled_channels': list(self.channels.keys()),
            'total_channels': len(self.channels),
            'timeout_ms': self.telemetry_config.emission_timeout_ms,
            'retry_attempts': self.telemetry_config.retry_attempts,
            'batch_size': self.telemetry_config.emission_batch_size,
            'verbosity_level': self.config.verbosity_level.value
        }


# =============================================================================
# Telemetry Validation and Quality Assurance
# =============================================================================

class TelemetryValidator:
    """Validates telemetry records for quality and completeness"""
    
    def __init__(self, config: TelemetryConfig):
        self.config = config
        self.validation_rules = self._load_validation_rules()
        self.validation_stats = defaultdict(int)
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Load validation rules"""
        return {
            'required_fields': [
                'event_id', 'timestamp', 'function_id', 'execution_phase',
                'anomaly_type', 'duration', 'memory_spike_kb', 'cpu_utilization',
                'network_io_bytes', 'fallback_mode', 'source'
            ],
            'numeric_ranges': {
                'duration': (0.0, 900.0),  # 0 to 15 minutes
                'memory_spike_kb': (0, 3008 * 1024),  # 0 to 3GB in KB
                'cpu_utilization': (0.0, 100.0),
                'network_io_bytes': (0, 1024 * 1024 * 1024),  # 0 to 1GB
                'adversarial_score': (0.0, 1.0),
                'economic_risk_score': (0.0, 1.0),
                'silent_failure_probability': (0.0, 1.0),
                'completeness_score': (0.0, 1.0),
                'confidence_level': (0.0, 1.0)
            },
            'string_patterns': {
                'event_id': r'^[a-zA-Z0-9\-_]{8,64}',
                'function_id': r'^[a-zA-Z0-9\-_.:]{1,128}',
            }
        }
    
    def validate_telemetry(self, telemetry: TelemetryRecord) -> Dict[str, Any]:
        """Comprehensive telemetry validation"""
        
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'quality_score': 1.0
        }
        
        # Check required fields
        self._validate_required_fields(telemetry, validation_result)
        
        # Check numeric ranges
        self._validate_numeric_ranges(telemetry, validation_result)
        
        # Check string patterns
        self._validate_string_patterns(telemetry, validation_result)
        
        # Check logical consistency
        self._validate_logical_consistency(telemetry, validation_result)
        
        # Check temporal consistency
        self._validate_temporal_consistency(telemetry, validation_result)
        
        # Calculate overall quality score
        validation_result['quality_score'] = self._calculate_quality_score(validation_result)
        
        # Update statistics
        self.validation_stats['total_validations'] += 1
        if validation_result['valid']:
            self.validation_stats['valid_records'] += 1
        else:
            self.validation_stats['invalid_records'] += 1
        
        return validation_result
    
    def _validate_required_fields(self, telemetry: TelemetryRecord, result: Dict):
        """Validate required fields are present and non-empty"""
        
        for field_name in self.validation_rules['required_fields']:
            if not hasattr(telemetry, field_name):
                result['errors'].append(f"Missing required field: {field_name}")
                result['valid'] = False
            else:
                value = getattr(telemetry, field_name)
                if value is None or (isinstance(value, str) and not value.strip()):
                    result['errors'].append(f"Empty required field: {field_name}")
                    result['valid'] = False
    
    def _validate_numeric_ranges(self, telemetry: TelemetryRecord, result: Dict):
        """Validate numeric fields are within expected ranges"""
        
        for field_name, (min_val, max_val) in self.validation_rules['numeric_ranges'].items():
            if hasattr(telemetry, field_name):
                value = getattr(telemetry, field_name)
                if value is not None and (value < min_val or value > max_val):
                    result['warnings'].append(f"{field_name} value {value} outside expected range [{min_val}, {max_val}]")
    
    def _validate_string_patterns(self, telemetry: TelemetryRecord, result: Dict):
        """Validate string fields match expected patterns"""
        
        import re
        for field_name, pattern in self.validation_rules['string_patterns'].items():
            if hasattr(telemetry, field_name):
                value = getattr(telemetry, field_name)
                if value and not re.match(pattern, str(value)):
                    result['warnings'].append(f"{field_name} value '{value}' doesn't match expected pattern")
    
    def _validate_logical_consistency(self, telemetry: TelemetryRecord, result: Dict):
        """Validate logical consistency between fields"""
        
        # Check that duration is reasonable for execution phase
        if telemetry.execution_phase == ExecutionPhase.INIT and telemetry.duration > 60.0:
            result['warnings'].append("Init phase duration seems unusually long")
        
        # Check that memory usage is reasonable
        if telemetry.memory_spike_kb > 1024 * 1024:  # > 1GB
            result['warnings'].append("Memory usage seems unusually high")
    
    def _validate_temporal_consistency(self, telemetry: TelemetryRecord, result: Dict):
        """Validate temporal consistency of timestamps"""
        
        current_time = time.time()
        if telemetry.timestamp > current_time:
            result['warnings'].append("Timestamp is in the future")
        elif current_time - telemetry.timestamp > 86400:  # > 24 hours
            result['warnings'].append("Timestamp is unusually old")
    
    def _calculate_quality_score(self, validation_result: Dict) -> float:
        """Calculate overall quality score based on validation results"""
        
        base_score = 1.0
        
        # Penalize errors heavily
        error_penalty = len(validation_result['errors']) * 0.3
        base_score -= error_penalty
        
        # Penalize warnings lightly
        warning_penalty = len(validation_result['warnings']) * 0.05
        base_score -= warning_penalty
        
        return max(0.0, base_score)


# =============================================================================
# Factory Functions for Backward Compatibility
# =============================================================================

def create_telemetry_record_with_telemetry_id(**kwargs) -> TelemetryRecord:
    """
    Factory function to create TelemetryRecord with telemetry_id parameter
    for backward compatibility with existing code.
    
    This function maps telemetry_id to event_id internally.
    """
    # Handle telemetry_id -> event_id mapping
    if 'telemetry_id' in kwargs and 'event_id' not in kwargs:
        kwargs['event_id'] = kwargs.pop('telemetry_id')
    
    # Ensure required fields have defaults if not provided
    if 'timestamp' not in kwargs:
        kwargs['timestamp'] = time.time()
    
    if 'concurrency_id' not in kwargs:
        kwargs['concurrency_id'] = str(uuid.uuid4())
    
    # Add missing required fields with sensible defaults
    if 'network_io_bytes' not in kwargs:
        kwargs['network_io_bytes'] = 0
    
    if 'fallback_mode' not in kwargs:
        kwargs['fallback_mode'] = False
    
    if 'source' not in kwargs:
        kwargs['source'] = TelemetrySource.PRIMARY
    
    # Create the record
    return TelemetryRecord(**kwargs)


# Alias for backward compatibility
create_telemetry_record = create_telemetry_record_with_telemetry_id
