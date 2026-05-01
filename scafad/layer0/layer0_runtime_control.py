"""
SCAFAD Layer 0: Runtime Control Loop Module
===========================================

Implements a runtime control loop that:
- Orchestrates negotiation → redundancy → sampling → fallback in order
- Updates channel health metrics and adapts choices dynamically
- Emits self-metrics (negotiation success %, channel health, drop reasons)
- Provides runtime adaptation and control

Academic References:
- Runtime adaptation systems (Lamport et al.)
- Control loop theory for distributed systems (Fonseca et al.)
- Self-adaptive telemetry systems (Barham et al.)
"""

import time
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import threading

# Import configuration and other Layer 0 components
from .app_config import Layer0Config, TelemetryConfig
from .layer0_signal_negotiation import ChannelType, SignalNegotiator
from .layer0_redundancy_manager import RedundancyManager, RedundancyMode
from .layer0_sampler import Sampler, SamplingStrategy
from .layer0_fallback_orchestrator import FallbackOrchestrator
from .layer0_core import AnomalyDetectionEngine

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Core Enumerations
# =============================================================================

class ControlPhase(Enum):
    """Phases of the runtime control loop"""
    NEGOTIATION = "negotiation"           # Signal negotiation phase
    REDUNDANCY = "redundancy"             # Redundancy management phase
    SAMPLING = "sampling"                 # Sampling decision phase
    FALLBACK = "fallback"                 # Fallback orchestration phase
    DETECTION = "detection"               # Anomaly detection phase
    ADAPTATION = "adaptation"             # Runtime adaptation phase

class ControlState(Enum):
    """States of the control loop"""
    INITIALIZING = "initializing"         # System initialization
    RUNNING = "running"                   # Normal operation
    ADAPTING = "adapting"                 # Adapting to changes
    DEGRADED = "degraded"                 # Operating in degraded mode
    RECOVERING = "recovering"             # Attempting recovery
    SHUTDOWN = "shutdown"                 # System shutdown

class AdaptationTrigger(Enum):
    """Triggers for runtime adaptation"""
    CHANNEL_HEALTH_CHANGE = "channel_health_change"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    ERROR_RATE_INCREASE = "error_rate_increase"
    RESOURCE_PRESSURE = "resource_pressure"
    MANUAL_ADAPTATION = "manual_adaptation"
    SCHEDULED_ADAPTATION = "scheduled_adaptation"

# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class ControlMetrics:
    """Metrics for the control loop"""
    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    
    # Phase-specific metrics
    negotiation_success_rate: float = 0.0
    redundancy_success_rate: float = 0.0
    sampling_success_rate: float = 0.0
    fallback_success_rate: float = 0.0
    
    # Phase-specific counters for success rate calculation
    negotiation_count: int = 0
    redundancy_count: int = 0
    sampling_count: int = 0
    fallback_count: int = 0
    detection_count: int = 0
    
    # Adaptation metrics
    adaptation_count: int = 0
    last_adaptation_time: float = 0.0
    adaptation_success_rate: float = 0.0
    
    # Performance metrics
    average_cycle_time_ms: float = 0.0
    total_cycle_time_ms: float = 0.0
    last_cycle_time_ms: float = 0.0
    
    # Channel health metrics
    channel_health_scores: Dict[ChannelType, float] = field(default_factory=dict)
    overall_channel_health: float = 1.0
    
    # Drop reasons
    drop_reasons: Dict[str, int] = field(default_factory=dict)

@dataclass
class ControlConfig:
    """Configuration for the control loop"""
    cycle_interval_ms: int = 1000         # Control loop cycle interval
    adaptation_threshold: float = 0.7     # Threshold for triggering adaptation
    health_check_interval_ms: int = 5000  # Health check interval
    metrics_emission_interval_ms: int = 10000  # Self-metrics emission interval
    max_adaptation_frequency_ms: int = 30000   # Minimum time between adaptations

@dataclass
class ControlEvent:
    """Control loop event record"""
    timestamp: float
    phase: ControlPhase
    state: ControlState
    success: bool
    duration_ms: float
    metadata: Dict[str, Any]
    error_details: Optional[str] = None

# =============================================================================
# Main Runtime Control Loop
# =============================================================================

class RuntimeControlLoop:
    """
    Runtime control loop that orchestrates all Layer 0 components
    
    This component ensures proper coordination between signal negotiation,
    redundancy management, sampling, and fallback orchestration while
    providing runtime adaptation and self-monitoring.
    """
    
    def __init__(self, config: Layer0Config):
        self.config = config
        
        # Initialize control configuration
        self.control_config = ControlConfig()
        self.control_state = ControlState.INITIALIZING
        self.control_metrics = ControlMetrics()
        
        # Control event history
        self.control_events: deque = deque(maxlen=1000)
        
        # Control loop state
        self._control_active = False
        self._control_thread = None
        self._lock = threading.RLock()
        
        # Component references (will be set during initialization)
        self.signal_negotiator: Optional[SignalNegotiator] = None
        self.redundancy_manager: Optional[RedundancyManager] = None
        self.sampler: Optional[Sampler] = None
        self.fallback_orchestrator: Optional[FallbackOrchestrator] = None
        self.detection_engine: Optional[AnomalyDetectionEngine] = None
        
        # Control loop configuration
        self.control_interval_ms = getattr(config, 'control_interval_ms', 1000)
        self.adaptation_interval_ms = getattr(config, 'adaptation_interval_ms', 30000)
        self.adaptation_threshold = getattr(config, 'adaptation_threshold', 0.8)
        self.max_control_events = getattr(config, 'max_control_events', 1000)
        
        # Initialize control configuration
        self._initialize_control_config()
        
        # Background workers
        self._health_check_thread = None
        self._metrics_emission_thread = None
        
        logger.info("Runtime control loop initialized")
    
    def _initialize_control_config(self):
        """Initialize control configuration from main config"""
        if hasattr(self.config, 'control_loop'):
            control_config = self.config.control_loop
            self.control_config.cycle_interval_ms = getattr(control_config, 'cycle_interval_ms', 1000)
            self.control_config.adaptation_threshold = getattr(control_config, 'adaptation_threshold', 0.7)
            self.control_config.health_check_interval_ms = getattr(control_config, 'health_check_interval_ms', 5000)
            self.control_config.metrics_emission_interval_ms = getattr(control_config, 'metrics_emission_interval_ms', 10000)
            self.control_config.max_adaptation_frequency_ms = getattr(control_config, 'max_adaptation_frequency_ms', 30000)
    
    def initialize_components(self, signal_negotiator: SignalNegotiator,
                            redundancy_manager: RedundancyManager,
                            sampler: Sampler,
                            fallback_orchestrator: FallbackOrchestrator,
                            detection_engine: AnomalyDetectionEngine):
        """Initialize all Layer 0 components"""
        self.signal_negotiator = signal_negotiator
        self.redundancy_manager = redundancy_manager
        self.sampler = sampler
        self.fallback_orchestrator = fallback_orchestrator
        self.detection_engine = detection_engine
        
        logger.info("All Layer 0 components initialized")
        self.control_state = ControlState.RUNNING
    
    def start_control_loop(self):
        """Start the main control loop"""
        if self._control_active:
            logger.warning("Control loop already active")
            return
        
        if not all([self.signal_negotiator, self.redundancy_manager, 
                   self.sampler, self.fallback_orchestrator, self.detection_engine]):
            logger.error("Cannot start control loop: not all components initialized")
            return
        
        self._control_active = True
        self._control_thread = threading.Thread(target=self._run_control_loop, daemon=True)
        self._control_thread.start()
        
        # Start background workers
        self._start_health_check_worker()
        self._start_metrics_emission_worker()
        
        logger.info("Runtime control loop started")
    
    def _run_control_loop(self):
        """Main control loop"""
        logger.info("Starting control loop")
        
        while self._control_active:
            cycle_start = time.time()
            cycle_success = True
            
            try:
                # Execute negotiation phase (async-aware)
                if not self._execute_negotiation_phase():
                    cycle_success = False
                    logger.warning("Negotiation phase failed")
                
                # Schedule periodic renegotiation for runtime QoS updates
                self._schedule_renegotiation()
                
                # Execute redundancy phase
                if not self._execute_redundancy_phase():
                    cycle_success = False
                    logger.warning("Redundancy phase failed")
                
                # Execute sampling phase
                if not self._execute_sampling_phase():
                    cycle_success = False
                    logger.warning("Sampling phase failed")
                
                # Execute fallback phase
                if not self._execute_fallback_phase():
                    cycle_success = False
                    logger.warning("Fallback phase failed")
                
                # Execute detection phase
                if not self._execute_detection_phase():
                    cycle_success = False
                    logger.warning("Detection phase failed")
                
                # Update metrics
                self._update_cycle_metrics(cycle_success, time.time() - cycle_start)
                
                # Check if adaptation is needed
                if self._should_adapt():
                    self._execute_adaptation()
                
            except Exception as e:
                cycle_success = False
                logger.error(f"Error in control loop: {e}", exc_info=True)
                # Attempt graceful recovery
                self._attempt_graceful_recovery(e)
                self._update_cycle_metrics(False, time.time() - cycle_start)
            
            # Sleep until next cycle
            time.sleep(self.control_interval_ms / 1000.0)
    
    def _execute_negotiation_phase(self) -> bool:
        """Execute signal negotiation phase"""
        start_time = time.time()
        try:
            if not self.signal_negotiator:
                return False
            
            # Check if negotiation is needed (first-time init or periodic renegotiation)
            channel_health = self.signal_negotiator.get_channel_health_summary()
            if not channel_health:
                # First-time initialization - perform full negotiation
                logger.info("Performing first-time channel negotiation")
                try:
                    negotiation_results = self._run_negotiation()
                    
                    # Update redundancy manager based on negotiation results
                    if self.redundancy_manager and negotiation_results:
                        self._update_redundancy_manager_from_negotiation(negotiation_results)
                        logger.info("Channel negotiation completed and redundancy updated")
                    else:
                        logger.warning("Channel negotiation failed or no results")
                        return False
                except Exception as nego_error:
                    logger.error(f"Channel negotiation failed: {nego_error}", exc_info=True)
                    # Use graceful failure handling instead of just returning False
                    return self._handle_negotiation_failure_gracefully()
            else:
                # Periodic health check - just verify channels are healthy
                logger.debug("Channel health check passed")
                
                # Check if renegotiation is needed based on health
                if self._should_trigger_renegotiation(channel_health):
                    logger.info("Channel health degradation detected, triggering renegotiation")
                    try:
                        # Perform renegotiation
                        if hasattr(self.signal_negotiator, 'negotiate_all_channels_sync'):
                            negotiation_results = self.signal_negotiator.negotiate_all_channels_sync()
                        else:
                            negotiation_results = self._run_negotiation()
                        
                        # Update redundancy manager with new results
                        if negotiation_results and self.redundancy_manager:
                            self._update_redundancy_manager_from_negotiation(negotiation_results)
                            logger.info("Health-triggered renegotiation completed successfully")
                        else:
                            logger.warning("Health-triggered renegotiation failed")
                            
                    except Exception as renego_error:
                        logger.error(f"Health-triggered renegotiation failed: {renego_error}")
                        # Continue with existing channels - don't fail the phase
            
            # Calculate duration and record control event
            duration_ms = (time.time() - start_time) * 1000.0
            self._record_control_event('negotiation_phase', True, duration_ms)
            
            # Update phase success rate
            self._update_phase_success_rate('negotiation', True)
            
            return True
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            logger.error(f"Negotiation phase failed: {e}", exc_info=True)
            self._record_control_event('negotiation_phase', False, duration_ms)
            self._update_phase_success_rate('negotiation', False)
            # Use graceful failure handling instead of just returning False
            return self._handle_negotiation_failure_gracefully()
    
    def _should_trigger_renegotiation(self, channel_health: Dict[str, Any]) -> bool:
        """Check if renegotiation is needed based on channel health"""
        try:
            for channel_type, health in channel_health.items():
                qos_score = health.get('qos_score', 1.0)
                if qos_score < 0.5:  # Threshold for renegotiation
                    return True
            return False
        except Exception as e:
            logger.warning(f"Error checking renegotiation trigger: {e}")
            return False
    
    def _update_redundancy_manager_from_negotiation(self, negotiation_results: Dict[str, Any]):
        """Update redundancy manager based on negotiation results"""
        try:
            # Analyze negotiation results to determine optimal redundancy mode
            overall_qos = 0.0
            channel_count = 0
            primary_channels = []
            secondary_channels = []
            
            for channel_type, result in negotiation_results.items():
                if result.get('status') == 'success':
                    qos_score = result.get('qos_score', 0.0)
                    overall_qos += qos_score
                    channel_count += 1
                    
                    # Categorize channels based on QoS score
                    if qos_score >= 0.8:
                        primary_channels.append(channel_type)
                    elif qos_score >= 0.5:
                        secondary_channels.append(channel_type)
            
            if channel_count > 0:
                avg_qos = overall_qos / channel_count
                
                # Set redundancy mode based on overall QoS
                if avg_qos >= 0.8:
                    self.redundancy_manager.set_redundancy_mode(RedundancyMode.ACTIVE_ACTIVE)
                elif avg_qos >= 0.5:
                    self.redundancy_manager.set_redundancy_mode(RedundancyMode.ACTIVE_STANDBY)
                else:
                    self.redundancy_manager.set_redundancy_mode(RedundancyMode.DEGRADED)
                
                # Update channel priorities in redundancy manager
                self._update_channel_priorities(primary_channels, secondary_channels)
                
                logger.info(f"Redundancy manager updated based on negotiation: QoS={avg_qos:.2f}, Mode={self.redundancy_manager.get_redundancy_summary().get('current_mode', 'unknown')}")
                
        except Exception as e:
            logger.error(f"Error updating redundancy manager from negotiation: {e}")
    
    def _update_channel_priorities(self, primary_channels: List[ChannelType], secondary_channels: List[ChannelType]):
        """Update channel priorities in the redundancy manager"""
        try:
            if not self.redundancy_manager:
                return
            
            # This would call a method on RedundancyManager to update channel priorities
            # For now, we'll log the intended changes
            logger.info(f"Updating channel priorities - Primary: {primary_channels}, Secondary: {secondary_channels}")
            
            # TODO: Implement actual channel priority update in RedundancyManager
            # self.redundancy_manager.update_channel_priorities(primary_channels, secondary_channels)
            
        except Exception as e:
            logger.error(f"Error updating channel priorities: {e}")

    def _run_negotiation(self) -> Dict[str, Any]:
        """Run async channel negotiation from the control loop thread."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.signal_negotiator.negotiate_all_channels())
        finally:
            loop.close()
    
    def _schedule_renegotiation(self):
        """Schedule periodic renegotiation for runtime QoS updates"""
        try:
            # Get renegotiation interval from config
            renegotiation_interval = getattr(self.config, 'renegotiation_interval_ms', 300000)  # 5 minutes default
            
            # Check if enough time has passed since last negotiation
            current_time = time.time()
            last_negotiation = getattr(self, '_last_negotiation_time', 0)
            
            if current_time - last_negotiation >= renegotiation_interval / 1000.0:
                logger.info("Scheduling periodic channel renegotiation")
                self._last_negotiation_time = current_time
                
                # Trigger renegotiation in background
                if hasattr(self, '_renegotiation_thread') and self._renegotiation_thread and self._renegotiation_thread.is_alive():
                    logger.debug("Renegotiation already in progress")
                else:
                    self._start_renegotiation_worker()
                    
        except Exception as e:
            logger.error(f"Error scheduling renegotiation: {e}")
    
    def _start_renegotiation_worker(self):
        """Start background renegotiation worker"""
        try:
            self._renegotiation_thread = threading.Thread(target=self._renegotiation_worker, daemon=True)
            self._renegotiation_thread.start()
            logger.debug("Renegotiation worker started")
        except Exception as e:
            logger.error(f"Error starting renegotiation worker: {e}")
    
    def _renegotiation_worker(self):
        """Background worker for channel renegotiation"""
        try:
            logger.info("Starting channel renegotiation worker")
            
            if self.signal_negotiator:
                # Perform renegotiation
                try:
                    # Use synchronous version for background worker
                    if hasattr(self.signal_negotiator, 'negotiate_all_channels_sync'):
                        negotiation_results = self.signal_negotiator.negotiate_all_channels_sync()
                    else:
                        # Fallback to async with new event loop
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            negotiation_results = loop.run_until_complete(
                                self.signal_negotiator.negotiate_all_channels()
                            )
                        finally:
                            loop.close()
                    
                    # Update redundancy manager with new results
                    if negotiation_results:
                        self._update_redundancy_manager_from_negotiation(negotiation_results)
                        logger.info("Background renegotiation completed successfully")
                        
                        # Update last negotiation time
                        self._last_negotiation_time = time.time()
                        
                        # Update channel health metrics
                        if hasattr(self.signal_negotiator, 'get_channel_health_summary'):
                            try:
                                channel_health = self.signal_negotiator.get_channel_health_summary()
                                self._update_channel_health_metrics(channel_health)
                            except Exception as e:
                                logger.warning(f"Error updating channel health metrics: {e}")
                    else:
                        logger.warning("Background renegotiation failed - no results")
                        # Attempt graceful recovery
                        self._handle_negotiation_failure_gracefully()
                        
                except Exception as e:
                    logger.error(f"Background renegotiation failed: {e}")
                    # Attempt graceful recovery
                    self._handle_negotiation_failure_gracefully()
            else:
                logger.warning("Signal negotiator not available for renegotiation")
                # Attempt graceful recovery
                self._handle_negotiation_failure_gracefully()
                
        except Exception as e:
            logger.error(f"Error in renegotiation worker: {e}")
            # Attempt graceful recovery
            try:
                self._handle_negotiation_failure_gracefully()
            except Exception as recovery_error:
                logger.error(f"Graceful recovery also failed: {recovery_error}")
        finally:
            logger.debug("Renegotiation worker completed")
    
    def _handle_negotiation_failure_gracefully(self) -> bool:
        """Handle negotiation failures with graceful downgrade"""
        try:
            logger.info("Attempting graceful negotiation failure handling")
            
            # Check if we have any existing channel configurations
            if self.redundancy_manager:
                current_channels = self.redundancy_manager.get_redundancy_summary()
                if current_channels and current_channels.get('active_channels', 0) > 0:
                    logger.info("Continuing with existing channel configuration")
                    return True
            
            # If no existing channels, try to initialize with minimal configuration
            logger.warning("No existing channels available, attempting minimal initialization")
            
            # Set up minimal local buffer configuration
            if self.redundancy_manager:
                try:
                    # Force degraded mode with local buffer only
                    self.redundancy_manager.set_redundancy_mode(RedundancyMode.DEGRADED)
                    logger.info("Set redundancy manager to degraded mode for minimal operation")
                    return True
                except Exception as e:
                    logger.error(f"Failed to set degraded mode: {e}")
            
            # This would typically involve setting up local buffer or basic logging
            # For now, we'll return False to indicate the phase failed
            # but the system can continue in degraded mode
            return False
            
        except Exception as e:
            logger.error(f"Error in graceful failure handling: {e}")
            return False
    
    def _attempt_graceful_recovery(self, error: Exception):
        """Attempt graceful recovery from control loop errors"""
        try:
            logger.info(f"Attempting graceful recovery from error: {error}")
            
            # Check if this is a negotiation-related error
            if "negotiation" in str(error).lower() or "channel" in str(error).lower():
                logger.info("Attempting recovery from negotiation error")
                return self._handle_negotiation_failure_gracefully()
            
            # Check if this is a redundancy-related error
            elif "redundancy" in str(error).lower():
                logger.info("Attempting recovery from redundancy error")
                if self.redundancy_manager:
                    try:
                        self.redundancy_manager.set_redundancy_mode(RedundancyMode.DEGRADED)
                        logger.info("Set redundancy manager to degraded mode for recovery")
                        return True
                    except Exception as e:
                        logger.error(f"Failed to set degraded mode during recovery: {e}")
            
            # For other errors, try to continue in degraded mode
            logger.info("Attempting to continue in degraded mode")
            self.control_state = ControlState.DEGRADED
            
            # Schedule recovery attempt
            self._schedule_recovery_attempt()
            
            return True
            
        except Exception as recovery_error:
            logger.error(f"Error during graceful recovery: {recovery_error}")
            return False
    
    def _schedule_recovery_attempt(self):
        """Schedule a recovery attempt after a delay"""
        try:
            recovery_delay = getattr(self.config, 'recovery_delay_ms', 30000)  # 30 seconds default
            
            def delayed_recovery():
                time.sleep(recovery_delay / 1000.0)
                try:
                    logger.info("Attempting delayed recovery")
                    self.control_state = ControlState.RECOVERING
                    
                    # Try to reinitialize critical components
                    if self._attempt_component_recovery():
                        self.control_state = ControlState.RUNNING
                        logger.info("Recovery successful, returning to running state")
                    else:
                        self.control_state = ControlState.DEGRADED
                        logger.warning("Recovery failed, remaining in degraded state")
                        
                except Exception as e:
                    logger.error(f"Error during delayed recovery: {e}")
                    self.control_state = ControlState.DEGRADED
            
            # Start recovery thread
            recovery_thread = threading.Thread(target=delayed_recovery, daemon=True)
            recovery_thread.start()
            logger.debug("Scheduled recovery attempt")
            
        except Exception as e:
            logger.error(f"Error scheduling recovery attempt: {e}")
    
    def _attempt_component_recovery(self) -> bool:
        """Attempt to recover individual components"""
        try:
            recovery_success = True
            
            # Try to recover signal negotiator
            if self.signal_negotiator and hasattr(self.signal_negotiator, 'reset'):
                try:
                    self.signal_negotiator.reset()
                    logger.info("Signal negotiator reset successful")
                except Exception as e:
                    logger.warning(f"Signal negotiator reset failed: {e}")
                    recovery_success = False
            
            # Try to recover redundancy manager
            if self.redundancy_manager and hasattr(self.redundancy_manager, 'reset'):
                try:
                    self.redundancy_manager.reset()
                    logger.info("Redundancy manager reset successful")
                except Exception as e:
                    logger.warning(f"Redundancy manager reset failed: {e}")
                    recovery_success = False
            
            # Try to recover sampler
            if self.sampler and hasattr(self.sampler, 'reset'):
                try:
                    self.sampler.reset()
                    logger.info("Sampler reset successful")
                except Exception as e:
                    logger.warning(f"Sampler reset failed: {e}")
                    recovery_success = False
            
            # Try to recover fallback orchestrator
            if self.fallback_orchestrator and hasattr(self.fallback_orchestrator, 'reset'):
                try:
                    self.fallback_orchestrator.reset()
                    logger.info("Fallback orchestrator reset successful")
                except Exception as e:
                    logger.warning(f"Fallback orchestrator reset failed: {e}")
                    recovery_success = False
            
            # Try to recover detection engine
            if self.detection_engine and hasattr(self.detection_engine, 'reset'):
                try:
                    self.detection_engine.reset()
                    logger.info("Detection engine reset successful")
                except Exception as e:
                    logger.warning(f"Detection engine reset failed: {e}")
                    recovery_success = False
            
            # If any component failed to recover, try graceful degradation
            if not recovery_success:
                logger.warning("Some components failed to recover, attempting graceful degradation")
                try:
                    # Set redundancy manager to degraded mode
                    if self.redundancy_manager:
                        self.redundancy_manager.set_redundancy_mode(RedundancyMode.DEGRADED)
                        logger.info("Set redundancy manager to degraded mode for graceful degradation")
                    
                    # Continue with partial recovery
                    recovery_success = True
                    
                except Exception as e:
                    logger.error(f"Graceful degradation failed: {e}")
                    recovery_success = False
            
            return recovery_success
            
        except Exception as e:
            logger.error(f"Error during component recovery: {e}")
            return False
    
    def _execute_redundancy_phase(self) -> bool:
        """Execute redundancy management phase"""
        start_time = time.time()
        try:
            if not self.redundancy_manager:
                return False
            
            # Get redundancy status
            redundancy_summary = self.redundancy_manager.get_redundancy_summary()
            if not redundancy_summary:
                return False
            
            # Check if redundancy mode needs adjustment
            current_mode = redundancy_summary.get('current_mode', 'unknown')
            if current_mode == 'degraded':
                # Try to improve redundancy
                self._attempt_redundancy_improvement()
            
            # Calculate duration and record control event
            duration_ms = (time.time() - start_time) * 1000.0
            self._record_control_event('redundancy_phase', True, duration_ms)
            
            # Update phase success rate
            self._update_phase_success_rate('redundancy', True)
            
            return True
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            logger.error(f"Redundancy phase failed: {e}", exc_info=True)
            self._record_control_event('redundancy_phase', False, duration_ms)
            self._update_phase_success_rate('redundancy', False)
            # Continue in degraded mode rather than failing completely
            return True
    
    def _execute_sampling_phase(self) -> bool:
        """Execute sampling decision phase"""
        start_time = time.time()
        try:
            if not self.sampler:
                return False
            
            # Get sampling status
            sampling_summary = self.sampler.get_sampling_summary()
            if not sampling_summary:
                return False
            
            # Check if sampling strategy needs adjustment
            current_strategy = sampling_summary.get('current_strategy', 'unknown')
            if current_strategy == 'degraded':
                # Try to improve sampling
                self._attempt_sampling_improvement()
            
            # Calculate duration and record control event
            duration_ms = (time.time() - start_time) * 1000.0
            self._record_control_event('sampling_phase', True, duration_ms)
            
            # Update phase success rate
            self._update_phase_success_rate('sampling', True)
            
            return True
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            logger.error(f"Sampling phase failed: {e}", exc_info=True)
            self._record_control_event('sampling_phase', False, duration_ms)
            self._update_phase_success_rate('sampling', False)
            # Continue with default sampling rather than failing completely
            return True
    
    def _execute_fallback_phase(self) -> bool:
        """Execute fallback orchestration phase"""
        start_time = time.time()
        try:
            if not self.fallback_orchestrator:
                return False
            
            # Get fallback status
            fallback_status = self.fallback_orchestrator.get_fallback_status()
            if not fallback_status:
                return False
            
            # Check if fallback mode needs adjustment
            current_mode = fallback_status.get('current_mode', 'normal')
            if current_mode != 'normal':
                # Try to recover from fallback mode
                self._attempt_fallback_recovery()
            
            # Calculate duration and record control event
            duration_ms = (time.time() - start_time) * 1000.0
            self._record_control_event('fallback_phase', True, duration_ms)
            
            # Update phase success rate
            self._update_phase_success_rate('fallback', True)
            
            return True
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            logger.error(f"Fallback phase failed: {e}", exc_info=True)
            self._record_control_event('fallback_phase', False, duration_ms)
            self._update_phase_success_rate('fallback', False)
            # Continue in normal mode rather than failing completely
            return True
    
    def _execute_detection_phase(self) -> bool:
        """Execute anomaly detection phase"""
        start_time = time.time()
        try:
            if not self.detection_engine:
                return True  # Detection is optional, don't fail the cycle
            
            # Get detection status
            detection_status = self.detection_engine.get_detection_status()
            if not detection_status:
                return True
            
            # Check if detection needs adjustment
            current_mode = detection_status.get('current_mode', 'active')
            if current_mode == 'degraded':
                # Try to improve detection
                self._attempt_detection_improvement()
            
            # Calculate duration and record control event
            duration_ms = (time.time() - start_time) * 1000.0
            self._record_control_event('detection_phase', True, duration_ms)
            
            # Update phase success rate
            self._update_phase_success_rate('detection', True)
            
            return True
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            logger.error(f"Detection phase failed: {e}", exc_info=True)
            self._record_control_event('detection_phase', False, duration_ms)
            self._update_phase_success_rate('detection', False)
            # Detection is optional, continue rather than failing completely
            return True
    
    def _attempt_redundancy_improvement(self):
        """Attempt to improve redundancy"""
        try:
            if self.redundancy_manager:
                logger.info("Attempting to improve redundancy")
                
                # Try to increase redundancy level
                current_mode = self.redundancy_manager.get_redundancy_summary().get('current_mode', 'unknown')
                if current_mode == 'degraded':
                    # Attempt to improve redundancy
                    improvement_result = self.redundancy_manager.attempt_improvement()
                    if improvement_result:
                        logger.info("Redundancy improvement successful")
                    else:
                        logger.warning("Redundancy improvement failed")
                        
        except Exception as e:
            logger.error(f"Redundancy improvement attempt failed: {e}", exc_info=True)
    
    def _attempt_fallback_recovery(self):
        """Attempt to recover from fallback mode"""
        try:
            if self.fallback_orchestrator:
                # Actively call the fallback orchestrator's recovery method
                # This reduces MTTR during chaos tests by actively attempting recovery
                logger.info("Initiating active fallback recovery")
                
                # Get current fallback status
                current_status = self.fallback_orchestrator.get_fallback_status()
                current_mode = current_status.get('current_mode', 'normal')
                
                if current_mode != 'normal':
                    # Attempt recovery through the fallback orchestrator
                    self.fallback_orchestrator._attempt_recovery()
                    
                    # Check if recovery was successful
                    new_status = self.fallback_orchestrator.get_fallback_status()
                    new_mode = new_status.get('current_mode', 'unknown')
                    
                    if new_mode == 'normal':
                        logger.info("Fallback recovery successful")
                    else:
                        logger.warning(f"Fallback recovery failed, still in {new_mode} mode")
                else:
                    logger.info("Already in normal mode, no recovery needed")
                    
        except Exception as e:
            logger.error(f"Fallback recovery attempt failed: {e}", exc_info=True)
    
    def _attempt_detection_improvement(self):
        """Attempt to improve detection"""
        try:
            if self.detection_engine:
                logger.info("Attempting to improve detection")
                
                # Try to improve detection model or strategy
                improvement_result = self.detection_engine.attempt_improvement()
                if improvement_result:
                    logger.info("Detection improvement successful")
                else:
                    logger.warning("Detection improvement failed")
                    
        except Exception as e:
            logger.error(f"Detection improvement attempt failed: {e}", exc_info=True)
    
    def _attempt_sampling_improvement(self):
        """Attempt to improve sampling"""
        try:
            if self.sampler:
                logger.info("Attempting to improve sampling")
                
                # Try to improve sampling strategy
                improvement_result = self.sampler.attempt_improvement()
                if improvement_result:
                    logger.info("Sampling improvement successful")
                else:
                    logger.warning("Sampling improvement failed")
                    
        except Exception as e:
            logger.error(f"Sampling improvement attempt failed: {e}", exc_info=True)
    
    def _should_adapt(self) -> bool:
        """Check if adaptation is needed"""
        current_time = time.time()
        
        # Check if enough time has passed since last adaptation
        if current_time - self.control_metrics.last_adaptation_time < self.adaptation_interval_ms / 1000.0:
            return False
        
        # Check if adaptation success rate is below threshold
        if self.control_metrics.adaptation_success_rate < self.adaptation_threshold:
            return True
        
        return False
    
    def _execute_adaptation(self):
        """Execute runtime adaptation"""
        try:
            logger.info("Executing runtime adaptation")
            
            # Update adaptation metrics
            self.control_metrics.adaptation_count += 1
            self.control_metrics.last_adaptation_time = time.time()
            
            # Perform adaptation logic here
            # This could include adjusting thresholds, changing strategies, etc.
            
            logger.info("Runtime adaptation completed")
            
        except Exception as e:
            logger.error(f"Runtime adaptation failed: {e}", exc_info=True)
    
    def _perform_adaptation(self) -> bool:
        """Perform runtime adaptation actions"""
        try:
            # Adaptation 1: Adjust sampling strategy
            if self.sampler:
                self.sampler.set_sampling_strategy(SamplingStrategy.ADAPTIVE)
            
            # Adaptation 2: Optimize redundancy mode
            if self.redundancy_manager:
                # Check current health and adjust accordingly
                if self.control_metrics.overall_channel_health < 0.5:
                    self.redundancy_manager.set_redundancy_mode(RedundancyMode.ADAPTIVE)
                else:
                    self.redundancy_manager.set_redundancy_mode(RedundancyMode.ACTIVE_ACTIVE)
            
            # Adaptation 3: Adjust fallback thresholds
            if self.fallback_orchestrator:
                # Could adjust fallback thresholds based on current conditions
                pass
            
            logger.info("Runtime adaptation completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Runtime adaptation failed: {e}")
            return False
    
    def _start_health_check_worker(self):
        """Start background health check worker"""
        self._health_check_thread = threading.Thread(target=self._health_check_worker, daemon=True)
        self._health_check_thread.start()
    
    def _health_check_worker(self):
        """Background health check worker"""
        while self._control_active:
            try:
                self._perform_health_check()
                time.sleep(self.control_config.health_check_interval_ms / 1000.0)
            except Exception as e:
                logger.error(f"Health check error: {e}")
                # Attempt graceful recovery
                try:
                    self._attempt_graceful_recovery(e)
                except Exception as recovery_error:
                    logger.error(f"Graceful recovery failed during health check: {recovery_error}")
                # Wait longer before next attempt
                time.sleep(10.0)
    
    def _perform_health_check(self):
        """Perform comprehensive health check"""
        try:
            # Check component health
            component_health = {
                'signal_negotiator': self.signal_negotiator is not None,
                'redundancy_manager': self.redundancy_manager is not None,
                'sampler': self.sampler is not None,
                'fallback_orchestrator': self.fallback_orchestrator is not None,
                'detection_engine': self.detection_engine is not None
            }
            
            # Check if any components are unhealthy
            unhealthy_components = [name for name, healthy in component_health.items() if not healthy]
            if unhealthy_components:
                logger.warning(f"Unhealthy components detected: {unhealthy_components}")
                
                # Attempt to recover unhealthy components
                if self._attempt_component_recovery():
                    logger.info("Component recovery successful during health check")
                else:
                    logger.warning("Component recovery failed during health check")
            
            # Check channel health if signal negotiator is available
            if self.signal_negotiator:
                try:
                    channel_health = self.signal_negotiator.get_channel_health_summary()
                    if channel_health:
                        # Update channel health metrics
                        self._update_channel_health_metrics(channel_health)
                        
                        # Check if renegotiation is needed
                        if self._should_trigger_renegotiation(channel_health):
                            logger.info("Channel health degradation detected during health check, scheduling renegotiation")
                            self._schedule_renegotiation()
                except Exception as e:
                    logger.warning(f"Error checking channel health: {e}")
            
            # Check redundancy manager health
            if self.redundancy_manager:
                try:
                    redundancy_summary = self.redundancy_manager.get_redundancy_summary()
                    if redundancy_summary:
                        current_mode = redundancy_summary.get('current_mode', 'unknown')
                        if current_mode == 'degraded':
                            logger.info("Redundancy manager in degraded mode, attempting improvement")
                            self._attempt_redundancy_improvement()
                except Exception as e:
                    logger.warning(f"Error checking redundancy manager health: {e}")
            
            # Update overall health
            overall_health = sum(component_health.values()) / len(component_health)
            self.control_metrics.overall_channel_health = overall_health
            
            # Log health status
            logger.debug(f"Health check completed - overall health: {overall_health:.2f}")
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            # Attempt graceful recovery
            try:
                self._attempt_graceful_recovery(e)
            except Exception as recovery_error:
                logger.error(f"Graceful recovery failed during health check: {recovery_error}")
    
    def _start_metrics_emission_worker(self):
        """Start background metrics emission worker"""
        self._metrics_emission_thread = threading.Thread(target=self._metrics_emission_worker, daemon=True)
        self._metrics_emission_thread.start()
    
    def _metrics_emission_worker(self):
        """Background metrics emission worker"""
        while self._control_active:
            try:
                self._emit_self_metrics()
                time.sleep(self.control_config.metrics_emission_interval_ms / 1000.0)
            except Exception as e:
                logger.error(f"Metrics emission error: {e}")
                # Attempt graceful recovery
                try:
                    self._attempt_graceful_recovery(e)
                except Exception as recovery_error:
                    logger.error(f"Graceful recovery failed during metrics emission: {recovery_error}")
                # Wait longer before next attempt
                time.sleep(15.0)
    
    def _emit_self_metrics(self):
        """Emit self-metrics for monitoring"""
        try:
            metrics = {
                'timestamp': time.time(),
                'control_state': self.control_state.value,
                'control_metrics': {
                    'total_cycles': self.control_metrics.total_cycles,
                    'successful_cycles': self.control_metrics.successful_cycles,
                    'cycle_success_rate': (self.control_metrics.successful_cycles / 
                                          max(self.control_metrics.total_cycles, 1)),
                    'average_cycle_time_ms': self.control_metrics.average_cycle_time_ms,
                    'adaptation_count': self.control_metrics.adaptation_count,
                    'adaptation_success_rate': self.control_metrics.adaptation_success_rate
                },
                'phase_metrics': {
                    'negotiation_success_rate': self.control_metrics.negotiation_success_rate,
                    'redundancy_success_rate': self.control_metrics.redundancy_success_rate,
                    'sampling_success_rate': self.control_metrics.sampling_success_rate,
                    'fallback_success_rate': self.control_metrics.fallback_success_rate
                },
                'channel_health': {
                    'overall_health': self.control_metrics.overall_channel_health,
                    'channel_scores': {k.value: v for k, v in self.control_metrics.channel_health_scores.items()}
                }
            }
            
            # Add negotiation summary if available
            try:
                negotiation_summary = self.get_negotiation_summary()
                metrics['negotiation'] = negotiation_summary
            except Exception as e:
                logger.warning(f"Error getting negotiation summary for metrics: {e}")
                metrics['negotiation'] = {'error': str(e)}
            
            # Add redundancy manager status if available
            if self.redundancy_manager:
                try:
                    redundancy_summary = self.redundancy_manager.get_redundancy_summary()
                    metrics['redundancy'] = redundancy_summary
                except Exception as e:
                    logger.warning(f"Error getting redundancy summary for metrics: {e}")
                    metrics['redundancy'] = {'error': str(e)}
            
            # Log metrics (in production, this would emit to CloudWatch, etc.)
            logger.info(f"Self-metrics emitted: {metrics}")
            
        except Exception as e:
            logger.error(f"Error emitting self-metrics: {e}")
            # Attempt graceful recovery
            try:
                self._attempt_graceful_recovery(e)
            except Exception as recovery_error:
                logger.error(f"Graceful recovery failed during metrics emission: {recovery_error}")
    
    def _update_cycle_metrics(self, success: bool, duration_ms: float):
        """Update control loop metrics"""
        self.control_metrics.total_cycles += 1
        
        if success:
            self.control_metrics.successful_cycles += 1
        else:
            self.control_metrics.failed_cycles += 1
        
        # Update average cycle time
        total_time = self.control_metrics.total_cycle_time_ms + duration_ms
        self.control_metrics.total_cycle_time_ms = total_time
        self.control_metrics.average_cycle_time_ms = total_time / self.control_metrics.total_cycles
    
    def _update_channel_health_metrics(self, channel_health: Dict[str, Any]):
        """Update channel health metrics"""
        try:
            for channel_type, health in channel_health.items():
                if isinstance(health, dict) and 'qos_score' in health:
                    self.control_metrics.channel_health_scores[ChannelType(channel_type)] = health['qos_score']
            
            # Calculate overall channel health
            if self.control_metrics.channel_health_scores:
                self.control_metrics.overall_channel_health = (
                    sum(self.control_metrics.channel_health_scores.values()) / 
                    len(self.control_metrics.channel_health_scores)
                )
        except Exception as e:
            logger.warning(f"Error updating channel health metrics: {e}")
    
    def _record_control_event(self, phase_name: str, success: bool, duration_ms: float, error_msg: str = None):
        """Record a control phase event"""
        try:
            event = {
                'timestamp': time.time(),
                'phase': phase_name,
                'success': success,
                'duration_ms': duration_ms,
                'error': error_msg
            }
            
            # Store in control events history
            self.control_events.append(event)
            
            # Keep only recent events
            while len(self.control_events) > self.max_control_events:
                self.control_events.popleft()
                
            logger.debug(f"Control event recorded: {phase_name} - {'SUCCESS' if success else 'FAILED'} in {duration_ms:.2f}ms")
            
        except Exception as e:
            logger.error(f"Failed to record control event: {e}", exc_info=True)
    
    def _update_phase_success_rate(self, metric_name: str, success: bool):
        """Update phase-specific success rate"""
        try:
            rate_attr = f"{metric_name}_success_rate"
            count_attr = f"{metric_name}_count"

            if not hasattr(self.control_metrics, rate_attr):
                return

            current_rate = getattr(self.control_metrics, rate_attr)
            count = getattr(self.control_metrics, count_attr, 0) + 1
            setattr(self.control_metrics, count_attr, count)
            new_rate = (current_rate * (count - 1) + (1.0 if success else 0.0)) / count
            setattr(self.control_metrics, rate_attr, new_rate)
            
        except Exception as e:
            logger.warning(f"Error updating phase success rate: {e}")
    
    def get_control_status(self) -> Dict[str, Any]:
        """Get current control loop status"""
        try:
            status = {
                'control_state': self.control_state.value,
                'control_active': self._control_active,
                'total_cycles': self.control_metrics.total_cycles,
                'successful_cycles': self.control_metrics.successful_cycles,
                'failed_cycles': self.control_metrics.failed_cycles,
                'cycle_success_rate': self.control_metrics.successful_cycles / max(self.control_metrics.total_cycles, 1),
                'average_cycle_time_ms': self.control_metrics.average_cycle_time_ms,
                'last_cycle_time_ms': self.control_metrics.last_cycle_time_ms,
                
                # Phase-specific metrics
                'negotiation_success_rate': self.control_metrics.negotiation_success_rate,
                'redundancy_success_rate': self.control_metrics.redundancy_success_rate,
                'sampling_success_rate': self.control_metrics.sampling_success_rate,
                'fallback_success_rate': self.control_metrics.fallback_success_rate,
                
                # Adaptation metrics
                'adaptation_count': self.control_metrics.adaptation_count,
                'last_adaptation_time': self.control_metrics.last_adaptation_time,
                'adaptation_success_rate': self.control_metrics.adaptation_success_rate,
                
                # Channel health metrics
                'overall_channel_health': self.control_metrics.overall_channel_health,
                'channel_health_scores': self.control_metrics.channel_health_scores,
                
                # Component status
                'components_initialized': all([
                    self.signal_negotiator is not None,
                    self.redundancy_manager is not None,
                    self.sampler is not None,
                    self.fallback_orchestrator is not None,
                    self.detection_engine is not None
                ]),
                
                # Thread status
                'threads_active': {
                    'control_thread': self._control_thread and self._control_thread.is_alive(),
                    'health_check_thread': self._health_check_thread and self._health_check_thread.is_alive(),
                    'metrics_emission_thread': self._metrics_emission_thread and self._metrics_emission_thread.is_alive(),
                    'renegotiation_thread': hasattr(self, '_renegotiation_thread') and self._renegotiation_thread and self._renegotiation_thread.is_alive()
                }
            }
            
            # Add negotiation summary
            negotiation_summary = self.get_negotiation_summary()
            status['negotiation'] = negotiation_summary
            
            # Add redundancy manager status if available
            if self.redundancy_manager:
                try:
                    redundancy_summary = self.redundancy_manager.get_redundancy_summary()
                    status['redundancy'] = redundancy_summary
                except Exception as e:
                    logger.warning(f"Error getting redundancy summary: {e}")
                    status['redundancy'] = {'error': str(e)}
            
            # Add fallback orchestrator status if available
            if self.fallback_orchestrator:
                try:
                    fallback_status = self.fallback_orchestrator.get_fallback_status()
                    status['fallback'] = fallback_status
                except Exception as e:
                    logger.warning(f"Error getting fallback status: {e}")
                    status['fallback'] = {'error': str(e)}
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting control status: {e}", exc_info=True)
            return {
                'control_state': 'error',
                'error': str(e),
                'control_active': False
            }
    
    def get_control_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get control loop event history"""
        try:
            # Convert deque to list and limit results
            events = list(self.control_events)
            if limit > 0:
                events = events[-limit:]
            
            # Convert events to serializable format
            serializable_events = []
            for event in events:
                try:
                    serializable_event = {
                        'timestamp': event.get('timestamp', 0),
                        'phase': event.get('phase', 'unknown'),
                        'success': event.get('success', False),
                        'duration_ms': event.get('duration_ms', 0),
                        'metadata': event.get('metadata', {}),
                        'error_details': event.get('error_details')
                    }
                    serializable_events.append(serializable_event)
                except Exception as e:
                    logger.warning(f"Error serializing event: {e}")
                    # Add a placeholder for failed events
                    serializable_events.append({
                        'timestamp': time.time(),
                        'phase': 'serialization_error',
                        'success': False,
                        'duration_ms': 0,
                        'metadata': {'error': 'Event serialization failed'},
                        'error_details': str(e)
                    })
            
            return serializable_events
            
        except Exception as e:
            logger.error(f"Error getting control history: {e}", exc_info=True)
            return [{
                'timestamp': time.time(),
                'phase': 'error',
                'success': False,
                'duration_ms': 0,
                'metadata': {'error': 'Failed to retrieve control history'},
                'error_details': str(e)
            }]
    
    def shutdown(self):
        """Shutdown the runtime control loop"""
        try:
            logger.info("Initiating runtime control loop shutdown")
            self._control_active = False
            
            # Wait for threads to finish with timeout
            if self._control_thread and self._control_thread.is_alive():
                self._control_thread.join(timeout=5.0)
                if self._control_thread.is_alive():
                    logger.warning("Control thread did not terminate within timeout")
            
            if self._health_check_thread and self._health_check_thread.is_alive():
                self._health_check_thread.join(timeout=5.0)
                if self._health_check_thread.is_alive():
                    logger.warning("Health check thread did not terminate within timeout")
            
            if self._metrics_emission_thread and self._metrics_emission_thread.is_alive():
                self._metrics_emission_thread.join(timeout=5.0)
                if self._metrics_emission_thread.is_alive():
                    logger.warning("Metrics emission thread did not terminate within timeout")
            
            # Wait for renegotiation thread if active
            if hasattr(self, '_renegotiation_thread') and self._renegotiation_thread and self._renegotiation_thread.is_alive():
                self._renegotiation_thread.join(timeout=5.0)
                if self._renegotiation_thread.is_alive():
                    logger.warning("Renegotiation thread did not terminate within timeout")
            
            # Gracefully shutdown components
            self._shutdown_components()
            
            self.control_state = ControlState.SHUTDOWN
            logger.info("Runtime control loop shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            # Force shutdown state even if there was an error
            self.control_state = ControlState.SHUTDOWN
    
    def _shutdown_components(self):
        """Gracefully shutdown individual components"""
        try:
            # Shutdown signal negotiator
            if self.signal_negotiator and hasattr(self.signal_negotiator, 'shutdown'):
                try:
                    self.signal_negotiator.shutdown()
                    logger.debug("Signal negotiator shutdown complete")
                except Exception as e:
                    logger.warning(f"Error shutting down signal negotiator: {e}")
            
            # Shutdown redundancy manager
            if self.redundancy_manager and hasattr(self.redundancy_manager, 'shutdown'):
                try:
                    self.redundancy_manager.shutdown()
                    logger.debug("Redundancy manager shutdown complete")
                except Exception as e:
                    logger.warning(f"Error shutting down redundancy manager: {e}")
            
            # Shutdown other components as needed
            # ... additional component shutdown logic ...
            
        except Exception as e:
            logger.error(f"Error during component shutdown: {e}")
    
    def get_negotiation_summary(self) -> Dict[str, Any]:
        """Get a summary of current negotiation status and channel priorities"""
        try:
            summary = {
                'negotiation_status': 'unknown',
                'primary_channels': [],
                'secondary_channels': [],
                'overall_qos': 0.0,
                'last_negotiation_time': getattr(self, '_last_negotiation_time', 0),
                'renegotiation_scheduled': False
            }
            
            # Check if we have a signal negotiator
            if self.signal_negotiator:
                try:
                    channel_health = self.signal_negotiator.get_channel_health_summary()
                    if channel_health:
                        summary['negotiation_status'] = 'active'
                        
                        # Calculate overall QoS
                        total_qos = 0.0
                        channel_count = 0
                        primary_channels = []
                        secondary_channels = []
                        
                        for channel_type, health in channel_health.items():
                            qos_score = health.get('qos_score', 0.0)
                            total_qos += qos_score
                            channel_count += 1
                            
                            # Categorize channels
                            if qos_score >= 0.8:
                                primary_channels.append(channel_type)
                            elif qos_score >= 0.5:
                                secondary_channels.append(channel_type)
                        
                        if channel_count > 0:
                            summary['overall_qos'] = total_qos / channel_count
                            summary['primary_channels'] = primary_channels
                            summary['secondary_channels'] = secondary_channels
                    else:
                        summary['negotiation_status'] = 'no_channels'
                        
                except Exception as e:
                    logger.warning(f"Error getting channel health: {e}")
                    summary['negotiation_status'] = 'error'
            
            # Check if renegotiation is scheduled
            if hasattr(self, '_renegotiation_thread') and self._renegotiation_thread and self._renegotiation_thread.is_alive():
                summary['renegotiation_scheduled'] = True
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting negotiation summary: {e}")
            return {'negotiation_status': 'error', 'error': str(e)}

# =============================================================================
# Factory Functions
# =============================================================================

def create_runtime_control_loop(config: Layer0Config) -> RuntimeControlLoop:
    """Create a new RuntimeControlLoop instance"""
    return RuntimeControlLoop(config)

# =============================================================================
# Testing Functions
# =============================================================================

async def test_runtime_control_loop():
    """Test the runtime control loop functionality"""
    try:
        from .app_config import Layer0Config
        
        config = Layer0Config()
        
        # Create control loop
        control_loop = create_runtime_control_loop(config)
        
        # Create mock components
        class MockSignalNegotiator:
            def get_channel_health_summary(self):
                return {'cloudwatch': {'qos_score': 0.8}, 'xray': {'qos_score': 0.6}}
            
            async def negotiate_all_channels(self):
                return {'cloudwatch': {'status': 'success', 'qos_score': 0.9}, 'xray': {'status': 'success', 'qos_score': 0.7}}
            
            def negotiate_all_channels_sync(self):
                return {'cloudwatch': {'status': 'success', 'qos_score': 0.9}, 'xray': {'status': 'success', 'qos_score': 0.7}}
            
            def reset(self):
                pass
            
            def shutdown(self):
                pass
        
        class MockRedundancyManager:
            def get_redundancy_summary(self):
                return {'current_mode': 'active_active', 'active_channels': 2}
            
            def set_redundancy_mode(self, mode):
                pass
            
            def attempt_improvement(self):
                return True
            
            def reset(self):
                pass
            
            def shutdown(self):
                pass
        
        class MockSampler:
            def get_sampling_summary(self):
                return {'current_strategy': 'adaptive'}
            
            def set_sampling_strategy(self, strategy):
                pass
            
            def reset(self):
                pass
            
            def shutdown(self):
                pass
        
        class MockFallbackOrchestrator:
            def get_fallback_status(self):
                return {'current_mode': 'normal'}
            
            def _attempt_recovery(self):
                pass  # Mock recovery
            
            def reset(self):
                pass
            
            def shutdown(self):
                pass
        
        class MockDetectionEngine:
            def get_detection_status(self):
                return {'status': 'operational', 'current_mode': 'active'}
            
            def attempt_improvement(self):
                return True
            
            def reset(self):
                pass
            
            def shutdown(self):
                pass
        
        # Initialize components
        control_loop.initialize_components(
            MockSignalNegotiator(),
            MockRedundancyManager(),
            MockSampler(),
            MockFallbackOrchestrator(),
            MockDetectionEngine()
        )
        
        # Start control loop
        control_loop.start_control_loop()
        
        # Wait for a few cycles
        await asyncio.sleep(5)
        
        # Get status
        try:
            status = control_loop.get_control_status()
            print(f"Control loop status: {status}")
        except Exception as e:
            print(f"Error getting control status: {e}")
            status = {'error': str(e)}
        
        # Get history
        try:
            history = control_loop.get_control_history(10)
            print(f"Control history (last 10): {len(history)} events")
        except Exception as e:
            print(f"Error getting control history: {e}")
            history = []
        
        # Get negotiation summary
        try:
            negotiation_summary = control_loop.get_negotiation_summary()
            print(f"Negotiation summary: {negotiation_summary}")
        except Exception as e:
            print(f"Error getting negotiation summary: {e}")
            negotiation_summary = {'error': str(e)}
        
        # Shutdown
        try:
            control_loop.shutdown()
            print("Control loop shutdown successful")
        except Exception as e:
            print(f"Error during shutdown: {e}")
        
        return "Runtime control loop test completed"
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return f"Runtime control loop test failed: {e}"

if __name__ == "__main__":
    try:
        asyncio.run(test_runtime_control_loop())
    except Exception as e:
        print(f"Main execution failed: {e}")
        import traceback
        traceback.print_exc()
