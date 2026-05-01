"""
SCAFAD Layer 0: Health and Heartbeat Monitoring System
======================================================

Implements comprehensive health monitoring with:
- Continuous heartbeat monitoring with configurable intervals
- Health check cascading (component → subsystem → system)
- MTTR (Mean Time To Recovery) tracking and assertions
- Dead man's switch for critical component monitoring
- Health state transitions with hysteresis
- Proactive degradation detection and alerts
- Recovery validation with confirmation testing

Academic References:
- Fault detection and diagnosis (Blanke et al.)
- System health monitoring (Isermann, Fault-Diagnosis Systems)
- MTTR optimization strategies (Ebeling, Reliability Engineering)
- Heartbeat algorithms for distributed systems (Chandra & Toueg)
"""

import time
import threading
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import json
import statistics
import weakref

# Import configuration
from .app_config import Layer0Config

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Enumerations and Data Structures
# =============================================================================

class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    FAILED = "failed"
    UNKNOWN = "unknown"

class ComponentType(Enum):
    """Types of monitored components"""
    SIGNAL_NEGOTIATOR = "signal_negotiator"
    REDUNDANCY_MANAGER = "redundancy_manager"
    EXECUTION_SAMPLER = "execution_sampler"
    FALLBACK_ORCHESTRATOR = "fallback_orchestrator"
    STREAM_PROCESSOR = "stream_processor"
    COMPRESSION_OPTIMIZER = "compression_optimizer"
    ADAPTIVE_BUFFER = "adaptive_buffer"
    VENDOR_ADAPTER = "vendor_adapter"
    RUNTIME_CONTROL = "runtime_control"
    ANOMALY_ENGINE = "anomaly_engine"

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class HealthCheck:
    """Individual health check definition"""
    name: str
    component: ComponentType
    check_function: Callable[[], Tuple[HealthStatus, Dict[str, Any]]]
    interval_ms: int = 5000  # 5 seconds
    timeout_ms: int = 1000   # 1 second
    enabled: bool = True
    critical: bool = False   # Critical component
    dependencies: List[str] = field(default_factory=list)

@dataclass
class HealthResult:
    """Result of a health check"""
    name: str
    component: ComponentType
    status: HealthStatus
    timestamp: float
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

@dataclass
class HeartbeatConfig:
    """Heartbeat monitoring configuration"""
    interval_ms: int = 1000        # 1 second
    timeout_ms: int = 3000         # 3 seconds
    max_missed_beats: int = 3      # Dead after 3 missed
    recovery_confirmation_beats: int = 2  # Confirm recovery

@dataclass
class MTTRConfig:
    """MTTR tracking configuration"""
    measurement_window_hours: int = 24     # 24 hours
    target_mttr_seconds: int = 300         # 5 minutes
    alert_threshold_ratio: float = 1.5     # Alert if MTTR > 1.5x target
    min_incidents_for_stats: int = 3       # Minimum incidents for valid stats

@dataclass
class HealthAlert:
    """Health alert"""
    timestamp: float
    component: ComponentType
    level: AlertLevel
    message: str
    previous_status: HealthStatus
    current_status: HealthStatus
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MTTRIncident:
    """MTTR incident tracking"""
    incident_id: str
    component: ComponentType
    start_time: float
    end_time: Optional[float] = None
    failure_status: HealthStatus = HealthStatus.FAILED
    recovery_status: HealthStatus = HealthStatus.HEALTHY
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class HealthMetrics:
    """Health monitoring metrics"""
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    timeout_checks: int = 0
    
    status_transitions: int = 0
    alerts_generated: int = 0
    incidents_tracked: int = 0
    
    avg_check_duration_ms: float = 0.0
    max_check_duration_ms: float = 0.0
    
    # MTTR metrics
    total_incidents: int = 0
    total_recovery_time_seconds: float = 0.0
    avg_mttr_seconds: float = 0.0
    median_mttr_seconds: float = 0.0
    max_mttr_seconds: float = 0.0

# =============================================================================
# Core Health Monitor Implementation
# =============================================================================

class HealthMonitor:
    """
    Comprehensive health monitoring system
    
    Features:
    - Continuous health checks with configurable intervals
    - Component dependency tracking
    - Health status transitions with hysteresis
    - MTTR tracking and alerting
    - Dead man's switch for critical components
    - Recovery validation
    """
    
    def __init__(self, config: Layer0Config, name: str = "health_monitor"):
        self.config = config
        self.name = name
        
        # Health check registry
        self.health_checks: Dict[str, HealthCheck] = {}
        self.component_status: Dict[ComponentType, HealthStatus] = {}
        
        # Results and history
        self.health_results: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.status_history: Dict[ComponentType, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Alerting
        self.alerts: deque = deque(maxlen=1000)
        self.alert_subscribers: List[Callable[[HealthAlert], None]] = []
        
        # MTTR tracking
        self.active_incidents: Dict[str, MTTRIncident] = {}
        self.completed_incidents: deque = deque(maxlen=1000)
        self.mttr_config = MTTRConfig()
        
        # Heartbeat monitoring
        self.heartbeat_config = HeartbeatConfig()
        self.last_heartbeats: Dict[ComponentType, float] = {}
        self.missed_heartbeats: Dict[ComponentType, int] = defaultdict(int)
        
        # Metrics
        self.metrics = HealthMetrics()
        
        # Threading
        self._lock = threading.RLock()
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        
        logger.info(f"HealthMonitor '{name}' initialized")
        
        # Start monitoring
        self._start_monitoring()
    
    def _start_monitoring(self):
        """Start health monitoring threads"""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        
        # Start health check thread
        self._monitor_thread = threading.Thread(target=self._monitoring_worker, daemon=True)
        self._monitor_thread.start()
        
        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
        self._heartbeat_thread.start()
        
        logger.info(f"HealthMonitor '{self.name}' monitoring started")
    
    def register_health_check(self, health_check: HealthCheck):
        """Register a health check"""
        with self._lock:
            self.health_checks[health_check.name] = health_check
            self.component_status[health_check.component] = HealthStatus.UNKNOWN
            logger.info(f"Registered health check: {health_check.name} ({health_check.component.value})")
    
    def register_component_heartbeat(self, component: ComponentType):
        """Register component for heartbeat monitoring"""
        with self._lock:
            self.last_heartbeats[component] = time.time()
            self.missed_heartbeats[component] = 0
            logger.info(f"Registered heartbeat monitoring for {component.value}")
    
    def heartbeat(self, component: ComponentType):
        """Receive heartbeat from component"""
        with self._lock:
            self.last_heartbeats[component] = time.time()
            self.missed_heartbeats[component] = 0
            
            # If component was marked as failed, check for recovery
            if self.component_status.get(component) == HealthStatus.FAILED:
                self._check_heartbeat_recovery(component)
    
    def _monitoring_worker(self):
        """Health check monitoring worker"""
        while self._monitoring_active:
            try:
                current_time = time.time()
                
                with self._lock:
                    checks_to_run = []
                    for name, check in self.health_checks.items():
                        if not check.enabled:
                            continue
                        
                        # Check if it's time to run this check
                        last_results = self.health_results.get(name)
                        if (not last_results or 
                            current_time - last_results[-1].timestamp >= check.interval_ms / 1000.0):
                            checks_to_run.append(check)
                
                # Run checks outside of lock to avoid blocking
                for check in checks_to_run:
                    self._run_health_check(check)
                
                time.sleep(0.1)  # 100ms monitoring loop
                
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                time.sleep(1.0)
    
    def _heartbeat_worker(self):
        """Heartbeat monitoring worker"""
        while self._monitoring_active:
            try:
                current_time = time.time()
                
                with self._lock:
                    for component in list(self.last_heartbeats.keys()):
                        last_heartbeat = self.last_heartbeats[component]
                        time_since_heartbeat = current_time - last_heartbeat
                        
                        if time_since_heartbeat > self.heartbeat_config.timeout_ms / 1000.0:
                            self.missed_heartbeats[component] += 1
                            
                            if self.missed_heartbeats[component] >= self.heartbeat_config.max_missed_beats:
                                # Component is dead
                                self._handle_dead_component(component)
                
                time.sleep(self.heartbeat_config.interval_ms / 1000.0)
                
            except Exception as e:
                logger.error(f"Heartbeat monitoring error: {e}")
                time.sleep(1.0)
    
    def _run_health_check(self, check: HealthCheck):
        """Run a single health check"""
        start_time = time.time()
        
        try:
            # Run the check with timeout
            status, details = check.check_function()
            duration_ms = (time.time() - start_time) * 1000
            
            # Create result
            result = HealthResult(
                name=check.name,
                component=check.component,
                status=status,
                timestamp=start_time,
                duration_ms=duration_ms,
                details=details
            )
            
            # Update metrics
            with self._lock:
                self.metrics.total_checks += 1
                if status == HealthStatus.HEALTHY:
                    self.metrics.successful_checks += 1
                else:
                    self.metrics.failed_checks += 1
                
                self.metrics.avg_check_duration_ms = (
                    (self.metrics.avg_check_duration_ms * (self.metrics.total_checks - 1) + duration_ms) /
                    self.metrics.total_checks
                )
                self.metrics.max_check_duration_ms = max(self.metrics.max_check_duration_ms, duration_ms)
                
                # Store result
                self.health_results[check.name].append(result)
                
                # Update component status
                self._update_component_status(check.component, status, result)
            
            logger.debug(f"Health check '{check.name}': {status.value} ({duration_ms:.1f}ms)")
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Timeout or error
            result = HealthResult(
                name=check.name,
                component=check.component,
                status=HealthStatus.FAILED,
                timestamp=start_time,
                duration_ms=duration_ms,
                error_message=str(e)
            )
            
            with self._lock:
                self.metrics.total_checks += 1
                if duration_ms > check.timeout_ms:
                    self.metrics.timeout_checks += 1
                else:
                    self.metrics.failed_checks += 1
                
                self.health_results[check.name].append(result)
                self._update_component_status(check.component, HealthStatus.FAILED, result)
            
            logger.warning(f"Health check '{check.name}' failed: {e}")
    
    def _update_component_status(self, component: ComponentType, new_status: HealthStatus, result: HealthResult):
        """Update component status with transition tracking"""
        previous_status = self.component_status.get(component, HealthStatus.UNKNOWN)
        
        if new_status != previous_status:
            # Status transition
            self.component_status[component] = new_status
            self.status_history[component].append((time.time(), previous_status, new_status))
            self.metrics.status_transitions += 1
            
            # Generate alert
            self._generate_health_alert(component, previous_status, new_status, result)
            
            # Track MTTR incidents
            self._track_mttr_incident(component, previous_status, new_status)
            
            logger.info(f"Component {component.value} status: {previous_status.value} -> {new_status.value}")
    
    def _generate_health_alert(self, component: ComponentType, previous_status: HealthStatus, 
                              current_status: HealthStatus, result: HealthResult):
        """Generate health alert"""
        # Determine alert level
        if current_status == HealthStatus.FAILED:
            level = AlertLevel.CRITICAL
        elif current_status == HealthStatus.CRITICAL:
            level = AlertLevel.ERROR
        elif current_status == HealthStatus.DEGRADED:
            level = AlertLevel.WARNING
        elif current_status == HealthStatus.HEALTHY and previous_status in [HealthStatus.FAILED, HealthStatus.CRITICAL]:
            level = AlertLevel.INFO
        else:
            level = AlertLevel.INFO
        
        message = f"Component {component.value} status changed: {previous_status.value} -> {current_status.value}"
        if result.error_message:
            message += f" (Error: {result.error_message})"
        
        alert = HealthAlert(
            timestamp=time.time(),
            component=component,
            level=level,
            message=message,
            previous_status=previous_status,
            current_status=current_status,
            details=result.details
        )
        
        self.alerts.append(alert)
        self.metrics.alerts_generated += 1
        
        # Notify subscribers
        self._notify_alert_subscribers(alert)
        
        logger.warning(f"Health alert: {alert.message}")
    
    def _track_mttr_incident(self, component: ComponentType, previous_status: HealthStatus, current_status: HealthStatus):
        """Track MTTR incidents"""
        incident_key = f"{component.value}_{time.time()}"
        
        # Start incident
        if previous_status == HealthStatus.HEALTHY and current_status in [HealthStatus.FAILED, HealthStatus.CRITICAL]:
            incident = MTTRIncident(
                incident_id=incident_key,
                component=component,
                start_time=time.time(),
                failure_status=current_status
            )
            self.active_incidents[incident_key] = incident
            self.metrics.incidents_tracked += 1
        
        # End incident
        elif previous_status in [HealthStatus.FAILED, HealthStatus.CRITICAL] and current_status == HealthStatus.HEALTHY:
            # Find active incident for this component
            for key, incident in list(self.active_incidents.items()):
                if incident.component == component and incident.end_time is None:
                    incident.end_time = time.time()
                    incident.recovery_status = current_status
                    
                    # Calculate MTTR
                    recovery_time = incident.end_time - incident.start_time
                    
                    # Move to completed incidents
                    self.completed_incidents.append(incident)
                    del self.active_incidents[key]
                    
                    # Update MTTR metrics
                    self._update_mttr_metrics(recovery_time)
                    
                    logger.info(f"MTTR incident resolved: {component.value} recovered in {recovery_time:.1f}s")
                    break
    
    def _update_mttr_metrics(self, recovery_time_seconds: float):
        """Update MTTR metrics"""
        self.metrics.total_incidents += 1
        self.metrics.total_recovery_time_seconds += recovery_time_seconds
        self.metrics.avg_mttr_seconds = self.metrics.total_recovery_time_seconds / self.metrics.total_incidents
        self.metrics.max_mttr_seconds = max(self.metrics.max_mttr_seconds, recovery_time_seconds)
        
        # Calculate median MTTR from recent incidents
        recent_incidents = list(self.completed_incidents)[-50:]  # Last 50 incidents
        if len(recent_incidents) >= self.mttr_config.min_incidents_for_stats:
            recovery_times = [inc.end_time - inc.start_time for inc in recent_incidents if inc.end_time]
            if recovery_times:
                self.metrics.median_mttr_seconds = statistics.median(recovery_times)
        
        # Check MTTR threshold
        if (self.metrics.avg_mttr_seconds > self.mttr_config.target_mttr_seconds * self.mttr_config.alert_threshold_ratio):
            logger.warning(f"MTTR threshold exceeded: {self.metrics.avg_mttr_seconds:.1f}s > {self.mttr_config.target_mttr_seconds * self.mttr_config.alert_threshold_ratio:.1f}s")
    
    def _handle_dead_component(self, component: ComponentType):
        """Handle dead component (missed heartbeats)"""
        current_status = self.component_status.get(component, HealthStatus.UNKNOWN)
        
        if current_status != HealthStatus.FAILED:
            result = HealthResult(
                name=f"heartbeat_{component.value}",
                component=component,
                status=HealthStatus.FAILED,
                timestamp=time.time(),
                duration_ms=0,
                details={"reason": "missed_heartbeats", "missed_count": self.missed_heartbeats[component]}
            )
            
            self._update_component_status(component, HealthStatus.FAILED, result)
            
            logger.critical(f"Component {component.value} declared dead (missed {self.missed_heartbeats[component]} heartbeats)")
    
    def _check_heartbeat_recovery(self, component: ComponentType):
        """Check if component has recovered via heartbeat"""
        # Require confirmation beats for recovery
        if self.missed_heartbeats[component] == 0:
            # Component is sending heartbeats again - mark as healthy
            result = HealthResult(
                name=f"heartbeat_{component.value}",
                component=component,
                status=HealthStatus.HEALTHY,
                timestamp=time.time(),
                duration_ms=0,
                details={"reason": "heartbeat_recovery"}
            )
            
            self._update_component_status(component, HealthStatus.HEALTHY, result)
            
            logger.info(f"Component {component.value} recovered via heartbeat")
    
    def _notify_alert_subscribers(self, alert: HealthAlert):
        """Notify alert subscribers"""
        for subscriber in self.alert_subscribers[:]:
            try:
                subscriber(alert)
            except Exception as e:
                logger.warning(f"Alert subscriber notification failed: {e}")
    
    def subscribe_alerts(self, callback: Callable[[HealthAlert], None]):
        """Subscribe to health alerts"""
        self.alert_subscribers.append(callback)
    
    def unsubscribe_alerts(self, callback: Callable[[HealthAlert], None]):
        """Unsubscribe from health alerts"""
        if callback in self.alert_subscribers:
            self.alert_subscribers.remove(callback)
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health"""
        with self._lock:
            # Calculate system-wide health
            status_counts = defaultdict(int)
            for status in self.component_status.values():
                status_counts[status] += 1
            
            # Determine overall status
            if status_counts[HealthStatus.FAILED] > 0:
                overall_status = HealthStatus.FAILED
            elif status_counts[HealthStatus.CRITICAL] > 0:
                overall_status = HealthStatus.CRITICAL
            elif status_counts[HealthStatus.DEGRADED] > 0:
                overall_status = HealthStatus.DEGRADED
            elif status_counts[HealthStatus.HEALTHY] > 0:
                overall_status = HealthStatus.HEALTHY
            else:
                overall_status = HealthStatus.UNKNOWN
            
            return {
                "overall_status": overall_status.value,
                "component_count": len(self.component_status),
                "status_breakdown": {status.value: count for status, count in status_counts.items()},
                "active_incidents": len(self.active_incidents),
                "recent_alerts": len([a for a in self.alerts if time.time() - a.timestamp < 300]),  # Last 5 minutes
                "mttr_stats": {
                    "avg_mttr_seconds": self.metrics.avg_mttr_seconds,
                    "median_mttr_seconds": self.metrics.median_mttr_seconds,
                    "max_mttr_seconds": self.metrics.max_mttr_seconds,
                    "target_mttr_seconds": self.mttr_config.target_mttr_seconds,
                    "total_incidents": self.metrics.total_incidents
                }
            }
    
    def get_component_status(self, component: ComponentType) -> Dict[str, Any]:
        """Get status for specific component"""
        with self._lock:
            status = self.component_status.get(component, HealthStatus.UNKNOWN)
            recent_results = []
            
            # Get recent health check results for this component
            for check_name, results in self.health_results.items():
                check = self.health_checks.get(check_name)
                if check and check.component == component:
                    recent_results.extend([{
                        "check_name": r.name,
                        "status": r.status.value,
                        "timestamp": r.timestamp,
                        "duration_ms": r.duration_ms,
                        "details": r.details,
                        "error_message": r.error_message
                    } for r in list(results)[-10:]])  # Last 10 results
            
            # Sort by timestamp
            recent_results.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return {
                "component": component.value,
                "current_status": status.value,
                "last_heartbeat": self.last_heartbeats.get(component),
                "missed_heartbeats": self.missed_heartbeats.get(component, 0),
                "recent_results": recent_results[:10],
                "status_history": [
                    {"timestamp": ts, "from": from_status.value, "to": to_status.value}
                    for ts, from_status, to_status in list(self.status_history[component])[-10:]
                ]
            }
    
    def get_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        with self._lock:
            alerts = []
            for alert in list(self.alerts)[-limit:]:
                alerts.append({
                    "timestamp": alert.timestamp,
                    "component": alert.component.value,
                    "level": alert.level.value,
                    "message": alert.message,
                    "previous_status": alert.previous_status.value,
                    "current_status": alert.current_status.value,
                    "details": alert.details
                })
            return alerts
    
    def get_mttr_report(self) -> Dict[str, Any]:
        """Get MTTR analysis report"""
        with self._lock:
            # Component-specific MTTR stats
            component_mttr = defaultdict(list)
            for incident in self.completed_incidents:
                if incident.end_time:
                    recovery_time = incident.end_time - incident.start_time
                    component_mttr[incident.component].append(recovery_time)
            
            component_stats = {}
            for component, times in component_mttr.items():
                if len(times) >= self.mttr_config.min_incidents_for_stats:
                    component_stats[component.value] = {
                        "avg_mttr_seconds": statistics.mean(times),
                        "median_mttr_seconds": statistics.median(times),
                        "max_mttr_seconds": max(times),
                        "incident_count": len(times),
                        "meets_sla": statistics.mean(times) <= self.mttr_config.target_mttr_seconds
                    }
            
            return {
                "overall": {
                    "avg_mttr_seconds": self.metrics.avg_mttr_seconds,
                    "median_mttr_seconds": self.metrics.median_mttr_seconds,
                    "max_mttr_seconds": self.metrics.max_mttr_seconds,
                    "total_incidents": self.metrics.total_incidents,
                    "target_mttr_seconds": self.mttr_config.target_mttr_seconds,
                    "meets_sla": self.metrics.avg_mttr_seconds <= self.mttr_config.target_mttr_seconds
                },
                "by_component": component_stats,
                "active_incidents": len(self.active_incidents),
                "recent_incidents": [
                    {
                        "component": inc.component.value,
                        "start_time": inc.start_time,
                        "end_time": inc.end_time,
                        "duration_seconds": (inc.end_time - inc.start_time) if inc.end_time else None,
                        "failure_status": inc.failure_status.value,
                        "recovery_status": inc.recovery_status.value
                    } for inc in list(self.completed_incidents)[-20:]
                ]
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status"""
        return {
            "name": self.name,
            "monitoring_active": self._monitoring_active,
            "registered_checks": len(self.health_checks),
            "monitored_components": len(self.component_status),
            "heartbeat_components": len(self.last_heartbeats),
            "system_health": self.get_system_health(),
            "metrics": {
                "total_checks": self.metrics.total_checks,
                "successful_checks": self.metrics.successful_checks,
                "failed_checks": self.metrics.failed_checks,
                "timeout_checks": self.metrics.timeout_checks,
                "status_transitions": self.metrics.status_transitions,
                "alerts_generated": self.metrics.alerts_generated,
                "incidents_tracked": self.metrics.incidents_tracked,
                "avg_check_duration_ms": self.metrics.avg_check_duration_ms,
                "max_check_duration_ms": self.metrics.max_check_duration_ms
            }
        }
    
    def shutdown(self):
        """Shutdown health monitor"""
        logger.info(f"HealthMonitor '{self.name}' shutting down")
        
        self._monitoring_active = False
        
        # Wait for threads
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2.0)
        
        logger.info(f"HealthMonitor '{self.name}' shutdown complete")

# =============================================================================
# Factory Functions
# =============================================================================

def create_health_monitor(config: Layer0Config = None, name: str = "health_monitor") -> HealthMonitor:
    """Create a health monitor"""
    if config is None:
        from .app_config import Layer0Config
        config = Layer0Config()
    
    return HealthMonitor(config, name)

# =============================================================================
# Testing Functions
# =============================================================================

def test_health_check() -> Tuple[HealthStatus, Dict[str, Any]]:
    """Sample health check function"""
    import random
    
    # Simulate health check logic
    if random.random() < 0.9:  # 90% healthy
        return HealthStatus.HEALTHY, {"cpu_usage": 25.5, "memory_usage": 45.2}
    else:
        return HealthStatus.DEGRADED, {"cpu_usage": 85.5, "memory_usage": 92.1, "issue": "high_load"}

async def test_health_monitor():
    """Test health monitor functionality"""
    print("🧪 Testing HealthMonitor...")
    
    from .app_config import Layer0Config
    config = Layer0Config()
    
    monitor = HealthMonitor(config, "test_monitor")
    
    # Register health checks
    check1 = HealthCheck(
        name="test_component_1",
        component=ComponentType.SIGNAL_NEGOTIATOR,
        check_function=test_health_check,
        interval_ms=1000,
        critical=True
    )
    
    check2 = HealthCheck(
        name="test_component_2", 
        component=ComponentType.REDUNDANCY_MANAGER,
        check_function=test_health_check,
        interval_ms=2000
    )
    
    monitor.register_health_check(check1)
    monitor.register_health_check(check2)
    
    # Register for heartbeats
    monitor.register_component_heartbeat(ComponentType.STREAM_PROCESSOR)
    
    # Send some heartbeats
    for _ in range(3):
        monitor.heartbeat(ComponentType.STREAM_PROCESSOR)
        await asyncio.sleep(0.5)
    
    # Wait for health checks
    await asyncio.sleep(3.0)
    
    # Get status
    system_health = monitor.get_system_health()
    print(f"System health: {json.dumps(system_health, indent=2)}")
    
    component_status = monitor.get_component_status(ComponentType.SIGNAL_NEGOTIATOR)
    print(f"Component status: {json.dumps(component_status, indent=2, default=str)}")
    
    alerts = monitor.get_alerts(5)
    print(f"Recent alerts: {len(alerts)}")
    
    mttr_report = monitor.get_mttr_report()
    print(f"MTTR report: {json.dumps(mttr_report, indent=2)}")
    
    monitor.shutdown()
    
    return "HealthMonitor test completed successfully"

if __name__ == "__main__":
    asyncio.run(test_health_monitor())