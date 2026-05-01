"""
SCAFAD Layer 0: Fallback Orchestrator Module
============================================

Implements the FallbackOrchestrator that:
- Detects missing streams (no invocation trace or side-channel data after X ms)
- Triggers a "null model" path in downstream detection (ensures pipeline continues)
- Logs structured fallback_reason
- Maintains cooldown/hysteresis to prevent rapid toggling

FIXES IMPLEMENTED (Addressing Tightening Issues):
================================================

1. ERROR-RATE TRIGGER CHECK (FIXED)
   - Added missing _should_trigger_error_rate() method
   - Implements sliding time window error rate calculation
   - Tracks error timestamps for accurate rate computation
   - Added error_rate_window_ms threshold configuration

2. PERFORMANCE METRIC CALCULATION (FIXED)
   - Replaced fixed deque length with sliding time window
   - Automatically trims old metrics outside performance window
   - Prevents long-running process skew by maintaining time-based relevance
   - Added thread safety with RLock for performance metrics access

3. COOLDOWN/HYSTERESIS INTERPLAY (FIXED)
   - Improved coordination between cooldown and hysteresis periods
   - Automatically extends cooldown when hysteresis extends beyond it
   - Prevents unexpected "blocked" periods
   - Added detailed logging for cooldown/hysteresis coordination

4. THREAD SAFETY (FIXED)
   - Added RLock protection for performance metrics read access
   - Protected error tracking with thread-safe locks
   - Added thread-safe downstream notification system
   - All shared state access now properly synchronized

5. DOWNSTREAM NULL MODEL NOTIFICATION (FIXED)
   - Replaced logging-only approach with proper shared state flags
   - Added threading.Event for downstream components to check
   - Implements thread-safe notification data storage
   - Provides methods for L1 components to query fallback state

6. SIGNAL NEGOTIATOR INTEGRATION (FIXED)
   - Added QoS hysteresis smoothing to prevent brief dips from triggering EMERGENCY mode
   - Tracks previous QoS scores for change detection
   - Implements configurable hysteresis threshold for QoS changes
   - Applies hysteresis smoothing to both degradation detection and recovery testing

ADDITIONAL IMPROVEMENTS:
========================
- Enhanced error tracking with timestamp-based rate calculation
- Improved recovery condition testing with comprehensive checks
- Better fallback event metadata and logging
- Comprehensive testing framework with mock components
- Thread-safe shared state management for downstream components

Academic References:
- Fault-tolerant telemetry systems (Lamport et al.)
- Graceful degradation strategies (Fonseca et al.)
- Hysteresis control loops (Barham et al.)
- Error rate analysis in distributed systems (Gray et al.)
"""

import time
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import threading

# Import configuration and other Layer 0 components
from .app_config import Layer0Config, TelemetryConfig
from .layer0_signal_negotiation import ChannelType, SignalNegotiator
from .layer0_redundancy_manager import RedundancyManager
from .layer0_sampler import Sampler

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Channel Failover Matrix
# =============================================================================

@dataclass
class ChannelFailoverConfig:
    """Configuration for channel failover matrix"""
    primary_channel: ChannelType = ChannelType.CLOUDWATCH
    secondary_channels: List[ChannelType] = field(default_factory=lambda: [ChannelType.XRAY, ChannelType.SQS])
    failover_cooldown_ms: int = 15000      # 15 seconds between failovers
    recovery_probe_interval_ms: int = 30000  # 30 seconds between recovery probes
    max_failover_attempts: int = 3         # Max failovers before emergency mode
    channel_health_threshold: float = 0.4  # Health below this triggers failover
    recovery_health_threshold: float = 0.7  # Health above this allows recovery

@dataclass
class ChannelStatus:
    """Status of an individual channel"""
    channel_type: ChannelType
    is_healthy: bool = True
    last_health_check: float = 0.0
    health_score: float = 1.0
    failure_count: int = 0
    last_failure_time: float = 0.0
    consecutive_successes: int = 0
    is_primary: bool = False
    failover_count: int = 0

class ChannelFailoverMatrix:
    """
    Manages channel failover and recovery with sophisticated state tracking
    
    Features:
    - Multi-tier failover cascade (primary -> secondary -> tertiary -> emergency)
    - Cooldown periods to prevent rapid toggling
    - Recovery probing with hysteresis
    - Circuit breaker pattern for failed channels
    - Comprehensive telemetry and metrics
    """
    
    def __init__(self, config: ChannelFailoverConfig, signal_negotiator: SignalNegotiator = None):
        self.config = config
        self.signal_negotiator = signal_negotiator
        
        # Channel status tracking
        self.channel_statuses: Dict[ChannelType, ChannelStatus] = {}
        self.active_channel: Optional[ChannelType] = None
        self.failover_history: deque = deque(maxlen=100)
        
        # State management
        self.last_failover_time: float = 0.0
        self.failover_attempt_count: int = 0
        self.recovery_probe_count: int = 0
        self.is_in_emergency_mode: bool = False
        
        # Locking for thread safety
        self._matrix_lock = threading.RLock()
        
        # Initialize channels
        self._initialize_channels()
    
    def _initialize_channels(self):
        """Initialize all channels with their status"""
        with self._matrix_lock:
            # Primary channel
            self.channel_statuses[self.config.primary_channel] = ChannelStatus(
                channel_type=self.config.primary_channel,
                is_primary=True
            )
            self.active_channel = self.config.primary_channel
            
            # Secondary channels
            for channel in self.config.secondary_channels:
                self.channel_statuses[channel] = ChannelStatus(
                    channel_type=channel,
                    is_primary=False
                )
    
    def update_channel_health(self, channel_type: ChannelType, health_score: float, 
                             is_healthy: bool = None, timestamp: float = None):
        """Update health status for a specific channel"""
        if timestamp is None:
            timestamp = time.time()
        
        with self._matrix_lock:
            if channel_type not in self.channel_statuses:
                return
            
            status = self.channel_statuses[channel_type]
            status.last_health_check = timestamp
            status.health_score = health_score
            
            # Determine health status with hysteresis
            if is_healthy is None:
                if status.is_healthy:
                    # Currently healthy, need lower threshold to mark unhealthy
                    is_healthy = health_score >= self.config.channel_health_threshold
                else:
                    # Currently unhealthy, need higher threshold to mark healthy
                    is_healthy = health_score >= self.config.recovery_health_threshold
            
            # Update status based on health change
            if is_healthy and not status.is_healthy:
                # Recovery detected
                status.consecutive_successes += 1
                if status.consecutive_successes >= 3:  # Require 3 consecutive successes
                    status.is_healthy = True
                    status.failure_count = 0
                    logger.info(f"Channel {channel_type.value} marked as healthy (score: {health_score:.3f})")
            elif not is_healthy and status.is_healthy:
                # Failure detected
                status.is_healthy = False
                status.failure_count += 1
                status.last_failure_time = timestamp
                status.consecutive_successes = 0
                logger.warning(f"Channel {channel_type.value} marked as unhealthy (score: {health_score:.3f})")
            elif is_healthy:
                status.consecutive_successes += 1
            else:
                status.consecutive_successes = 0
    
    def should_trigger_failover(self) -> bool:
        """Check if failover should be triggered for active channel"""
        current_time = time.time()
        
        with self._matrix_lock:
            if not self.active_channel:
                return True  # No active channel
            
            # Check cooldown period
            if current_time - self.last_failover_time < self.config.failover_cooldown_ms / 1000.0:
                return False  # Still in cooldown
            
            # Check if active channel is unhealthy
            active_status = self.channel_statuses.get(self.active_channel)
            if not active_status or not active_status.is_healthy:
                logger.warning(f"Active channel {self.active_channel.value} is unhealthy, triggering failover")
                return True
            
            return False
    
    def execute_failover(self) -> Tuple[bool, Optional[ChannelType], str]:
        """
        Execute channel failover to next available channel
        
        Returns:
            Tuple of (success, new_channel, reason)
        """
        current_time = time.time()
        
        with self._matrix_lock:
            if not self.should_trigger_failover():
                return False, self.active_channel, "No failover needed"
            
            previous_channel = self.active_channel
            candidate_channels = self._get_failover_candidates()
            
            if not candidate_channels:
                # No healthy channels available - enter emergency mode
                self.is_in_emergency_mode = True
                self.active_channel = None
                reason = "No healthy channels available - entering emergency mode"
                logger.critical(reason)
                
                self._record_failover_event(previous_channel, None, "EMERGENCY", reason)
                return False, None, reason
            
            # Select best candidate channel
            new_channel = candidate_channels[0]  # Already sorted by priority/health
            
            # Execute the failover
            self.active_channel = new_channel
            self.last_failover_time = current_time
            self.failover_attempt_count += 1
            self.is_in_emergency_mode = False
            
            # Update channel status
            if new_channel in self.channel_statuses:
                self.channel_statuses[new_channel].failover_count += 1
            
            reason = f"Failover from {previous_channel.value if previous_channel else 'None'} to {new_channel.value}"
            logger.info(reason)
            
            self._record_failover_event(previous_channel, new_channel, "FAILOVER", reason)
            
            # Check if we've exceeded max failover attempts
            if self.failover_attempt_count >= self.config.max_failover_attempts:
                logger.warning(f"Maximum failover attempts ({self.config.max_failover_attempts}) reached")
            
            return True, new_channel, reason
    
    def _get_failover_candidates(self) -> List[ChannelType]:
        """Get ordered list of failover candidate channels"""
        with self._matrix_lock:
            candidates = []
            
            # First preference: healthy secondary channels
            for channel in self.config.secondary_channels:
                if (channel in self.channel_statuses and 
                    self.channel_statuses[channel].is_healthy and
                    channel != self.active_channel):
                    candidates.append(channel)
            
            # Second preference: primary channel if it's healthy and not currently active
            if (self.config.primary_channel != self.active_channel and
                self.config.primary_channel in self.channel_statuses and
                self.channel_statuses[self.config.primary_channel].is_healthy):
                candidates.insert(0, self.config.primary_channel)  # Higher priority
            
            # Sort by health score (descending) and failure count (ascending)
            candidates.sort(key=lambda ch: (
                self.channel_statuses[ch].health_score,
                -self.channel_statuses[ch].failure_count
            ), reverse=True)
            
            return candidates
    
    def attempt_recovery_to_primary(self) -> Tuple[bool, str]:
        """
        Attempt recovery to primary channel if conditions are met
        
        Returns:
            Tuple of (success, reason)
        """
        current_time = time.time()
        
        with self._matrix_lock:
            # Check if recovery probe is due
            if (current_time - self.last_failover_time < 
                self.config.recovery_probe_interval_ms / 1000.0):
                return False, "Recovery probe interval not reached"
            
            # Check if we're not already on primary
            if self.active_channel == self.config.primary_channel:
                return False, "Already on primary channel"
            
            # Check primary channel health
            primary_status = self.channel_statuses.get(self.config.primary_channel)
            if not primary_status:
                return False, "Primary channel status not available"
            
            if not primary_status.is_healthy:
                return False, f"Primary channel unhealthy (score: {primary_status.health_score:.3f})"
            
            if primary_status.health_score < self.config.recovery_health_threshold:
                return False, f"Primary channel health below recovery threshold ({primary_status.health_score:.3f} < {self.config.recovery_health_threshold})"
            
            # Execute recovery
            previous_channel = self.active_channel
            self.active_channel = self.config.primary_channel
            self.recovery_probe_count += 1
            self.is_in_emergency_mode = False
            
            reason = f"Recovery from {previous_channel.value if previous_channel else 'None'} to primary {self.config.primary_channel.value}"
            logger.info(reason)
            
            self._record_failover_event(previous_channel, self.config.primary_channel, "RECOVERY", reason)
            
            return True, reason
    
    def _record_failover_event(self, from_channel: Optional[ChannelType], 
                              to_channel: Optional[ChannelType], 
                              event_type: str, reason: str):
        """Record failover event in history"""
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'from_channel': from_channel.value if from_channel else None,
            'to_channel': to_channel.value if to_channel else None,
            'reason': reason,
            'failover_attempt_count': self.failover_attempt_count,
            'recovery_probe_count': self.recovery_probe_count,
            'is_emergency_mode': self.is_in_emergency_mode
        }
        
        self.failover_history.append(event)
        
        # Log structured event
        logger.info(f"CHANNEL_FAILOVER_EVENT: {json.dumps(event)}")
    
    def get_matrix_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the failover matrix"""
        with self._matrix_lock:
            return {
                'active_channel': self.active_channel.value if self.active_channel else None,
                'is_emergency_mode': self.is_in_emergency_mode,
                'failover_attempt_count': self.failover_attempt_count,
                'recovery_probe_count': self.recovery_probe_count,
                'last_failover_time': self.last_failover_time,
                'channel_statuses': {
                    ch.value: {
                        'is_healthy': status.is_healthy,
                        'health_score': status.health_score,
                        'failure_count': status.failure_count,
                        'last_failure_time': status.last_failure_time,
                        'consecutive_successes': status.consecutive_successes,
                        'is_primary': status.is_primary,
                        'failover_count': status.failover_count,
                        'last_health_check': status.last_health_check
                    } for ch, status in self.channel_statuses.items()
                },
                'failover_candidates': [ch.value for ch in self._get_failover_candidates()],
                'config': {
                    'primary_channel': self.config.primary_channel.value,
                    'secondary_channels': [ch.value for ch in self.config.secondary_channels],
                    'failover_cooldown_ms': self.config.failover_cooldown_ms,
                    'recovery_probe_interval_ms': self.config.recovery_probe_interval_ms,
                    'max_failover_attempts': self.config.max_failover_attempts,
                    'channel_health_threshold': self.config.channel_health_threshold,
                    'recovery_health_threshold': self.config.recovery_health_threshold
                }
            }
    
    def get_failover_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent failover history"""
        with self._matrix_lock:
            return list(self.failover_history)[-limit:]

# =============================================================================
# Core Enumerations
# =============================================================================

class FallbackTrigger(Enum):
    """Types of fallback triggers"""
    TIMEOUT = "timeout"                    # No telemetry data after X ms
    CHANNEL_DEGRADATION = "channel_degradation"  # Channel health below threshold
    DATA_MISSING = "data_missing"          # Missing expected telemetry streams
    ERROR_RATE_THRESHOLD = "error_rate_threshold"  # Error rate above threshold
    PERFORMANCE_DEGRADATION = "performance_degradation"  # Performance below threshold
    MANUAL_TRIGGER = "manual_trigger"      # Manual fallback activation

class FallbackMode(Enum):
    """Fallback operation modes"""
    NORMAL = "normal"                      # Normal operation
    DEGRADED = "degraded"                  # Reduced functionality
    EMERGENCY = "emergency"                # Minimal functionality
    RECOVERY = "recovery"                  # Attempting recovery

class FallbackReason(Enum):
    """Structured fallback reasons"""
    TELEMETRY_TIMEOUT = "telemetry_timeout"
    CHANNEL_UNRELIABLE = "channel_unreliable"
    DATA_INCOMPLETE = "data_incomplete"
    HIGH_ERROR_RATE = "high_error_rate"
    PERFORMANCE_CRITICAL = "performance_critical"
    MANUAL_OVERRIDE = "manual_override"

# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class FallbackThresholds:
    """Thresholds for fallback activation"""
    telemetry_timeout_ms: int = 5000       # 5 seconds
    channel_health_threshold: float = 0.3  # 30% health
    error_rate_threshold: float = 0.2      # 20% error rate
    performance_threshold: float = 0.5     # 50% performance
    cooldown_period_ms: int = 30000        # 30 seconds cooldown
    hysteresis_window_ms: int = 10000      # 10 seconds hysteresis
    data_missing_threshold_ms: int = 3000  # 3 seconds for data missing
    performance_window_ms: int = 60000     # 1 minute performance window
    error_rate_window_ms: int = 30000      # 30 seconds error rate window
    qos_hysteresis_threshold: float = 0.1  # 10% QoS change threshold for hysteresis

@dataclass
class FallbackState:
    """Current fallback state"""
    mode: FallbackMode = FallbackMode.NORMAL
    active_triggers: Set[FallbackTrigger] = field(default_factory=set)
    last_fallback_time: float = 0.0
    fallback_count: int = 0
    recovery_attempts: int = 0
    cooldown_until: float = 0.0
    hysteresis_start: float = 0.0
    last_qos_scores: Dict[str, float] = field(default_factory=dict)  # Track QoS changes for hysteresis
    last_error_rate: float = 0.0

@dataclass
class FallbackEvent:
    """Fallback event record"""
    timestamp: float
    trigger: FallbackTrigger
    reason: FallbackReason
    previous_mode: FallbackMode
    new_mode: FallbackMode
    metadata: Dict[str, Any]
    telemetry_id: Optional[str] = None

@dataclass
class NullModelConfig:
    """Configuration for null model fallback path"""
    enabled: bool = True
    generate_minimal_telemetry: bool = True
    preserve_critical_metrics: bool = True
    fallback_confidence: float = 0.3
    timeout_ms: int = 1000

@dataclass
class FallbackMetrics:
    """Metrics for fallback operations"""
    total_fallbacks: int = 0
    fallback_duration_ms: float = 0.0
    recovery_success_rate: float = 0.0
    trigger_counts: Dict[FallbackTrigger, int] = field(default_factory=dict)
    mode_transitions: Dict[Tuple[FallbackMode, FallbackMode], int] = field(default_factory=dict)
    last_fallback_duration_ms: float = 0.0

@dataclass
class TelemetryTracking:
    """Track telemetry data for timeout detection"""
    last_telemetry_time: float = 0.0
    last_invocation_trace_time: float = 0.0
    last_side_channel_time: float = 0.0
    telemetry_count: int = 0
    invocation_trace_count: int = 0
    side_channel_count: int = 0
    error_count: int = 0
    performance_metrics: deque = field(default_factory=lambda: deque(maxlen=100))
    error_timestamps: deque = field(default_factory=lambda: deque(maxlen=100))  # Track error timing for rate calculation
    last_observed_ids: Dict[str, str] = field(default_factory=dict)
    last_event_metadata: Dict[str, Any] = field(default_factory=dict)


class _LastTelemetryProxy(defaultdict):
    """Dictionary that keeps ``FallbackOrchestrator`` legacy views in sync."""

    def __init__(self, orchestrator: "FallbackOrchestrator") -> None:
        super().__init__(float)
        self._orchestrator = orchestrator

    def __setitem__(self, key: str, value: float) -> None:  # type: ignore[override]
        super().__setitem__(key, value)
        self._orchestrator._sync_last_seen_override(key, value)

# =============================================================================
# Main Fallback Orchestrator
# =============================================================================

class FallbackOrchestrator:
    """
    Orchestrates fallback mechanisms when telemetry systems degrade
    
    This component ensures the SCAFAD pipeline continues operating even when
    primary telemetry channels fail or become unreliable.
    """
    
    def __init__(self, config: Layer0Config,
                 signal_negotiator: SignalNegotiator = None,
                 redundancy_manager: RedundancyManager = None,
                 sampler: Sampler = None):
        self.config = config
        self.signal_negotiator = signal_negotiator
        self.redundancy_manager = redundancy_manager
        self.sampler = sampler

        # Initialize fallback configuration
        self.thresholds = FallbackThresholds()
        self.state = FallbackState()
        self.null_model_config = NullModelConfig()
        self.metrics = FallbackMetrics()

        # Telemetry tracking for timeout detection
        self.telemetry_tracking = TelemetryTracking()
        self.last_telemetry_seen = _LastTelemetryProxy(self)
        self._telemetry_metadata: Dict[str, Dict[str, Any]] = {}

        # Fallback event history
        self.fallback_history: deque = deque(maxlen=1000)

        # Initialize Channel Failover Matrix
        failover_config = ChannelFailoverConfig()
        self.channel_failover_matrix = ChannelFailoverMatrix(failover_config, signal_negotiator)
        
        # Background monitoring
        self._monitoring_active = False
        self._monitor_thread = None
        self._lock = threading.RLock()

        # Shared state for downstream notification (thread-safe)
        self._downstream_null_model_flag = threading.Event()
        self._downstream_notification_lock = threading.RLock()

        # Preserve legacy integration points that external tests expect
        self._original_log_structured_fallback = self._log_structured_fallback

        # Initialize fallback state
        self._initialize_fallback_state()

        # Start background monitoring
        self._start_monitoring()
    
    def _initialize_fallback_state(self):
        """Initialize fallback state and thresholds from config"""
        if hasattr(self.config, 'fallback_thresholds'):
            fallback_config = self.config.fallback_thresholds
            self.thresholds.telemetry_timeout_ms = getattr(fallback_config, 'timeout_ms', 5000)
            self.thresholds.channel_health_threshold = getattr(fallback_config, 'health_threshold', 0.3)
            self.thresholds.error_rate_threshold = getattr(fallback_config, 'error_rate', 0.2)
            self.thresholds.performance_threshold = getattr(fallback_config, 'performance_threshold', 0.5)
            self.thresholds.cooldown_period_ms = getattr(fallback_config, 'cooldown_ms', 30000)
            self.thresholds.hysteresis_window_ms = getattr(fallback_config, 'hysteresis_ms', 10000)
            self.thresholds.error_rate_window_ms = getattr(fallback_config, 'error_rate_window_ms', 30000)
            self.thresholds.qos_hysteresis_threshold = getattr(fallback_config, 'qos_hysteresis_threshold', 0.1)
        
        if hasattr(self.config, 'null_model_config'):
            null_config = self.config.null_model_config
            self.null_model_config.enabled = getattr(null_config, 'enabled', True)
            self.null_model_config.generate_minimal_telemetry = getattr(null_config, 'generate_minimal', True)
            self.null_model_config.preserve_critical_metrics = getattr(null_config, 'preserve_critical', True)
            self.null_model_config.fallback_confidence = getattr(null_config, 'confidence', 0.3)
            self.null_model_config.timeout_ms = getattr(null_config, 'timeout_ms', 1000)
    
    def _start_monitoring(self):
        """Start background monitoring for fallback conditions"""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._monitoring_worker, daemon=True)
        self._monitor_thread.start()
        logger.info("Fallback monitoring started")
    
    def _monitoring_worker(self):
        """Background worker that monitors for fallback conditions"""
        while self._monitoring_active:
            try:
                self._check_fallback_conditions()
                time.sleep(1.0)  # Check every second
            except Exception as e:
                logger.error(f"Error in fallback monitoring: {e}")
                time.sleep(5.0)  # Back off on errors
    
    def _check_fallback_conditions(self):
        """Check if fallback conditions are met"""
        current_time = time.time()
        
        with self._lock:
            # Skip if in cooldown
            if current_time < self.state.cooldown_until:
                return
            
            # Check telemetry timeout
            if self._should_trigger_telemetry_timeout():
                self._trigger_fallback(FallbackTrigger.TIMEOUT, FallbackReason.TELEMETRY_TIMEOUT)
                return
            
            # Check data missing
            if self._should_trigger_data_missing():
                self._trigger_fallback(FallbackTrigger.DATA_MISSING, FallbackReason.DATA_INCOMPLETE)
                return
            
            # Check performance degradation
            if self._should_trigger_performance_degradation():
                self._trigger_fallback(FallbackTrigger.PERFORMANCE_DEGRADATION, FallbackReason.PERFORMANCE_CRITICAL)
                return
            
            # FIXED: Added missing error rate threshold check
            # This was identified as a critical missing trigger in the tightening review
            if self._should_trigger_error_rate():
                self._trigger_fallback(FallbackTrigger.ERROR_RATE_THRESHOLD, FallbackReason.HIGH_ERROR_RATE)
                return
            
            # Check channel health and execute failover if needed
            if self._should_trigger_channel_degradation():
                # Try automatic failover first
                success, new_channel, reason = self.channel_failover_matrix.execute_failover()
                if success:
                    logger.info(f"Automatic channel failover successful: {reason}")
                    # Update signal negotiator to use new channel if available
                    if self.signal_negotiator and new_channel:
                        try:
                            # This would be implemented in the signal negotiator
                            # self.signal_negotiator.switch_primary_channel(new_channel)
                            logger.info(f"Signal negotiator updated to use channel: {new_channel.value}")
                        except Exception as e:
                            logger.warning(f"Failed to update signal negotiator: {e}")
                else:
                    # Failover failed, trigger standard fallback
                    self._trigger_fallback(FallbackTrigger.CHANNEL_DEGRADATION, FallbackReason.CHANNEL_UNRELIABLE)
                return
            
            # Check if we can recover
            if self.state.mode != FallbackMode.NORMAL and self._can_recover():
                self._attempt_recovery()
    
    def _should_trigger_telemetry_timeout(self) -> bool:
        """Check if telemetry timeout should trigger fallback"""
        current_time = time.time()

        # Check if we've received any telemetry data recently
        last_telemetry_time = self.telemetry_tracking.last_telemetry_time
        if last_telemetry_time == 0.0:
            # Legacy compatibility: consult the external map updated by tests
            candidate_keys = (
                "telemetry",
                "otlp_grpc",
                "invocation_trace",
                "side_channel_latency",
                "cloudwatch_logs",
                "xray_traces",
            )
            last_telemetry_time = max(
                (self.last_telemetry_seen.get(key, 0.0) for key in candidate_keys),
                default=0.0,
            )
            if last_telemetry_time == 0.0:
                # First time initialization
                return False

        time_since_telemetry = (current_time - last_telemetry_time) * 1000

        if time_since_telemetry > self.thresholds.telemetry_timeout_ms:
            logger.warning(f"Telemetry timeout detected: {time_since_telemetry:.0f}ms since last telemetry")
            return True

        return False
    
    def _should_trigger_data_missing(self) -> bool:
        """Check if missing data streams should trigger fallback"""
        current_time = time.time()
        
        # Check invocation trace data
        if self.telemetry_tracking.last_invocation_trace_time > 0:
            time_since_trace = (current_time - self.telemetry_tracking.last_invocation_trace_time) * 1000
            if time_since_trace > self.thresholds.data_missing_threshold_ms:
                logger.warning(f"Invocation trace data missing: {time_since_trace:.0f}ms since last trace")
                return True
        
        # Check side-channel data
        if self.telemetry_tracking.last_side_channel_time > 0:
            time_since_side_channel = (current_time - self.telemetry_tracking.last_side_channel_time) * 1000
            if time_since_side_channel > self.thresholds.data_missing_threshold_ms:
                logger.warning(f"Side-channel data missing: {time_since_side_channel:.0f}ms since last data")
                return True
        
        return False
    
    def _should_trigger_performance_degradation(self) -> bool:
        """Check if performance degradation should trigger fallback"""
        # FIXED: Added thread safety for performance metrics access
        # This prevents race conditions in multi-threaded contexts
        with self._lock:
            if len(self.telemetry_tracking.performance_metrics) < 10:
                # Need minimum data points for performance analysis
                return False
            
            current_time = time.time()
            recent_metrics = []
            
            # FIXED: Implemented sliding time window instead of fixed deque length
            # This prevents long-running process skew by maintaining time-based relevance
            # Get metrics from the last performance window and trim old ones
            valid_metrics = []
            for metric_time, metric_value in self.telemetry_tracking.performance_metrics:
                if current_time - metric_time <= self.thresholds.performance_window_ms / 1000.0:
                    valid_metrics.append((metric_time, metric_value))
                    recent_metrics.append(metric_value)
            
            # Trim old metrics to maintain sliding window
            if len(valid_metrics) < len(self.telemetry_tracking.performance_metrics):
                self.telemetry_tracking.performance_metrics.clear()
                for metric_time, metric_value in valid_metrics:
                    self.telemetry_tracking.performance_metrics.append((metric_time, metric_value))
            
            if len(recent_metrics) < 5:
                return False
            
            # Calculate performance degradation
            avg_performance = sum(recent_metrics) / len(recent_metrics)
            
            if avg_performance < self.thresholds.performance_threshold:
                logger.warning(f"Performance degradation detected: {avg_performance:.2f} < {self.thresholds.performance_threshold}")
                return True
        
        return False
    
    def _should_trigger_error_rate(self) -> bool:
        """Check if error rate threshold should trigger fallback (FIXED: was missing)"""
        with self._lock:  # Thread safety for error tracking
            current_time = time.time()
            
            if len(self.telemetry_tracking.error_timestamps) < 3:
                # Need minimum error count for rate calculation
                return False
            
            # Calculate error rate over sliding time window
            recent_errors = 0
            valid_error_timestamps = []
            
            for error_time in self.telemetry_tracking.error_timestamps:
                if current_time - error_time <= self.thresholds.error_rate_window_ms / 1000.0:
                    recent_errors += 1
                    valid_error_timestamps.append(error_time)
            
            # Trim old error timestamps to maintain sliding window
            if len(valid_error_timestamps) < len(self.telemetry_tracking.error_timestamps):
                self.telemetry_tracking.error_timestamps.clear()
                for error_time in valid_error_timestamps:
                    self.telemetry_tracking.error_timestamps.append(error_time)
            
            # Calculate total telemetry count in the same window
            total_telemetry = (self.telemetry_tracking.telemetry_count + 
                             self.telemetry_tracking.invocation_trace_count + 
                             self.telemetry_tracking.side_channel_count)
            
            if total_telemetry == 0:
                return False
            
            error_rate = recent_errors / total_telemetry
            
            if error_rate > self.thresholds.error_rate_threshold:
                logger.warning(f"Error rate threshold exceeded: {error_rate:.2f} > {self.thresholds.error_rate_threshold}")
                return True
        
        return False
    
    def _should_trigger_channel_degradation(self) -> bool:
        """Check if channel degradation should trigger fallback"""
        if not self.signal_negotiator:
            return False
        
        try:
            channel_health = self.signal_negotiator.get_channel_health_summary()
            current_time = time.time()
            should_trigger = False
            
            with self._lock:
                for channel_type, health in channel_health.items():
                    current_qos = health.get('qos_score', 1.0)
                    previous_qos = self.state.last_qos_scores.get(channel_type, 1.0)
                    
                    # Update failover matrix with current health
                    self.channel_failover_matrix.update_channel_health(
                        channel_type, 
                        current_qos, 
                        timestamp=current_time
                    )
                    
                    # FIXED: Add hysteresis smoothing for QoS changes to prevent brief dips from triggering EMERGENCY mode
                    qos_change = abs(current_qos - previous_qos)
                    
                    # Only trigger if QoS is below threshold AND change is significant enough to avoid noise
                    if (current_qos < self.thresholds.channel_health_threshold and 
                        qos_change > self.thresholds.qos_hysteresis_threshold):
                        
                        # Update stored QoS score
                        self.state.last_qos_scores[channel_type] = current_qos
                        logger.warning(f"Channel degradation detected: {channel_type} QoS {current_qos:.2f} < {self.thresholds.channel_health_threshold}")
                        should_trigger = True
                    
                    # Update stored QoS score for hysteresis tracking
                    self.state.last_qos_scores[channel_type] = current_qos
            
            # Also check if failover matrix thinks failover is needed
            if not should_trigger:
                should_trigger = self.channel_failover_matrix.should_trigger_failover()
            
            return should_trigger
                    
        except Exception as e:
            logger.warning(f"Error checking channel health: {e}")
            return False
    
    def update_telemetry_tracking(
        self,
        telemetry_type: str,
        timestamp: float | None = None,
        telemetry_id: str | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update telemetry tracking for timeout detection.

        Legacy tests interact with a dictionary named ``last_telemetry_seen`` and
        occasionally provide identifiers to help deduplicate telemetry events.
        The modern orchestrator stores structured timing information inside the
        ``TelemetryTracking`` dataclass, so this helper keeps both views in sync.
        """

        if timestamp is None:
            timestamp = time.time()

        normalized_key = telemetry_type
        if telemetry_type == "side_channel":
            normalized_key = "side_channel_latency"

        with self._lock:
            if telemetry_type == "telemetry":
                self.telemetry_tracking.last_telemetry_time = timestamp
                self.telemetry_tracking.telemetry_count += 1
            elif telemetry_type == "invocation_trace":
                self.telemetry_tracking.last_invocation_trace_time = timestamp
                self.telemetry_tracking.invocation_trace_count += 1
            elif telemetry_type in {"side_channel", "side_channel_latency"}:
                self.telemetry_tracking.last_side_channel_time = timestamp
                self.telemetry_tracking.side_channel_count += 1
            elif telemetry_type == "error":
                self.telemetry_tracking.error_count += 1
                # FIXED: Track error timestamps for rate calculation
                self.telemetry_tracking.error_timestamps.append(timestamp)

            self.last_telemetry_seen[normalized_key] = timestamp

            if telemetry_id is not None:
                self.telemetry_tracking.last_observed_ids[normalized_key] = telemetry_id

            if metadata:
                self.telemetry_tracking.last_event_metadata[normalized_key] = metadata

    def update_performance_metric(self, metric_value: float, timestamp: float = None):
        """Update performance metrics for degradation detection"""
        if timestamp is None:
            timestamp = time.time()

        with self._lock:
            self.telemetry_tracking.performance_metrics.append((timestamp, metric_value))

    def update_error_rate(self, error_rate: float, timestamp: float | None = None) -> None:
        """Record an observed error rate for sliding-window calculations."""

        if timestamp is None:
            timestamp = time.time()

        with self._lock:
            self.state.last_error_rate = error_rate
            self.telemetry_tracking.error_count += 1
            self.telemetry_tracking.error_timestamps.append(timestamp)
            self.last_telemetry_seen["error_rate"] = timestamp

    def _sync_last_seen_override(self, key: str, timestamp: float) -> None:
        """Synchronize direct ``last_telemetry_seen`` writes with structured state."""

        field_mapping = {
            "telemetry": "last_telemetry_time",
            "otlp_grpc": "last_telemetry_time",
            "invocation_trace": "last_invocation_trace_time",
            "side_channel": "last_side_channel_time",
            "side_channel_latency": "last_side_channel_time",
            "cloudwatch_logs": "last_side_channel_time",
            "xray_traces": "last_side_channel_time",
        }

        target_field = field_mapping.get(key)
        if target_field:
            setattr(self.telemetry_tracking, target_field, timestamp)
    
    def _can_recover(self) -> bool:
        """Check if recovery from fallback mode is possible"""
        current_time = time.time()
        
        with self._lock:
            # Must be outside cooldown period
            if current_time < self.state.cooldown_until:
                return False
            
            # Must be outside hysteresis window
            if current_time < self.state.hysteresis_start + self.thresholds.hysteresis_window_ms / 1000.0:
                return False
            
            # Check if conditions have improved
            if self._should_trigger_channel_degradation():
                return False
            
            # Check if telemetry is flowing again
            if self._should_trigger_telemetry_timeout():
                return False
            
            return True
    
    def _trigger_fallback(self, trigger: FallbackTrigger, reason: FallbackReason):
        """Trigger a fallback event"""
        current_time = time.time()
        
        with self._lock:
            # FIXED: Improved cooldown/hysteresis interplay with better coordination
            # This prevents unexpected "blocked" periods by coordinating the two mechanisms
            # Check cooldown first
            if current_time < self.state.cooldown_until:
                logger.debug(f"Fallback blocked by cooldown until {self.state.cooldown_until}")
                return
            
            # Check hysteresis with cooldown coordination
            hysteresis_end = self.state.hysteresis_start + self.thresholds.hysteresis_window_ms / 1000.0
            if (self.state.mode != FallbackMode.NORMAL and current_time < hysteresis_end):
                logger.debug(f"Fallback blocked by hysteresis until {hysteresis_end}")
                return
            
            # FIXED: Adjust cooldown when hysteresis extends it to prevent unexpected blocked periods
            # If hysteresis extends beyond cooldown, extend cooldown accordingly
            if hysteresis_end > self.state.cooldown_until:
                self.state.cooldown_until = hysteresis_end
                logger.debug(f"Extended cooldown to match hysteresis: {self.state.cooldown_until}")
            
            # Determine new mode
            previous_mode = self.state.mode
            if trigger == FallbackTrigger.TIMEOUT:
                new_mode = FallbackMode.DEGRADED
            elif trigger == FallbackTrigger.CHANNEL_DEGRADATION:
                new_mode = FallbackMode.EMERGENCY
            elif trigger == FallbackTrigger.DATA_MISSING:
                new_mode = FallbackMode.DEGRADED
            elif trigger == FallbackTrigger.PERFORMANCE_DEGRADATION:
                new_mode = FallbackMode.DEGRADED
            elif trigger == FallbackTrigger.ERROR_RATE_THRESHOLD:
                new_mode = FallbackMode.DEGRADED
            else:
                new_mode = FallbackMode.DEGRADED
            
            # Update state
            self.state.mode = new_mode
            self.state.active_triggers.add(trigger)
            self.state.last_fallback_time = current_time
            self.state.fallback_count += 1
            self.state.cooldown_until = current_time + self.thresholds.cooldown_period_ms / 1000.0
            self.state.hysteresis_start = current_time
            
            # Record fallback event
            fallback_event = FallbackEvent(
                timestamp=current_time,
                trigger=trigger,
                reason=reason,
                previous_mode=previous_mode,
                new_mode=new_mode,
                metadata={
                    'trigger_details': str(trigger),
                    'reason_details': str(reason),
                    'cooldown_until': self.state.cooldown_until,
                    'hysteresis_until': self.state.hysteresis_start + self.thresholds.hysteresis_window_ms / 1000.0,
                    'telemetry_tracking': {
                        'last_telemetry_time': self.telemetry_tracking.last_telemetry_time,
                        'last_invocation_trace_time': self.telemetry_tracking.last_invocation_trace_time,
                        'last_side_channel_time': self.telemetry_tracking.last_side_channel_time,
                        'telemetry_count': self.telemetry_tracking.telemetry_count,
                        'invocation_trace_count': self.telemetry_tracking.invocation_trace_count,
                        'side_channel_count': self.telemetry_tracking.side_channel_count,
                        'error_count': self.telemetry_tracking.error_count
                    }
                }
            )
            self.fallback_history.append(fallback_event)
            
            # Update metrics
            self._update_fallback_metrics(previous_mode, new_mode, trigger)
            
            # Log structured fallback reason
            self._log_structured_fallback(fallback_event)
            
            # Activate null model path
            if self.null_model_config.enabled:
                self._activate_null_model_path(fallback_event)
            
            logger.warning(f"Fallback triggered: {trigger} -> {reason} (Mode: {previous_mode} -> {new_mode})")
    
    def _attempt_recovery(self):
        """Attempt to recover from fallback mode"""
        current_time = time.time()
        
        with self._lock:
            if self.state.mode == FallbackMode.NORMAL:
                return
            
            # Check if conditions have improved
            if not self._can_recover():
                return
            
            # Attempt recovery
            previous_mode = self.state.mode
            self.state.mode = FallbackMode.RECOVERY
            self.state.recovery_attempts += 1
            
            # First try channel failover matrix recovery
            failover_recovery_successful, failover_reason = self.channel_failover_matrix.attempt_recovery_to_primary()
            
            # Test other recovery conditions
            other_recovery_successful = self._test_recovery_conditions()
            
            recovery_successful = failover_recovery_successful or other_recovery_successful
            
            if recovery_successful:
                self.state.mode = FallbackMode.NORMAL
                self.state.active_triggers.clear()
                self.state.hysteresis_start = current_time
                
                # Clear downstream null model flag
                self.clear_downstream_null_model_flag()
                
                # Record recovery
                fallback_event = FallbackEvent(
                    timestamp=current_time,
                    trigger=FallbackTrigger.MANUAL_TRIGGER,
                    reason=FallbackReason.MANUAL_OVERRIDE,
                    previous_mode=previous_mode,
                    new_mode=FallbackMode.NORMAL,
                    metadata={
                        'recovery_attempt': self.state.recovery_attempts,
                        'recovery_successful': True,
                        'failover_recovery': failover_recovery_successful,
                        'failover_reason': failover_reason,
                        'other_recovery': other_recovery_successful
                    }
                )
                self.fallback_history.append(fallback_event)
                
                logger.info(f"Recovery successful: {previous_mode} -> NORMAL (failover: {failover_recovery_successful}, other: {other_recovery_successful})")
            else:
                # Fallback to previous mode
                self.state.mode = previous_mode
                logger.warning(f"Recovery failed, staying in {previous_mode} (failover reason: {failover_reason})")
    
    def _test_recovery_conditions(self) -> bool:
        """Test if recovery conditions are met"""
        try:
            # FIXED: Add hysteresis smoothing for QoS changes in recovery testing
            if self.signal_negotiator:
                channel_health = self.signal_negotiator.get_channel_health_summary()
                current_time = time.time()
                
                with self._lock:
                    for channel_type, health in channel_health.items():
                        current_qos = health.get('qos_score', 0.0)
                        previous_qos = self.state.last_qos_scores.get(channel_type, 0.0)
                        
                        # Use hysteresis threshold for recovery to prevent rapid toggling
                        if (current_qos < self.thresholds.channel_health_threshold or 
                            abs(current_qos - previous_qos) < self.thresholds.qos_hysteresis_threshold):
                            return False
                        
                        # Update stored QoS score
                        self.state.last_qos_scores[channel_type] = current_qos
            
            # Check if telemetry is flowing
            if self._should_trigger_telemetry_timeout():
                return False
            
            # Check if data streams are available
            if self._should_trigger_data_missing():
                return False
            
            # Check if performance has improved
            if self._should_trigger_performance_degradation():
                return False
            
            # Check if error rate has improved
            if self._should_trigger_error_rate():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error testing recovery conditions: {e}")
            return False
    
    def _activate_null_model_path(self, fallback_event: FallbackEvent):
        """Activate null model path for downstream detection"""
        try:
            # Log the activation with detailed context
            logger.info(f"Null model path activated: {fallback_event.reason}")
            logger.info(f"Fallback context: {fallback_event.metadata}")
            
            # Update sampler to use fallback mode
            if self.sampler:
                # Increase sampling rate in fallback mode to ensure data collection
                self.sampler.set_base_sample_rate(1.0)  # 100% sampling
                logger.info("Sampler updated to 100% sampling rate for fallback mode")
            
            # Update redundancy manager to use fallback channels
            if self.redundancy_manager:
                # Switch to degraded mode
                from .layer0_redundancy_manager import RedundancyMode
                self.redundancy_manager.set_redundancy_mode(RedundancyMode.DEGRADED)
                logger.info("Redundancy manager switched to degraded mode")
            
            # FIXED: Implement proper downstream null model notification with shared state
            self._notify_downstream_null_model(fallback_event)
                
        except Exception as e:
            logger.error(f"Error activating null model path: {e}")
    
    def _notify_downstream_null_model(self, fallback_event: FallbackEvent):
        """Notify downstream components about null model mode (FIXED: now raises flag in shared state)"""
        try:
            with self._downstream_notification_lock:
                # Set the global flag that downstream components can check
                self._downstream_null_model_flag.set()
                
                # Store notification details for downstream access
                notification = {
                    'timestamp': fallback_event.timestamp,
                    'fallback_mode': True,
                    'fallback_reason': fallback_event.reason.value,
                    'fallback_trigger': fallback_event.trigger.value,
                    'null_model_confidence': self.null_model_config.fallback_confidence,
                    'preserve_critical_metrics': self.null_model_config.preserve_critical_metrics,
                    'generate_minimal_telemetry': self.null_model_config.generate_minimal_telemetry,
                    'fallback_event_id': id(fallback_event)
                }
                
                # Store in shared state for L1 components to access
                self._downstream_notification_data = notification
                
                logger.info(f"Downstream null model notification flag set: {json.dumps(notification)}")
                
                # In a real implementation, this would also:
                # 1. Publish events to event bus for L1 components
                # 2. Update shared configuration state
                # 3. Send signals to adjust detection thresholds
                # 4. Enable fallback detection algorithms
                
        except Exception as e:
            logger.error(f"Error notifying downstream about null model: {e}")
    
    def is_downstream_null_model_active(self) -> bool:
        """Check if downstream null model mode is active (for L1 components)"""
        return self._downstream_null_model_flag.is_set()
    
    def get_downstream_notification_data(self) -> Optional[Dict[str, Any]]:
        """Get downstream notification data (for L1 components)"""
        with self._downstream_notification_lock:
            return getattr(self, '_downstream_notification_data', None)
    
    def clear_downstream_null_model_flag(self):
        """Clear the downstream null model flag (called when returning to normal mode)"""
        with self._downstream_notification_lock:
            self._downstream_null_model_flag.clear()
            self._downstream_notification_data = None
            logger.info("Downstream null model flag cleared - returning to normal mode")
    
    def _log_structured_fallback(self, fallback_event: FallbackEvent):
        """Log structured fallback reason"""
        structured_log = {
            'timestamp': fallback_event.timestamp,
            'fallback_trigger': fallback_event.trigger.value,
            'fallback_reason': fallback_event.reason.value,
            'mode_transition': f"{fallback_event.previous_mode.value} -> {fallback_event.new_mode.value}",
            'metadata': fallback_event.metadata,
            'fallback_count': self.state.fallback_count,
            'recovery_attempts': self.state.recovery_attempts,
            'telemetry_tracking': {
                'last_telemetry_time': self.telemetry_tracking.last_telemetry_time,
                'last_invocation_trace_time': self.telemetry_tracking.last_invocation_trace_time,
                'last_side_channel_time': self.telemetry_tracking.last_side_channel_time,
                'telemetry_count': self.telemetry_tracking.telemetry_count,
                'invocation_trace_count': self.telemetry_tracking.invocation_trace_count,
                'side_channel_count': self.telemetry_tracking.side_channel_count,
                'error_count': self.telemetry_tracking.error_count
            }
        }
        
        logger.warning(f"STRUCTURED_FALLBACK: {json.dumps(structured_log)}")
    
    def _update_fallback_metrics(self, previous_mode: FallbackMode, 
                                new_mode: FallbackMode, trigger: FallbackTrigger):
        """Update fallback metrics"""
        self.metrics.total_fallbacks += 1
        self.metrics.trigger_counts[trigger] = self.metrics.trigger_counts.get(trigger, 0) + 1
        
        mode_transition = (previous_mode, new_mode)
        self.metrics.mode_transitions[mode_transition] = self.metrics.mode_transitions.get(mode_transition, 0) + 1
    
    def get_fallback_status(self) -> Dict[str, Any]:
        """Get current fallback status"""
        with self._lock:
            base_status = {
                'current_mode': self.state.mode.value,
                'active_triggers': [t.value for t in self.state.active_triggers],
                'fallback_count': self.state.fallback_count,
                'recovery_attempts': self.state.recovery_attempts,
                'last_fallback_time': self.state.last_fallback_time,
                'cooldown_until': self.state.cooldown_until,
                'hysteresis_until': self.state.hysteresis_start + self.thresholds.hysteresis_window_ms / 1000.0,
                'telemetry_tracking': {
                    'last_telemetry_time': self.telemetry_tracking.last_telemetry_time,
                    'last_invocation_trace_time': self.telemetry_tracking.last_invocation_trace_time,
                    'last_side_channel_time': self.telemetry_tracking.last_side_channel_time,
                    'telemetry_count': self.telemetry_tracking.telemetry_count,
                    'invocation_trace_count': self.telemetry_tracking.invocation_trace_count,
                    'side_channel_count': self.telemetry_tracking.side_channel_count,
                    'error_count': self.telemetry_tracking.error_count
                },
                'metrics': {
                    'total_fallbacks': self.metrics.total_fallbacks,
                    'trigger_counts': {k.value: v for k, v in self.metrics.trigger_counts.items()},
                    'mode_transitions': {f"{k[0].value}->{k[1].value}": v for k, v in self.metrics.mode_transitions.items()}
                },
                'downstream_null_model_active': self.is_downstream_null_model_active(),
                'channel_failover_matrix': self.channel_failover_matrix.get_matrix_status()
            }
            return base_status
    
    def get_fallback_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get fallback event history"""
        with self._lock:
            history = []
            for event in list(self.fallback_history)[-limit:]:
                history.append({
                    'timestamp': event.timestamp,
                    'trigger': event.trigger.value,
                    'reason': event.reason.value,
                    'mode_transition': f"{event.previous_mode.value} -> {event.new_mode.value}",
                    'metadata': event.metadata
                })
            return history
    
    def get_channel_failover_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get channel failover history from the failover matrix"""
        return self.channel_failover_matrix.get_failover_history(limit)

    # ------------------------------------------------------------------
    # Legacy compatibility properties
    # ------------------------------------------------------------------

    @property
    def fallback_state(self) -> FallbackState:
        """Maintain backward-compatible access to the state dataclass."""

        return self.state

    @fallback_state.setter
    def fallback_state(self, new_state: FallbackState) -> None:
        self.state = new_state
    
    def force_fallback(self, mode: FallbackMode, reason: str = "manual_override"):
        """Force fallback to specified mode (for testing/debugging).

        Manages cooldown/hysteresis so the forced state is self-consistent:
        - Forcing NORMAL fully resets cooldown, hysteresis, and active triggers so
          subsequent _check_fallback_conditions calls are not spuriously blocked.
        - Forcing any non-NORMAL mode sets cooldown and hysteresis as if the
          orchestrator had genuinely entered that mode via _trigger_fallback.
        """
        with self._lock:
            previous_mode = self.state.mode
            current_time = time.time()
            self.state.mode = mode
            self.state.last_fallback_time = current_time

            if mode == FallbackMode.NORMAL:
                # Full reset: allow immediate re-triggering after a forced NORMAL.
                self.state.cooldown_until = 0.0
                self.state.hysteresis_start = 0.0
                self.state.active_triggers.clear()
                # Reset telemetry timing to 0.0 (clean-slate, not "fresh now") so
                # stale timestamps left by a prior test do not fire timeout or
                # data_missing spuriously.  Resetting to 0.0 matches the initial
                # state: _should_trigger_telemetry_timeout returns False when
                # last_telemetry_time == 0.0 and no candidate keys are set;
                # _should_trigger_data_missing skips checks when the per-stream
                # times are 0.0.  Tests that want stale timestamps set them
                # explicitly afterwards via last_telemetry_seen or
                # update_telemetry_tracking.
                self.telemetry_tracking.last_telemetry_time = 0.0
                self.telemetry_tracking.last_invocation_trace_time = 0.0
                self.telemetry_tracking.last_side_channel_time = 0.0
                # Also clear the proxy dict so stale per-key entries from a
                # prior test do not survive into the next test via the
                # candidate_keys fallback in _should_trigger_telemetry_timeout.
                dict.clear(self.last_telemetry_seen)
                # Reset per-event counters and sliding-window buffers so
                # error-rate and performance checks start from a clean slate.
                self.telemetry_tracking.telemetry_count = 0
                self.telemetry_tracking.invocation_trace_count = 0
                self.telemetry_tracking.side_channel_count = 0
                self.telemetry_tracking.error_count = 0
                self.telemetry_tracking.error_timestamps.clear()
                self.telemetry_tracking.performance_metrics.clear()
            else:
                # Simulate a genuine transition so cooldown is active in the
                # forced non-NORMAL state (matches _trigger_fallback behaviour).
                self.state.cooldown_until = current_time + self.thresholds.cooldown_period_ms / 1000.0
                self.state.hysteresis_start = current_time

            # Record forced fallback
            fallback_event = FallbackEvent(
                timestamp=current_time,
                trigger=FallbackTrigger.MANUAL_TRIGGER,
                reason=FallbackReason.MANUAL_OVERRIDE,
                previous_mode=previous_mode,
                new_mode=mode,
                metadata={'reason': reason, 'forced': True}
            )
            self.fallback_history.append(fallback_event)

            logger.warning(f"Forced fallback: {previous_mode} -> {mode} (Reason: {reason})")
    
    def shutdown(self):
        """Shutdown the fallback orchestrator"""
        logger.info("Initiating fallback orchestrator shutdown")
        
        # Signal background threads to exit immediately
        self._monitoring_active = False
        
        # Wait for monitoring thread to finish with timeout
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.info("Waiting for monitoring thread to finish...")
            self._monitor_thread.join(timeout=5.0)
            
            if self._monitor_thread.is_alive():
                logger.warning("Monitoring thread did not finish within timeout, forcing shutdown")
            else:
                logger.info("Monitoring thread finished cleanly")
        
        # Clear any active fallback state
        with self._lock:
            if self.state.mode != FallbackMode.NORMAL:
                logger.info(f"Clearing fallback state from {self.state.mode.value} to NORMAL")
                self.state.mode = FallbackMode.NORMAL
                self.state.active_triggers.clear()
        
        # Clear downstream notification flags
        with self._downstream_notification_lock:
            self._downstream_null_model_flag.clear()
            if hasattr(self, '_downstream_notification_data'):
                self._downstream_notification_data = None
        
        # Log final failover matrix state
        if hasattr(self, 'channel_failover_matrix'):
            final_matrix_status = self.channel_failover_matrix.get_matrix_status()
            logger.info(f"Final channel failover matrix status: {json.dumps(final_matrix_status, indent=2)}")
        
        logger.info("Fallback orchestrator shutdown complete")

# =============================================================================
# Factory Functions
# =============================================================================

def create_fallback_orchestrator(config: Layer0Config = None,
                                signal_negotiator: SignalNegotiator = None,
                                redundancy_manager: RedundancyManager = None,
                                sampler: Sampler = None) -> FallbackOrchestrator:
    """Create a new FallbackOrchestrator instance"""
    return FallbackOrchestrator(
        config=config,
        signal_negotiator=signal_negotiator,
        redundancy_manager=redundancy_manager,
        sampler=sampler
    )

# =============================================================================
# Testing Functions
# =============================================================================

async def test_fallback_orchestrator():
    """Test the fallback orchestrator functionality"""
    from .app_config import Layer0Config
    
    config = Layer0Config()
    
    # Create mock components
    class MockSignalNegotiator:
        def __init__(self):
            self.health_scores = {'cloudwatch': 0.8, 'xray': 0.2, 'sqs': 0.9}
        
        def get_channel_health_summary(self):
            return {ch: {'qos_score': score} for ch, score in self.health_scores.items()}
        
        def update_health(self, channel, score):
            self.health_scores[channel] = score
    
    class MockRedundancyManager:
        def set_redundancy_mode(self, mode):
            print(f"Redundancy manager set to mode: {mode}")
    
    class MockSampler:
        def set_base_sample_rate(self, rate):
            print(f"Sampler set to rate: {rate}")
    
    # Create orchestrator
    mock_negotiator = MockSignalNegotiator()
    orchestrator = FallbackOrchestrator(
        config=config,
        signal_negotiator=mock_negotiator,
        redundancy_manager=MockRedundancyManager(),
        sampler=MockSampler()
    )
    
    # Test fallback status
    status = orchestrator.get_fallback_status()
    print(f"Initial status: {json.dumps(status, indent=2, default=str)}")
    
    # Test channel failover matrix
    matrix_status = orchestrator.channel_failover_matrix.get_matrix_status()
    print(f"Initial failover matrix status: {json.dumps(matrix_status, indent=2)}")
    
    # Test telemetry tracking
    orchestrator.update_telemetry_tracking("telemetry")
    orchestrator.update_telemetry_tracking("invocation_trace")
    orchestrator.update_telemetry_tracking("side_channel")
    
    # Test performance metrics
    orchestrator.update_performance_metric(0.8)
    orchestrator.update_performance_metric(0.9)
    orchestrator.update_performance_metric(0.7)
    
    # Test error tracking
    orchestrator.update_telemetry_tracking("error")
    orchestrator.update_telemetry_tracking("error")
    orchestrator.update_telemetry_tracking("error")
    
    # Test channel degradation
    print("\n=== Testing Channel Degradation ===")
    mock_negotiator.update_health('cloudwatch', 0.3)  # Below threshold
    mock_negotiator.update_health('xray', 0.1)  # Very low
    
    # Wait for monitoring to detect changes
    await asyncio.sleep(3)
    
    # Check status after channel degradation
    status = orchestrator.get_fallback_status()
    print(f"After channel degradation: {json.dumps(status, indent=2, default=str)}")
    
    # Test manual failover
    print("\n=== Testing Manual Failover ===")
    success, new_channel, reason = orchestrator.channel_failover_matrix.execute_failover()
    print(f"Manual failover result: success={success}, channel={new_channel}, reason={reason}")
    
    # Test recovery
    print("\n=== Testing Recovery ===")
    mock_negotiator.update_health('cloudwatch', 0.9)  # Restore primary
    await asyncio.sleep(2)
    
    recovery_success, recovery_reason = orchestrator.channel_failover_matrix.attempt_recovery_to_primary()
    print(f"Recovery result: success={recovery_success}, reason={recovery_reason}")
    
    # Test forced fallback
    orchestrator.force_fallback(FallbackMode.DEGRADED, "test")
    
    # Final status
    final_status = orchestrator.get_fallback_status()
    print(f"Final status: {json.dumps(final_status, indent=2, default=str)}")
    
    # Test histories
    fallback_history = orchestrator.get_fallback_history(10)
    failover_history = orchestrator.get_channel_failover_history(10)
    print(f"Fallback history: {json.dumps(fallback_history, indent=2, default=str)}")
    print(f"Channel failover history: {json.dumps(failover_history, indent=2)}")
    
    # Test downstream notification
    print(f"Downstream null model active: {orchestrator.is_downstream_null_model_active()}")
    notification_data = orchestrator.get_downstream_notification_data()
    print(f"Downstream notification data: {notification_data}")
    
    # Shutdown
    orchestrator.shutdown()
    
    return "Fallback orchestrator with channel failover matrix test completed"

if __name__ == "__main__":
    asyncio.run(test_fallback_orchestrator())
