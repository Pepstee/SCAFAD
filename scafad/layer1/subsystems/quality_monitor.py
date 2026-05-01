#!/usr/bin/env python3
"""
SCAFAD Layer 1: Quality Assurance Monitor Subsystem
==================================================

The Quality Assurance Monitor monitors data quality and provides quality metrics
for Layer 1's behavioral intake zone. It provides:

- Data quality assessment and scoring
- Schema compliance monitoring
- Anomaly preservation validation
- Quality trend analysis
- Quality alerting and reporting
- Performance quality metrics

Author: SCAFAD Research Team
Institution: Birmingham Newman University
License: MIT
Version: 1.0.0
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from enum import Enum, auto
from datetime import datetime, timezone, timedelta
import copy
from collections import defaultdict, deque

# =============================================================================
# Quality Monitor Data Models
# =============================================================================

class QualityLevel(Enum):
    """Data quality levels"""
    EXCELLENT = "excellent"         # 95%+ quality
    GOOD = "good"                   # 85-94% quality
    ACCEPTABLE = "acceptable"       # 75-84% quality
    POOR = "poor"                   # 60-74% quality
    UNACCEPTABLE = "unacceptable"   # <60% quality

class QualityMetric(Enum):
    """Quality metric types"""
    COMPLETENESS = "completeness"   # Data completeness
    ACCURACY = "accuracy"           # Data accuracy
    CONSISTENCY = "consistency"     # Data consistency
    TIMELINESS = "timeliness"       # Data timeliness
    VALIDITY = "validity"           # Data validity
    INTEGRITY = "integrity"         # Data integrity

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"                   # Informational
    WARNING = "warning"             # Warning
    ERROR = "error"                 # Error
    CRITICAL = "critical"           # Critical

@dataclass
class QualityScore:
    """Quality score for a specific metric"""
    metric: QualityMetric
    score: float
    weight: float
    details: Dict[str, Any]
    timestamp: datetime
    
    def __post_init__(self):
        """Post-initialization validation"""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Quality score must be between 0.0 and 1.0")
        
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError("Weight must be between 0.0 and 1.0")

@dataclass
class QualityMetrics:
    """Comprehensive quality metrics for a dataset"""
    overall_score: float = 1.0
    metric_scores: Dict[QualityMetric, QualityScore] = field(default_factory=dict)
    quality_level: QualityLevel = QualityLevel.GOOD
    assessment_timestamp: datetime = field(default_factory=datetime.utcnow)
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    missing_fields: int = 0
    schema_violations: int = 0
    preservation_rate: float = 1.0
    # Extra fields used by layer1_core.py
    individual_scores: List[float] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class QualityAlert:
    """Quality alert definition"""
    alert_id: str
    severity: AlertSeverity
    message: str
    metric: QualityMetric
    current_value: float
    threshold: float
    timestamp: datetime
    record_count: int
    recommendations: List[str]
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class QualityTrend:
    """Quality trend analysis"""
    metric: QualityMetric
    time_period: str
    data_points: List[Tuple[datetime, float]]
    trend_direction: str
    trend_strength: float
    average_value: float
    min_value: float
    max_value: float
    volatility: float
    metadata: Optional[Dict[str, Any]] = None

# =============================================================================
# Quality Monitor Core Class
# =============================================================================

class QualityAssuranceMonitor:
    """
    Quality Assurance Monitor for data quality assessment
    
    The Quality Assurance Monitor provides comprehensive monitoring of data
    quality across all aspects of Layer 1's processing pipeline.
    """
    
    def __init__(self, config: Any = None):
        """Initialize the Quality Assurance Monitor"""
        self.config = config
        self.logger = logging.getLogger("SCAFAD.Layer1.QualityAssuranceMonitor")
        
        # Quality thresholds
        self.quality_thresholds = {
            QualityLevel.EXCELLENT: 0.95,
            QualityLevel.GOOD: 0.85,
            QualityLevel.ACCEPTABLE: 0.75,
            QualityLevel.POOR: 0.60,
            QualityLevel.UNACCEPTABLE: 0.0
        }
        
        # Metric weights
        self.metric_weights = {
            QualityMetric.COMPLETENESS: 0.25,
            QualityMetric.ACCURACY: 0.25,
            QualityMetric.CONSISTENCY: 0.20,
            QualityMetric.TIMELINESS: 0.15,
            QualityMetric.VALIDITY: 0.10,
            QualityMetric.INTEGRITY: 0.05
        }
        
        # Alert thresholds
        self.alert_thresholds = {
            QualityMetric.COMPLETENESS: 0.8,
            QualityMetric.ACCURACY: 0.8,
            QualityMetric.CONSISTENCY: 0.8,
            QualityMetric.TIMELINESS: 0.9,
            QualityMetric.VALIDITY: 0.8,
            QualityMetric.INTEGRITY: 0.9
        }
        
        # Quality history
        self.quality_history: Dict[QualityMetric, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        
        # Active alerts
        self.active_alerts: Dict[str, QualityAlert] = {}
        
        # Performance tracking
        self.monitor_stats = {
            'total_assessments': 0,
            'total_alerts_generated': 0,
            'total_alerts_resolved': 0,
            'average_assessment_time_ms': 0.0
        }
        
        self.logger.info("Quality Assurance Monitor initialized")
    
    async def assess_batch_quality(self, records: List[Dict[str, Any]], 
                           schema_version: str = "v2.1") -> QualityMetrics:
        """
        Assess quality of a batch of records
        
        Args:
            records: List of telemetry records to assess
            schema_version: Schema version for validation
            
        Returns:
            QualityMetrics with comprehensive quality assessment
        """
        import time
        start_time = time.time()
        
        try:
            if not records:
                return self._create_empty_quality_metrics()
            
            # Calculate individual metric scores
            metric_scores = {}
            
            # Completeness
            completeness_score = self._assess_completeness(records, schema_version)
            metric_scores[QualityMetric.COMPLETENESS] = completeness_score
            
            # Accuracy
            accuracy_score = self._assess_accuracy(records, schema_version)
            metric_scores[QualityMetric.ACCURACY] = accuracy_score
            
            # Consistency
            consistency_score = self._assess_consistency(records, schema_version)
            metric_scores[QualityMetric.CONSISTENCY] = consistency_score
            
            # Timeliness
            timeliness_score = self._assess_timeliness(records)
            metric_scores[QualityMetric.TIMELINESS] = timeliness_score
            
            # Validity
            validity_score = self._assess_validity(records, schema_version)
            metric_scores[QualityMetric.VALIDITY] = validity_score
            
            # Integrity
            integrity_score = self._assess_integrity(records)
            metric_scores[QualityMetric.INTEGRITY] = integrity_score
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(metric_scores)
            
            # Determine quality level
            quality_level = self._determine_quality_level(overall_score)
            
            # Calculate summary statistics
            total_records = len(records)
            valid_records = sum(1 for r in records if self._is_record_valid(r, schema_version))
            invalid_records = total_records - valid_records
            
            # Count missing fields and schema violations
            missing_fields = self._count_missing_fields(records, schema_version)
            schema_violations = self._count_schema_violations(records, schema_version)
            
            # Calculate preservation rate (placeholder)
            preservation_rate = 0.95  # This would be calculated by preservation guard
            
            assessment_time = (time.time() - start_time) * 1000
            
            # Update quality history
            self._update_quality_history(metric_scores)
            
            # Update statistics
            self._update_monitor_stats(assessment_time)
            
            # Check for quality alerts
            self._check_quality_alerts(metric_scores, total_records)
            
            # Create quality metrics
            quality_metrics = QualityMetrics(
                overall_score=overall_score,
                metric_scores=metric_scores,
                quality_level=quality_level,
                assessment_timestamp=datetime.now(timezone.utc),
                total_records=total_records,
                valid_records=valid_records,
                invalid_records=invalid_records,
                missing_fields=missing_fields,
                schema_violations=schema_violations,
                preservation_rate=preservation_rate,
                metadata={
                    'schema_version': schema_version,
                    'assessment_time_ms': assessment_time
                }
            )
            
            self.logger.debug(f"Quality assessment completed in {assessment_time:.2f}ms")
            return quality_metrics
            
        except Exception as e:
            self.logger.error(f"Quality assessment failed: {str(e)}")
            raise
    
    def get_quality_trends(self, metric: QualityMetric, 
                          time_period: str = "24h") -> QualityTrend:
        """
        Get quality trends for a specific metric
        
        Args:
            metric: Quality metric to analyze
            time_period: Time period for trend analysis
            
        Returns:
            QualityTrend with trend analysis
        """
        try:
            if metric not in self.quality_history:
                return self._create_empty_quality_trend(metric)
            
            # Get data points for the time period
            cutoff_time = self._get_cutoff_time(time_period)
            data_points = [
                (score.timestamp, score.score)
                for score in self.quality_history[metric]
                if score.timestamp >= cutoff_time
            ]
            
            if not data_points:
                return self._create_empty_quality_trend(metric)
            
            # Sort by timestamp
            data_points.sort(key=lambda x: x[0])
            
            # Calculate trend statistics
            scores = [score for _, score in data_points]
            trend_direction = self._calculate_trend_direction(scores)
            trend_strength = self._calculate_trend_strength(scores)
            average_value = sum(scores) / len(scores)
            min_value = min(scores)
            max_value = max(scores)
            volatility = self._calculate_volatility(scores)
            
            # Create trend analysis
            trend = QualityTrend(
                metric=metric,
                time_period=time_period,
                data_points=data_points,
                trend_direction=trend_direction,
                trend_strength=trend_strength,
                average_value=average_value,
                min_value=min_value,
                max_value=max_value,
                volatility=volatility,
                metadata={
                    'data_points_count': len(data_points),
                    'analysis_timestamp': datetime.now(timezone.utc)
                }
            )
            
            return trend
            
        except Exception as e:
            self.logger.error(f"Trend analysis failed: {str(e)}")
            raise
    
    def get_active_alerts(self) -> List[QualityAlert]:
        """Get all active quality alerts"""
        return list(self.active_alerts.values())
    
    def resolve_alert(self, alert_id: str, resolution_notes: str = ""):
        """
        Resolve a quality alert
        
        Args:
            alert_id: ID of alert to resolve
            resolution_notes: Optional notes about resolution
        """
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.is_resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                
                # Remove from active alerts
                del self.active_alerts[alert_id]
                
                self.monitor_stats['total_alerts_resolved'] += 1
                self.logger.info(f"Alert {alert_id} resolved")
            
        except Exception as e:
            self.logger.error(f"Failed to resolve alert {alert_id}: {str(e)}")
    
    def get_monitor_stats(self) -> Dict[str, Any]:
        """Get monitor statistics"""
        return self.monitor_stats.copy()
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _create_empty_quality_metrics(self) -> QualityMetrics:
        """Create empty quality metrics for empty datasets"""
        empty_score = QualityScore(
            metric=QualityMetric.COMPLETENESS,
            score=0.0,
            weight=1.0,
            details={},
            timestamp=datetime.now(timezone.utc)
        )
        
        return QualityMetrics(
            overall_score=0.0,
            metric_scores={QualityMetric.COMPLETENESS: empty_score},
            quality_level=QualityLevel.UNACCEPTABLE,
            assessment_timestamp=datetime.now(timezone.utc),
            total_records=0,
            valid_records=0,
            invalid_records=0,
            missing_fields=0,
            schema_violations=0,
            preservation_rate=0.0
        )
    
    def _assess_completeness(self, records: List[Dict[str, Any]], 
                            schema_version: str) -> QualityScore:
        """Assess data completeness"""
        if not records:
            return QualityScore(
                metric=QualityMetric.COMPLETENESS,
                score=0.0,
                weight=self.metric_weights[QualityMetric.COMPLETENESS],
                details={'reason': 'No records provided'},
                timestamp=datetime.now(timezone.utc)
            )
        
        # Define required fields for schema version
        required_fields = self._get_required_fields(schema_version)
        
        total_fields = len(records) * len(required_fields)
        missing_fields = 0
        
        for record in records:
            for field_name in required_fields:
                if field_name not in record or record[field_name] is None:
                    missing_fields += 1
        
        completeness_score = 1.0 - (missing_fields / total_fields) if total_fields > 0 else 0.0
        
        return QualityScore(
            metric=QualityMetric.COMPLETENESS,
            score=completeness_score,
            weight=self.metric_weights[QualityMetric.COMPLETENESS],
            details={
                'total_fields': total_fields,
                'missing_fields': missing_fields,
                'required_fields': required_fields
            },
            timestamp=datetime.now(timezone.utc)
        )
    
    def _assess_accuracy(self, records: List[Dict[str, Any]], 
                         schema_version: str) -> QualityScore:
        """Assess data accuracy"""
        if not records:
            return QualityScore(
                metric=QualityMetric.ACCURACY,
                score=0.0,
                weight=self.metric_weights[QualityMetric.ACCURACY],
                details={'reason': 'No records provided'},
                timestamp=datetime.now(timezone.utc)
            )
        
        # Simple accuracy assessment based on field validation
        # In a real implementation, this would be more sophisticated
        total_fields = 0
        valid_fields = 0
        
        for record in records:
            for field_name, field_value in record.items():
                total_fields += 1
                if self._is_field_value_valid(field_name, field_value, schema_version):
                    valid_fields += 1
        
        accuracy_score = valid_fields / total_fields if total_fields > 0 else 0.0
        
        return QualityScore(
            metric=QualityMetric.ACCURACY,
            score=accuracy_score,
            weight=self.metric_weights[QualityMetric.ACCURACY],
            details={
                'total_fields': total_fields,
                'valid_fields': valid_fields
            },
            timestamp=datetime.now(timezone.utc)
        )
    
    def _assess_consistency(self, records: List[Dict[str, Any]], 
                           schema_version: str) -> QualityScore:
        """Assess data consistency"""
        if not records:
            return QualityScore(
                metric=QualityMetric.CONSISTENCY,
                score=0.0,
                weight=self.metric_weights[QualityMetric.CONSISTENCY],
                details={'reason': 'No records provided'},
                timestamp=datetime.now(timezone.utc)
            )
        
        # Check schema consistency across records
        schema_versions = set()
        anomaly_types = set()
        execution_phases = set()
        
        for record in records:
            if 'schema_version' in record:
                schema_versions.add(record['schema_version'])
            if 'anomaly_type' in record:
                anomaly_types.add(record['anomaly_type'])
            if 'execution_phase' in record:
                execution_phases.add(record['execution_phase'])
        
        # Consistency score based on uniformity
        schema_consistency = 1.0 / len(schema_versions) if schema_versions else 0.0
        anomaly_consistency = 1.0 / len(anomaly_types) if anomaly_types else 0.0
        phase_consistency = 1.0 / len(execution_phases) if execution_phases else 0.0
        
        # Weighted average
        consistency_score = (schema_consistency * 0.4 + 
                           anomaly_consistency * 0.3 + 
                           phase_consistency * 0.3)
        
        return QualityScore(
            metric=QualityMetric.CONSISTENCY,
            score=consistency_score,
            weight=self.metric_weights[QualityMetric.CONSISTENCY],
            details={
                'schema_versions': list(schema_versions),
                'anomaly_types': list(anomaly_types),
                'execution_phases': list(execution_phases)
            },
            timestamp=datetime.now(timezone.utc)
        )
    
    def _assess_timeliness(self, records: List[Dict[str, Any]]) -> QualityScore:
        """Assess data timeliness"""
        if not records:
            return QualityScore(
                metric=QualityMetric.TIMELINESS,
                score=0.0,
                weight=self.metric_weights[QualityMetric.TIMELINESS],
                details={'reason': 'No records provided'},
                timestamp=datetime.now(timezone.utc)
            )
        
        current_time = time.time()
        total_records = len(records)
        timely_records = 0
        
        for record in records:
            timestamp = record.get('timestamp')
            if timestamp:
                # Consider data timely if within last 5 minutes
                time_diff = current_time - timestamp
                if time_diff <= 300:  # 5 minutes
                    timely_records += 1
        
        timeliness_score = timely_records / total_records if total_records > 0 else 0.0
        
        return QualityScore(
            metric=QualityMetric.TIMELINESS,
            score=timeliness_score,
            weight=self.metric_weights[QualityMetric.TIMELINESS],
            details={
                'total_records': total_records,
                'timely_records': timely_records,
                'current_time': current_time
            },
            timestamp=datetime.now(timezone.utc)
        )
    
    def _assess_validity(self, records: List[Dict[str, Any]], 
                         schema_version: str) -> QualityScore:
        """Assess data validity"""
        if not records:
            return QualityScore(
                metric=QualityMetric.VALIDITY,
                score=0.0,
                weight=self.metric_weights[QualityMetric.VALIDITY],
                details={'reason': 'No records provided'},
                timestamp=datetime.now(timezone.utc)
            )
        
        total_records = len(records)
        valid_records = sum(1 for r in records if self._is_record_valid(r, schema_version))
        
        validity_score = valid_records / total_records if total_records > 0 else 0.0
        
        return QualityScore(
            metric=QualityMetric.VALIDITY,
            score=validity_score,
            weight=self.metric_weights[QualityMetric.VALIDITY],
            details={
                'total_records': total_records,
                'valid_records': valid_records
            },
            timestamp=datetime.now(timezone.utc)
        )
    
    def _assess_integrity(self, records: List[Dict[str, Any]]) -> QualityScore:
        """Assess data integrity"""
        if not records:
            return QualityScore(
                metric=QualityMetric.INTEGRITY,
                score=0.0,
                weight=self.metric_weights[QualityMetric.INTEGRITY],
                details={'reason': 'No records provided'},
                timestamp=datetime.now(timezone.utc)
            )
        
        # Check for data corruption indicators
        total_records = len(records)
        integrity_violations = 0
        
        for record in records:
            # Check for malformed data
            if self._has_integrity_violations(record):
                integrity_violations += 1
        
        integrity_score = 1.0 - (integrity_violations / total_records) if total_records > 0 else 0.0
        
        return QualityScore(
            metric=QualityMetric.INTEGRITY,
            score=integrity_score,
            weight=self.metric_weights[QualityMetric.INTEGRITY],
            details={
                'total_records': total_records,
                'integrity_violations': integrity_violations
            },
            timestamp=datetime.now(timezone.utc)
        )
    
    def _calculate_overall_score(self, metric_scores: Dict[QualityMetric, QualityScore]) -> float:
        """Calculate overall quality score"""
        if not metric_scores:
            return 0.0
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for metric, score in metric_scores.items():
            weighted_sum += score.score * score.weight
            total_weight += score.weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _determine_quality_level(self, overall_score: float) -> QualityLevel:
        """Determine quality level from overall score"""
        for level, threshold in sorted(self.quality_thresholds.items(), 
                                     key=lambda x: x[1], reverse=True):
            if overall_score >= threshold:
                return level
        
        return QualityLevel.UNACCEPTABLE
    
    def _is_record_valid(self, record: Dict[str, Any], schema_version: str) -> bool:
        """Check if a record is valid"""
        # Basic validation - check required fields
        required_fields = self._get_required_fields(schema_version)
        
        for field_name in required_fields:
            if field_name not in record or record[field_name] is None:
                return False
        
        return True
    
    def _get_required_fields(self, schema_version: str) -> List[str]:
        """Get required fields for a schema version"""
        if schema_version == "v2.1":
            return ['record_id', 'timestamp', 'function_name', 'execution_phase', 'anomaly_type', 'telemetry_data']
        else:
            return ['record_id', 'timestamp', 'function_name', 'execution_phase', 'anomaly_type', 'telemetry_data']
    
    def _is_field_value_valid(self, field_name: str, field_value: Any, 
                             schema_version: str) -> bool:
        """Check if a field value is valid"""
        # Basic validation - check for None and empty values
        if field_value is None:
            return False
        
        if isinstance(field_value, str) and not field_value.strip():
            return False
        
        return True
    
    def _has_integrity_violations(self, record: Dict[str, Any]) -> bool:
        """Check for data integrity violations"""
        # Check for malformed data patterns
        for key, value in record.items():
            if isinstance(value, str):
                # Check for extremely long strings (potential corruption)
                if len(value) > 10000:
                    return True
                
                # Check for null bytes or control characters
                if '\x00' in value or any(ord(c) < 32 for c in value if c not in '\t\n\r'):
                    return True
        
        return False
    
    def _count_missing_fields(self, records: List[Dict[str, Any]], 
                             schema_version: str) -> int:
        """Count missing required fields"""
        required_fields = self._get_required_fields(schema_version)
        missing_count = 0
        
        for record in records:
            for field_name in required_fields:
                if field_name not in record or record[field_name] is None:
                    missing_count += 1
        
        return missing_count
    
    def _count_schema_violations(self, records: List[Dict[str, Any]], 
                                schema_version: str) -> int:
        """Count schema violations"""
        violation_count = 0
        
        for record in records:
            if not self._is_record_valid(record, schema_version):
                violation_count += 1
        
        return violation_count
    
    def _update_quality_history(self, metric_scores: Dict[QualityMetric, QualityScore]):
        """Update quality history with new scores"""
        for metric, score in metric_scores.items():
            self.quality_history[metric].append(score)
    
    def _update_monitor_stats(self, assessment_time: float):
        """Update monitor statistics"""
        self.monitor_stats['total_assessments'] += 1
        
        # Update average assessment time
        current_avg = self.monitor_stats['average_assessment_time_ms']
        total_assessments = self.monitor_stats['total_assessments']
        
        if total_assessments > 0:
            self.monitor_stats['average_assessment_time_ms'] = (
                (current_avg * (total_assessments - 1) + assessment_time) / total_assessments
            )
    
    def _check_quality_alerts(self, metric_scores: Dict[QualityMetric, QualityScore], 
                             record_count: int):
        """Check for quality alerts"""
        for metric, score in metric_scores.items():
            threshold = self.alert_thresholds.get(metric, 0.8)
            
            if score.score < threshold:
                self._generate_quality_alert(metric, score, threshold, record_count)
    
    def _generate_quality_alert(self, metric: QualityMetric, score: QualityScore, 
                               threshold: float, record_count: int):
        """Generate a quality alert"""
        alert_id = f"quality_alert_{metric.value}_{int(time.time())}"
        
        # Determine severity
        if score.score < threshold * 0.5:
            severity = AlertSeverity.CRITICAL
        elif score.score < threshold * 0.7:
            severity = AlertSeverity.ERROR
        elif score.score < threshold * 0.85:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO
        
        # Generate recommendations
        recommendations = self._generate_quality_recommendations(metric, score, threshold)
        
        # Create alert
        alert = QualityAlert(
            alert_id=alert_id,
            severity=severity,
            message=f"Quality metric {metric.value} below threshold: {score.score:.2f} < {threshold:.2f}",
            metric=metric,
            current_value=score.score,
            threshold=threshold,
            timestamp=datetime.now(timezone.utc),
            record_count=record_count,
            recommendations=recommendations
        )
        
        # Add to active alerts
        self.active_alerts[alert_id] = alert
        self.monitor_stats['total_alerts_generated'] += 1
        
        self.logger.warning(f"Quality alert generated: {alert.message}")
    
    def _generate_quality_recommendations(self, metric: QualityMetric, score: QualityScore, 
                                        threshold: float) -> List[str]:
        """Generate recommendations for quality improvement"""
        recommendations = []
        
        if metric == QualityMetric.COMPLETENESS:
            recommendations.append("Review data collection pipeline for missing fields")
            recommendations.append("Check for network or storage issues")
        elif metric == QualityMetric.ACCURACY:
            recommendations.append("Validate data transformation logic")
            recommendations.append("Review input validation rules")
        elif metric == QualityMetric.CONSISTENCY:
            recommendations.append("Standardize data formats across sources")
            recommendations.append("Implement schema validation")
        elif metric == QualityMetric.TIMELINESS:
            recommendations.append("Optimize data processing pipeline")
            recommendations.append("Check for processing bottlenecks")
        elif metric == QualityMetric.VALIDITY:
            recommendations.append("Review data validation rules")
            recommendations.append("Check for malformed input data")
        elif metric == QualityMetric.INTEGRITY:
            recommendations.append("Investigate data corruption sources")
            recommendations.append("Implement data integrity checks")
        
        recommendations.append(f"Target improvement: {score.score:.2f} -> {threshold:.2f}")
        
        return recommendations
    
    def _create_empty_quality_trend(self, metric: QualityMetric) -> QualityTrend:
        """Create empty quality trend for metrics with no history"""
        return QualityTrend(
            metric=metric,
            time_period="24h",
            data_points=[],
            trend_direction="unknown",
            trend_strength=0.0,
            average_value=0.0,
            min_value=0.0,
            max_value=0.0,
            volatility=0.0
        )
    
    def _get_cutoff_time(self, time_period: str) -> datetime:
        """Get cutoff time for trend analysis"""
        now = datetime.now(timezone.utc)
        
        if time_period == "1h":
            return now - timedelta(hours=1)
        elif time_period == "6h":
            return now - timedelta(hours=6)
        elif time_period == "24h":
            return now - timedelta(days=1)
        elif time_period == "7d":
            return now - timedelta(days=7)
        elif time_period == "30d":
            return now - timedelta(days=30)
        else:
            return now - timedelta(hours=24)  # Default to 24h
    
    def _calculate_trend_direction(self, scores: List[float]) -> str:
        """Calculate trend direction from scores"""
        if len(scores) < 2:
            return "insufficient_data"
        
        # Simple linear trend
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        if second_avg > first_avg * 1.05:
            return "improving"
        elif second_avg < first_avg * 0.95:
            return "declining"
        else:
            return "stable"
    
    def _calculate_trend_strength(self, scores: List[float]) -> float:
        """Calculate trend strength from scores"""
        if len(scores) < 2:
            return 0.0
        
        # Calculate coefficient of variation
        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / len(scores)
        std_dev = variance ** 0.5
        
        if mean == 0:
            return 0.0
        
        cv = std_dev / mean
        return min(1.0, cv)
    
    def _calculate_volatility(self, scores: List[float]) -> float:
        """Calculate volatility from scores"""
        if len(scores) < 2:
            return 0.0
        
        # Calculate standard deviation
        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / len(scores)
        std_dev = variance ** 0.5
        
        return std_dev

# =============================================================================
# Quality Monitor Factory Functions
# =============================================================================

def create_quality_assurance_monitor(config: Optional[Any] = None) -> QualityAssuranceMonitor:
    """Create a quality assurance monitor with default configuration"""
    return QualityAssuranceMonitor(config)

if __name__ == "__main__":
    # Example usage
    monitor = create_quality_assurance_monitor()
    
    # Test records
    test_records = [
        {
            'record_id': 'test123',
            'timestamp': time.time(),
            'function_name': 'test_function',
            'execution_phase': 'invocation',
            'anomaly_type': 'performance',
            'telemetry_data': {'cpu_usage': 85.5}
        },
        {
            'record_id': 'test124',
            'timestamp': time.time() - 60,
            'function_name': 'test_function',
            'execution_phase': 'invocation',
            'anomaly_type': 'performance',
            'telemetry_data': {'cpu_usage': 87.1}
        }
    ]
    
    # Assess quality
    quality_metrics = monitor.assess_batch_quality(test_records)
    print(f"Overall quality score: {quality_metrics.overall_score:.2f}")
    print(f"Quality level: {quality_metrics.quality_level.value}")
    print(f"Total records: {quality_metrics.total_records}")
    print(f"Valid records: {quality_metrics.valid_records}")
    
    # Get trends
    trend = monitor.get_quality_trends(QualityMetric.COMPLETENESS)
    print(f"\nCompleteness trend: {trend.trend_direction}")
    print(f"Trend strength: {trend.trend_strength:.2f}")
    
    # Get active alerts
    alerts = monitor.get_active_alerts()
    print(f"\nActive alerts: {len(alerts)}")
    
    # Get monitor stats
    stats = monitor.get_monitor_stats()
    print(f"\nMonitor stats: {stats}")
