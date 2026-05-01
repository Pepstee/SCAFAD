#!/usr/bin/env python3
"""
SCAFAD Layer 1: Audit Trail Generator Subsystem
==============================================

The Audit Trail Generator creates comprehensive audit trails for all processing
operations in Layer 1's behavioral intake zone. It provides:

- Processing audit trail generation
- Compliance audit logging
- Performance audit tracking
- Security audit recording
- Audit trail persistence and retrieval
- Audit trail analysis and reporting

Author: SCAFAD Research Team
Institution: Birmingham Newman University
License: MIT
Version: 1.0.0
"""

import json
import logging
import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from enum import Enum, auto
from datetime import datetime, timezone, timedelta
import copy
from collections import defaultdict, deque
import uuid

# =============================================================================
# Audit Trail Data Models
# =============================================================================

class AuditLevel(Enum):
    """Audit logging levels"""
    DEBUG = "debug"                 # Detailed debugging information
    INFO = "info"                   # General information
    WARNING = "warning"             # Warning messages
    ERROR = "error"                 # Error messages
    CRITICAL = "critical"           # Critical system events
    SECURITY = "security"           # Security-related events
    COMPLIANCE = "compliance"       # Compliance-related events

class AuditCategory(Enum):
    """Audit event categories"""
    PROCESSING = "processing"       # Data processing events
    VALIDATION = "validation"       # Data validation events
    PRIVACY = "privacy"            # Privacy-related events
    SECURITY = "security"          # Security events
    SCHEMA = "schema"              # Schema-related events
    PERFORMANCE = "performance"    # Performance events
    SYSTEM = "system"              # System events
    USER = "user"                  # User action events

class AuditAction(Enum):
    """Audit action types"""
    CREATE = "create"               # Resource creation
    READ = "read"                   # Resource access
    UPDATE = "update"               # Resource modification
    DELETE = "delete"               # Resource deletion
    VALIDATE = "validate"           # Data validation
    PROCESS = "process"             # Data processing
    TRANSFORM = "transform"         # Data transformation
    MIGRATE = "migrate"            # Data migration
    REDACT = "redact"              # Data redaction
    HASH = "hash"                  # Data hashing
    ANALYZE = "analyze"            # Data analysis
    MONITOR = "monitor"            # System monitoring

@dataclass
class AuditEvent:
    """Individual audit event"""
    event_id: str
    timestamp: datetime
    level: AuditLevel
    category: AuditCategory
    action: AuditAction
    component: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    record_id: Optional[str] = None
    batch_id: Optional[str] = None
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    outcome: str = "success"
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Post-initialization validation"""
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)
        
        if not isinstance(self.level, AuditLevel):
            self.level = AuditLevel(self.level)
        
        if not isinstance(self.category, AuditCategory):
            self.category = AuditCategory(self.category)
        
        if not isinstance(self.action, AuditAction):
            self.action = AuditAction(self.action)

@dataclass
class ProcessingAudit:
    """Complete processing audit trail"""
    audit_id: str = ""
    batch_id: str = ""
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    total_records: int = 0
    processed_records: int = 0
    failed_records: int = 0
    processing_phases: List[str] = field(default_factory=list)
    phase_audits: Dict[str, List[AuditEvent]] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    compliance_status: Dict[str, bool] = field(default_factory=dict)
    security_events: List[AuditEvent] = field(default_factory=list)
    privacy_events: List[AuditEvent] = field(default_factory=list)
    error_summary: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Extra fields used by layer1_core.py
    processing_status: Any = None
    error_details: Optional[str] = None
    phases_completed: List[str] = field(default_factory=list)
    timestamp: str = ""
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class AuditSummary:
    """Audit trail summary statistics"""
    total_events: int
    events_by_level: Dict[AuditLevel, int]
    events_by_category: Dict[AuditCategory, int]
    events_by_action: Dict[AuditAction, int]
    events_by_component: Dict[str, int]
    time_range: Tuple[datetime, datetime]
    error_count: int
    warning_count: int
    security_event_count: int
    compliance_event_count: int
    average_event_duration_ms: float
    metadata: Optional[Dict[str, Any]] = None

# =============================================================================
# Audit Trail Generator Core Class
# =============================================================================

class AuditTrailGenerator:
    """
    Audit Trail Generator for comprehensive logging and tracking
    
    The Audit Trail Generator provides comprehensive audit trail generation
    for all operations in Layer 1's processing pipeline.
    """
    
    def __init__(self, config: Any = None):
        """Initialize the Audit Trail Generator"""
        self.config = config
        self.logger = logging.getLogger("SCAFAD.Layer1.AuditTrailGenerator")
        
        # Audit event storage
        self.audit_events: List[AuditEvent] = []
        self.audit_trails: Dict[str, ProcessingAudit] = {}
        
        # Audit configuration
        self.audit_config = {
            'retention_days': 90,
            'max_events_per_trail': 10000,
            'enable_performance_tracking': True,
            'enable_compliance_tracking': True,
            'enable_security_tracking': True,
            'enable_privacy_tracking': True
        }
        
        # Performance tracking
        self.generator_stats = {
            'total_events_generated': 0,
            'total_audit_trails': 0,
            'average_event_generation_time_ms': 0.0,
            'total_storage_bytes': 0
        }
        
        # Initialize audit configuration
        if config and hasattr(config, 'audit_config'):
            self.audit_config.update(config.audit_config)
        
        self.logger.info("Audit Trail Generator initialized")
    
    def log_event(self, level: AuditLevel, category: AuditCategory, action: AuditAction,
                  component: str, description: str = "", details: Optional[Dict[str, Any]] = None,
                  user_id: Optional[str] = None, session_id: Optional[str] = None,
                  record_id: Optional[str] = None, batch_id: Optional[str] = None,
                  outcome: str = "success", duration_ms: Optional[float] = None,
                  error_message: Optional[str] = None) -> str:
        """
        Log an audit event
        
        Args:
            level: Audit level
            category: Event category
            action: Action performed
            component: Component that generated the event
            description: Event description
            details: Additional event details
            user_id: User ID (if applicable)
            session_id: Session ID (if applicable)
            record_id: Record ID (if applicable)
            batch_id: Batch ID (if applicable)
            outcome: Event outcome
            duration_ms: Event duration in milliseconds
            error_message: Error message (if applicable)
            
        Returns:
            Event ID of the generated audit event
        """
        try:
            # Create audit event
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                level=level,
                category=category,
                action=action,
                component=component,
                user_id=user_id,
                session_id=session_id,
                record_id=record_id,
                batch_id=batch_id,
                description=description,
                details=details or {},
                outcome=outcome,
                duration_ms=duration_ms,
                error_message=error_message,
                metadata={
                    'generator_version': '1.0.0',
                    'config_hash': self._get_config_hash()
                }
            )
            
            # Add to audit events
            self.audit_events.append(event)
            
            # Update statistics
            self._update_generator_stats(event)
            
            # Log to system logger
            self._log_to_system_logger(event)
            
            self.logger.debug(f"Audit event logged: {event.event_id}")
            return event.event_id
            
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {str(e)}")
            raise
    
    def start_processing_audit(self, batch_id: str, total_records: int,
                              processing_phases: List[str]) -> str:
        """
        Start a new processing audit trail
        
        Args:
            batch_id: Unique batch identifier
            total_records: Total number of records in batch
            processing_phases: List of processing phases
            
        Returns:
            Audit ID for the new audit trail
        """
        try:
            audit_id = str(uuid.uuid4())
            
            # Create processing audit
            audit = ProcessingAudit(
                audit_id=audit_id,
                batch_id=batch_id,
                start_time=datetime.now(timezone.utc),
                end_time=None,
                total_records=total_records,
                processed_records=0,
                failed_records=0,
                processing_phases=processing_phases,
                phase_audits={phase: [] for phase in processing_phases},
                performance_metrics={},
                compliance_status={},
                security_events=[],
                privacy_events=[],
                error_summary=[],
                warnings=[],
                metadata={
                    'generator_version': '1.0.0',
                    'config_hash': self._get_config_hash()
                }
            )
            
            # Store audit trail
            self.audit_trails[audit_id] = audit
            
            # Update statistics
            self.generator_stats['total_audit_trails'] += 1
            
            self.logger.info(f"Processing audit started: {audit_id} for batch {batch_id}")
            return audit_id
            
        except Exception as e:
            self.logger.error(f"Failed to start processing audit: {str(e)}")
            raise
    
    def log_phase_event(self, audit_id: str, phase: str, level: AuditLevel,
                       category: AuditCategory, action: AuditAction, component: str,
                       description: str = "", details: Optional[Dict[str, Any]] = None,
                       record_id: Optional[str] = None, outcome: str = "success",
                       duration_ms: Optional[float] = None, error_message: Optional[str] = None):
        """
        Log an event for a specific processing phase
        
        Args:
            audit_id: Audit trail ID
            phase: Processing phase
            level: Audit level
            category: Event category
            action: Action performed
            component: Component that generated the event
            description: Event description
            details: Additional event details
            record_id: Record ID (if applicable)
            outcome: Event outcome
            duration_ms: Event duration in milliseconds
            error_message: Error message (if applicable)
        """
        try:
            if audit_id not in self.audit_trails:
                self.logger.warning(f"Audit trail {audit_id} not found")
                return
            
            audit = self.audit_trails[audit_id]
            
            # Create audit event
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                level=level,
                category=category,
                action=action,
                component=component,
                record_id=record_id,
                batch_id=audit.batch_id,
                description=description,
                details=details or {},
                outcome=outcome,
                duration_ms=duration_ms,
                error_message=error_message
            )
            
            # Add to phase audits
            if phase in audit.phase_audits:
                audit.phase_audits[phase].append(event)
            else:
                audit.phase_audits[phase] = [event]
            
            # Update audit statistics
            self._update_audit_statistics(audit, event)
            
            # Add to main audit events
            self.audit_events.append(event)
            
            # Update generator statistics
            self._update_generator_stats(event)
            
            self.logger.debug(f"Phase event logged for {audit_id}, phase {phase}")
            
        except Exception as e:
            self.logger.error(f"Failed to log phase event: {str(e)}")
            raise
    
    def complete_processing_audit(self, audit_id: str, processed_records: int,
                                 failed_records: int, performance_metrics: Optional[Dict[str, float]] = None,
                                 compliance_status: Optional[Dict[str, bool]] = None,
                                 error_summary: Optional[List[str]] = None,
                                 warnings: Optional[List[str]] = None):
        """
        Complete a processing audit trail
        
        Args:
            audit_id: Audit trail ID
            processed_records: Number of successfully processed records
            failed_records: Number of failed records
            performance_metrics: Performance metrics
            compliance_status: Compliance status for various aspects
            error_summary: Summary of errors encountered
            warnings: List of warnings
        """
        try:
            if audit_id not in self.audit_trails:
                self.logger.warning(f"Audit trail {audit_id} not found")
                return
            
            audit = self.audit_trails[audit_id]
            
            # Update audit completion
            audit.end_time = datetime.now(timezone.utc)
            audit.processed_records = processed_records
            audit.failed_records = failed_records
            
            if performance_metrics:
                audit.performance_metrics.update(performance_metrics)
            
            if compliance_status:
                audit.compliance_status.update(compliance_status)
            
            if error_summary:
                audit.error_summary.extend(error_summary)
            
            if warnings:
                audit.warnings.extend(warnings)
            
            # Calculate final statistics
            self._calculate_final_audit_statistics(audit)
            
            # Generate audit summary
            summary = self._generate_audit_summary(audit)
            
            self.logger.info(f"Processing audit completed: {audit_id}")
            self.logger.info(f"Audit summary: {summary.total_events} events, "
                           f"{summary.error_count} errors, {summary.warning_count} warnings")
            
        except Exception as e:
            self.logger.error(f"Failed to complete processing audit: {str(e)}")
            raise
    
    def get_audit_trail(self, audit_id: str) -> Optional[ProcessingAudit]:
        """
        Retrieve a complete audit trail
        
        Args:
            audit_id: Audit trail ID
            
        Returns:
            ProcessingAudit or None if not found
        """
        return self.audit_trails.get(audit_id)
    
    def get_audit_events(self, filters: Optional[Dict[str, Any]] = None,
                         limit: Optional[int] = None) -> List[AuditEvent]:
        """
        Retrieve audit events with optional filtering
        
        Args:
            filters: Optional filters for events
            limit: Maximum number of events to return
            
        Returns:
            List of filtered audit events
        """
        try:
            filtered_events = self.audit_events.copy()
            
            # Apply filters
            if filters:
                filtered_events = self._apply_event_filters(filtered_events, filters)
            
            # Sort by timestamp (newest first)
            filtered_events.sort(key=lambda x: x.timestamp, reverse=True)
            
            # Apply limit
            if limit:
                filtered_events = filtered_events[:limit]
            
            return filtered_events
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve audit events: {str(e)}")
            return []
    
    def get_audit_summary(self, time_range: Optional[Tuple[datetime, datetime]] = None,
                          filters: Optional[Dict[str, Any]] = None) -> AuditSummary:
        """
        Get audit summary statistics
        
        Args:
            time_range: Optional time range for summary
            filters: Optional filters for events
            
        Returns:
            AuditSummary with comprehensive statistics
        """
        try:
            # Get events for summary
            events = self.audit_events.copy()
            
            # Apply time range filter
            if time_range:
                start_time, end_time = time_range
                events = [e for e in events if start_time <= e.timestamp <= end_time]
            
            # Apply additional filters
            if filters:
                events = self._apply_event_filters(events, filters)
            
            if not events:
                return self._create_empty_audit_summary(time_range)
            
            # Calculate statistics
            events_by_level = defaultdict(int)
            events_by_category = defaultdict(int)
            events_by_action = defaultdict(int)
            events_by_component = defaultdict(int)
            
            error_count = 0
            warning_count = 0
            security_event_count = 0
            compliance_event_count = 0
            total_duration = 0.0
            events_with_duration = 0
            
            for event in events:
                events_by_level[event.level] += 1
                events_by_category[event.category] += 1
                events_by_action[event.action] += 1
                events_by_component[event.component] += 1
                
                if event.level == AuditLevel.ERROR:
                    error_count += 1
                elif event.level == AuditLevel.WARNING:
                    warning_count += 1
                
                if event.category == AuditCategory.SECURITY:
                    security_event_count += 1
                elif event.category == AuditCategory.COMPLIANCE:
                    compliance_event_count += 1
                
                if event.duration_ms is not None:
                    total_duration += event.duration_ms
                    events_with_duration += 1
            
            # Calculate averages
            average_duration = total_duration / events_with_duration if events_with_duration > 0 else 0.0
            
            # Determine time range
            if not time_range:
                timestamps = [e.timestamp for e in events]
                time_range = (min(timestamps), max(timestamps))
            
            # Create summary
            summary = AuditSummary(
                total_events=len(events),
                events_by_level=dict(events_by_level),
                events_by_category=dict(events_by_category),
                events_by_action=dict(events_by_action),
                events_by_component=dict(events_by_component),
                time_range=time_range,
                error_count=error_count,
                warning_count=warning_count,
                security_event_count=security_event_count,
                compliance_event_count=compliance_event_count,
                average_event_duration_ms=average_duration,
                metadata={
                    'generation_timestamp': datetime.now(timezone.utc),
                    'filters_applied': filters
                }
            )
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to generate audit summary: {str(e)}")
            raise
    
    def export_audit_trail(self, audit_id: str, format: str = "json") -> Optional[str]:
        """
        Export audit trail in specified format
        
        Args:
            audit_id: Audit trail ID
            format: Export format (json, csv)
            
        Returns:
            Exported audit trail string or None if failed
        """
        try:
            audit = self.audit_trails.get(audit_id)
            if not audit:
                return None
            
            if format.lower() == "json":
                return json.dumps(asdict(audit), indent=2, default=str)
            else:
                self.logger.warning(f"Export format {format} not supported")
                return None
                
        except Exception as e:
            self.logger.error(f"Export failed: {str(e)}")
            return None
    
    def cleanup_old_audits(self, retention_days: Optional[int] = None):
        """
        Clean up old audit trails and events
        
        Args:
            retention_days: Number of days to retain (uses config default if None)
        """
        try:
            if retention_days is None:
                retention_days = self.audit_config['retention_days']
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=retention_days)
            
            # Clean up old audit events
            original_count = len(self.audit_events)
            self.audit_events = [e for e in self.audit_events if e.timestamp >= cutoff_time]
            removed_events = original_count - len(self.audit_events)
            
            # Clean up old audit trails
            original_trails = len(self.audit_trails)
            self.audit_trails = {
                aid: audit for aid, audit in self.audit_trails.items()
                if audit.start_time >= cutoff_time
            }
            removed_trails = original_trails - len(self.audit_trails)
            
            self.logger.info(f"Cleanup completed: removed {removed_events} events, {removed_trails} trails")
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {str(e)}")
    
    def get_generator_stats(self) -> Dict[str, Any]:
        """Get generator statistics"""
        return self.generator_stats.copy()
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _get_config_hash(self) -> str:
        """Generate hash of current configuration"""
        config_str = json.dumps(self.audit_config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]
    
    def _update_generator_stats(self, event: AuditEvent):
        """Update generator statistics with new event"""
        self.generator_stats['total_events_generated'] += 1
        
        # Update average event generation time
        current_avg = self.generator_stats['average_event_generation_time_ms']
        total_events = self.generator_stats['total_events_generated']
        
        if total_events > 0:
            self.generator_stats['average_event_generation_time_ms'] = (
                (current_avg * (total_events - 1) + 0.1) / total_events  # Assume 0.1ms generation time
            )
        
        # Update storage estimate
        event_size = len(json.dumps(asdict(event), default=str))
        self.generator_stats['total_storage_bytes'] += event_size
    
    def _log_to_system_logger(self, event: AuditEvent):
        """Log audit event to system logger"""
        log_message = f"[AUDIT] {event.category.value.upper()}: {event.action.value} - {event.description}"
        
        if event.level == AuditLevel.DEBUG:
            self.logger.debug(log_message)
        elif event.level == AuditLevel.INFO:
            self.logger.info(log_message)
        elif event.level == AuditLevel.WARNING:
            self.logger.warning(log_message)
        elif event.level == AuditLevel.ERROR:
            self.logger.error(log_message)
        elif event.level == AuditLevel.CRITICAL:
            self.logger.critical(log_message)
        elif event.level == AuditLevel.SECURITY:
            self.logger.warning(f"[SECURITY] {log_message}")
        elif event.level == AuditLevel.COMPLIANCE:
            self.logger.info(f"[COMPLIANCE] {log_message}")
    
    def _update_audit_statistics(self, audit: ProcessingAudit, event: AuditEvent):
        """Update audit trail statistics with new event"""
        # Track security and privacy events
        if event.category == AuditCategory.SECURITY:
            audit.security_events.append(event)
        elif event.category == AuditCategory.PRIVACY:
            audit.privacy_events.append(event)
        
        # Track errors and warnings
        if event.level == AuditLevel.ERROR:
            if event.error_message:
                audit.error_summary.append(f"{event.component}: {event.error_message}")
        elif event.level == AuditLevel.WARNING:
            audit.warnings.append(f"{event.component}: {event.description}")
    
    def _calculate_final_audit_statistics(self, audit: ProcessingAudit):
        """Calculate final statistics for completed audit"""
        # Calculate processing success rate
        if audit.total_records > 0:
            success_rate = audit.processed_records / audit.total_records
            audit.performance_metrics['success_rate'] = success_rate
        
        # Calculate total processing time
        if audit.start_time and audit.end_time:
            total_duration = (audit.end_time - audit.start_time).total_seconds() * 1000
            audit.performance_metrics['total_duration_ms'] = total_duration
            
            # Calculate throughput
            if total_duration > 0:
                throughput = audit.processed_records / (total_duration / 1000)
                audit.performance_metrics['throughput_records_per_sec'] = throughput
    
    def _generate_audit_summary(self, audit: ProcessingAudit) -> AuditSummary:
        """Generate summary for a specific audit trail"""
        # Collect all events from the audit
        all_events = []
        for phase_events in audit.phase_audits.values():
            all_events.extend(phase_events)
        
        # Add security and privacy events
        all_events.extend(audit.security_events)
        all_events.extend(audit.privacy_events)
        
        if not all_events:
            return self._create_empty_audit_summary((audit.start_time, audit.end_time))
        
        # Calculate statistics
        events_by_level = defaultdict(int)
        events_by_category = defaultdict(int)
        events_by_action = defaultdict(int)
        events_by_component = defaultdict(int)
        
        error_count = len(audit.error_summary)
        warning_count = len(audit.warnings)
        security_event_count = len(audit.security_events)
        compliance_event_count = len([e for e in all_events if e.category == AuditCategory.COMPLIANCE])
        
        total_duration = 0.0
        events_with_duration = 0
        
        for event in all_events:
            events_by_level[event.level] += 1
            events_by_category[event.category] += 1
            events_by_action[event.action] += 1
            events_by_component[event.component] += 1
            
            if event.duration_ms is not None:
                total_duration += event.duration_ms
                events_with_duration += 1
        
        # Calculate averages
        average_duration = total_duration / events_with_duration if events_with_duration > 0 else 0.0
        
        # Create summary
        summary = AuditSummary(
            total_events=len(all_events),
            events_by_level=dict(events_by_level),
            events_by_category=dict(events_by_category),
            events_by_action=dict(events_by_action),
            events_by_component=dict(events_by_component),
            time_range=(audit.start_time, audit.end_time or datetime.now(timezone.utc)),
            error_count=error_count,
            warning_count=warning_count,
            security_event_count=security_event_count,
            compliance_event_count=compliance_event_count,
            average_event_duration_ms=average_duration,
            metadata={
                'audit_id': audit.audit_id,
                'batch_id': audit.batch_id,
                'generation_timestamp': datetime.now(timezone.utc)
            }
        )
        
        return summary
    
    def _apply_event_filters(self, events: List[AuditEvent], filters: Dict[str, Any]) -> List[AuditEvent]:
        """Apply filters to audit events"""
        filtered_events = events.copy()
        
        for filter_key, filter_value in filters.items():
            if filter_key == 'level' and filter_value:
                filtered_events = [e for e in filtered_events if e.level == filter_value]
            elif filter_key == 'category' and filter_value:
                filtered_events = [e for e in filtered_events if e.category == filter_value]
            elif filter_key == 'action' and filter_value:
                filtered_events = [e for e in filtered_events if e.action == filter_value]
            elif filter_key == 'component' and filter_value:
                filtered_events = [e for e in filtered_events if e.component == filter_value]
            elif filter_key == 'outcome' and filter_value:
                filtered_events = [e for e in filtered_events if e.outcome == filter_value]
            elif filter_key == 'user_id' and filter_value:
                filtered_events = [e for e in filtered_events if e.user_id == filter_value]
            elif filter_key == 'batch_id' and filter_value:
                filtered_events = [e for e in filtered_events if e.batch_id == filter_value]
            elif filter_key == 'record_id' and filter_value:
                filtered_events = [e for e in filtered_events if e.record_id == filter_value]
            elif filter_key == 'start_time' and filter_value:
                filtered_events = [e for e in filtered_events if e.timestamp >= filter_value]
            elif filter_key == 'end_time' and filter_value:
                filtered_events = [e for e in filtered_events if e.timestamp <= filter_value]
        
        return filtered_events
    
    def _create_empty_audit_summary(self, time_range: Optional[Tuple[datetime, datetime]] = None) -> AuditSummary:
        """Create empty audit summary"""
        if not time_range:
            now = datetime.now(timezone.utc)
            time_range = (now, now)
        
        return AuditSummary(
            total_events=0,
            events_by_level={},
            events_by_category={},
            events_by_action={},
            events_by_component={},
            time_range=time_range,
            error_count=0,
            warning_count=0,
            security_event_count=0,
            compliance_event_count=0,
            average_event_duration_ms=0.0,
            metadata={
                'generation_timestamp': datetime.now(timezone.utc),
                'note': 'No events found for specified criteria'
            }
        )

    async def generate_processing_audit(self, processing_summary: dict) -> "ProcessingAudit":
        """Generate a ProcessingAudit from a processing_summary dict (stub)."""
        import datetime as _dt
        batch_id = processing_summary.get('batch_id', '')
        phases = [p.get('phase', str(p)) if isinstance(p, dict) else str(p)
                  for p in processing_summary.get('phases_completed', [])]
        return ProcessingAudit(
            batch_id=batch_id,
            phases_completed=phases,
            timestamp=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        )


# =============================================================================
# Audit Trail Generator Factory Functions
# =============================================================================

def create_audit_trail_generator(config: Optional[Any] = None) -> AuditTrailGenerator:
    """Create an audit trail generator with default configuration"""
    return AuditTrailGenerator(config)

if __name__ == "__main__":
    # Example usage
    generator = create_audit_trail_generator()
    
    # Start processing audit
    audit_id = generator.start_processing_audit(
        batch_id="batch_123",
        total_records=100,
        processing_phases=["validation", "sanitization", "privacy", "hashing", "preservation"]
    )
    
    # Log phase events
    generator.log_phase_event(
        audit_id=audit_id,
        phase="validation",
        level=AuditLevel.INFO,
        category=AuditCategory.VALIDATION,
        action=AuditAction.VALIDATE,
        component="InputValidationGateway",
        description="Batch validation started",
        details={"validation_rules": "v2.1", "strict_mode": True}
    )
    
    generator.log_phase_event(
        audit_id=audit_id,
        phase="validation",
        level=AuditLevel.INFO,
        category=AuditCategory.VALIDATION,
        action=AuditAction.VALIDATE,
        component="InputValidationGateway",
        description="Batch validation completed",
        details={"valid_records": 98, "invalid_records": 2},
        duration_ms=45.2
    )
    
    # Complete audit
    generator.complete_processing_audit(
        audit_id=audit_id,
        processed_records=98,
        failed_records=2,
        performance_metrics={"avg_latency_ms": 2.1},
        compliance_status={"gdpr": True, "ccpa": True},
        error_summary=["2 records failed validation"],
        warnings=["High memory usage detected"]
    )
    
    # Get audit trail
    audit = generator.get_audit_trail(audit_id)
    print(f"Audit completed: {audit.audit_id}")
    print(f"Processing time: {audit.performance_metrics.get('total_duration_ms', 0):.2f}ms")
    print(f"Success rate: {audit.performance_metrics.get('success_rate', 0):.2%}")
    
    # Get audit summary
    summary = generator.get_audit_summary()
    print(f"\nAudit summary: {summary.total_events} events")
    print(f"Errors: {summary.error_count}, Warnings: {summary.warning_count}")
    
    # Get generator stats
    stats = generator.get_generator_stats()
    print(f"\nGenerator stats: {stats}")
