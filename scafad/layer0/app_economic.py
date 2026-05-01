"""SCAFAD Layer 0: Economic Abuse Detection Module
==============================================

Advanced economic abuse detection for serverless environments.
Implements detection algorithms for DoW/DoS attacks, cryptomining,
and billing amplification attacks based on academic research.

Academic References:
- DoWNet: Economic denial-of-wallet attacks in serverless computing (Xiong et al., 2023)
- Warmonger: Economic DoS attacks in cloud environments (Kelly et al., 2022) 
- FaaSDet: Cost anomaly detection in Function-as-a-Service (Huang et al., 2023)
- Economic Security in Cloud Computing: Survey and Taxonomy (Li et al., 2024)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Iterable, Tuple, Union
import math
import time
import statistics
import asyncio
import logging
from collections import defaultdict, deque
from enum import Enum

from .app_config import EconomicConfig
from .app_telemetry import TelemetryRecord, AnomalyType

logger = logging.getLogger(__name__)


class EconomicAttackType(Enum):
    """Types of economic attacks on serverless functions"""
    DENIAL_OF_WALLET = "DENIAL_OF_WALLET"  # DoW attacks
    CRYPTOMINING = "CRYPTOMINING"  # Unauthorized mining
    AMPLIFICATION = "AMPLIFICATION"  # Request amplification
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"  # Memory/CPU exhaustion
    BILLING_MANIPULATION = "BILLING_MANIPULATION"  # Cost inflation
    COLD_START_ABUSE = "COLD_START_ABUSE"  # Cold start cost attacks
    CONCURRENCY_ABUSE = "CONCURRENCY_ABUSE"  # Concurrent execution abuse


@dataclass
class EconomicRiskReport:
    """Comprehensive economic risk assessment report"""
    total_invocations: int
    estimated_cost_usd: float
    risk_score: float
    attack_type: Optional[EconomicAttackType]
    indicators: Dict[str, float]
    attack_hypothesis: Optional[str] = None
    confidence: float = 0.0
    cost_per_invocation: float = 0.0
    cost_anomaly_score: float = 0.0
    temporal_patterns: Dict[str, Any] = None
    recommendation: str = ""
    
    def __post_init__(self):
        if self.temporal_patterns is None:
            self.temporal_patterns = {}


@dataclass
class BillingPattern:
    """Billing pattern analysis result"""
    pattern_type: str
    frequency: float
    amplitude: float
    confidence: float
    description: str


class BillingAnomalyAnalyzer:
    """
    Advanced billing anomaly analyzer using statistical methods
    and time-series analysis for economic attack detection.
    """
    
    def __init__(self, config: EconomicConfig):
        self.config = config
        self.cost_history: deque = deque(maxlen=1000)
        self.baseline_costs: Dict[str, float] = {}
        self.pattern_cache: Dict[str, BillingPattern] = {}
        self.last_analysis_time = time.time()
        
    def analyze_cost_patterns(self, cost_history: List[float]) -> Dict[str, Any]:
        """Comprehensive cost pattern analysis using multiple statistical methods"""
        if not cost_history:
            return {"mean": 0.0, "stdev": 0.0, "spikes": [], "patterns": []}
        
        # Basic statistics
        mean_cost = statistics.fmean(cost_history)
        stdev_cost = statistics.pstdev(cost_history) if len(cost_history) > 1 else 0.0
        median_cost = statistics.median(cost_history)
        
        # Detect cost spikes using multiple methods
        z_score_spikes = self._detect_zscore_spikes(cost_history)
        iqr_spikes = self._detect_iqr_spikes(cost_history)
        mad_spikes = self._detect_mad_spikes(cost_history)
        
        # Combine spike detection results
        all_spikes = list(set(z_score_spikes + iqr_spikes + mad_spikes))
        
        # Pattern detection
        patterns = self._detect_temporal_patterns(cost_history)
        
        # Anomaly scoring
        anomaly_score = self._calculate_anomaly_score(cost_history, mean_cost, stdev_cost)
        
        return {
            "mean": mean_cost,
            "stdev": stdev_cost,
            "median": median_cost,
            "spikes": all_spikes,
            "patterns": patterns,
            "anomaly_score": anomaly_score,
            "coefficient_variation": stdev_cost / (mean_cost or 1e-6),
            "trend": self._calculate_trend(cost_history),
            "volatility": self._calculate_volatility(cost_history)
        }
    
    def _detect_zscore_spikes(self, cost_history: List[float], k: float = 3.0) -> List[int]:
        """Z-score based spike detection"""
        if len(cost_history) < 3:
            return []
        
        mu = statistics.fmean(cost_history)
        sd = statistics.pstdev(cost_history) or 1e-6
        return [i for i, c in enumerate(cost_history) if abs((c - mu) / sd) > k]
    
    def _detect_iqr_spikes(self, cost_history: List[float]) -> List[int]:
        """IQR (Interquartile Range) based outlier detection"""
        if len(cost_history) < 4:
            return []
        
        sorted_costs = sorted(cost_history)
        q1_idx = len(sorted_costs) // 4
        q3_idx = 3 * len(sorted_costs) // 4
        
        q1 = sorted_costs[q1_idx]
        q3 = sorted_costs[q3_idx]
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        return [i for i, c in enumerate(cost_history) 
                if c < lower_bound or c > upper_bound]
    
    def _detect_mad_spikes(self, cost_history: List[float], k: float = 3.0) -> List[int]:
        """MAD (Median Absolute Deviation) based robust outlier detection"""
        if len(cost_history) < 3:
            return []
        
        median = statistics.median(cost_history)
        mad = statistics.median([abs(c - median) for c in cost_history])
        
        if mad == 0:
            return []
        
        return [i for i, c in enumerate(cost_history) 
                if abs(c - median) / (mad * 1.4826) > k]
    
    def _detect_temporal_patterns(self, cost_history: List[float]) -> List[BillingPattern]:
        """Detect temporal patterns in cost data"""
        patterns = []
        
        if len(cost_history) < 10:
            return patterns
        
        # Periodic pattern detection
        periods_to_check = [2, 3, 4, 5, 6, 7, 12, 24]  # Common periods
        
        for period in periods_to_check:
            if len(cost_history) >= 2 * period:
                correlation = self._calculate_periodicity(cost_history, period)
                if correlation > 0.6:  # Strong periodicity
                    patterns.append(BillingPattern(
                        pattern_type="periodic",
                        frequency=1.0 / period,
                        amplitude=correlation,
                        confidence=correlation,
                        description=f"Periodic pattern with period {period}"
                    ))
        
        # Burst pattern detection
        burst_score = self._detect_burst_pattern(cost_history)
        if burst_score > 0.5:
            patterns.append(BillingPattern(
                pattern_type="burst",
                frequency=0.0,
                amplitude=burst_score,
                confidence=burst_score,
                description="Burst pattern detected"
            ))
        
        return patterns
    
    def _calculate_periodicity(self, data: List[float], period: int) -> float:
        """Calculate autocorrelation for a given period"""
        if len(data) < 2 * period:
            return 0.0
        
        correlations = []
        for lag in range(1, min(period + 1, len(data) // 2)):
            corr = self._autocorrelation(data, lag)
            correlations.append(corr)
        
        return max(correlations) if correlations else 0.0
    
    def _autocorrelation(self, data: List[float], lag: int) -> float:
        """Calculate autocorrelation at given lag"""
        if len(data) <= lag:
            return 0.0
        
        n = len(data) - lag
        if n <= 1:
            return 0.0
        
        mean_data = statistics.fmean(data)
        numerator = sum((data[i] - mean_data) * (data[i + lag] - mean_data) for i in range(n))
        denominator = sum((x - mean_data) ** 2 for x in data)
        
        return numerator / (denominator or 1e-6)
    
    def _detect_burst_pattern(self, cost_history: List[float]) -> float:
        """Detect burst patterns in cost data"""
        if len(cost_history) < 5:
            return 0.0
        
        # Calculate rolling variance to detect bursts
        window_size = min(5, len(cost_history) // 3)
        variances = []
        
        for i in range(len(cost_history) - window_size + 1):
            window = cost_history[i:i + window_size]
            variance = statistics.pvariance(window)
            variances.append(variance)
        
        if not variances:
            return 0.0
        
        # High variance indicates potential burst
        max_variance = max(variances)
        mean_variance = statistics.fmean(variances)
        
        return min(1.0, max_variance / (mean_variance or 1e-6) / 10)
    
    def _calculate_anomaly_score(self, cost_history: List[float], mean: float, stdev: float) -> float:
        """Calculate overall anomaly score for cost patterns"""
        if not cost_history or stdev == 0:
            return 0.0
        
        # Z-score based anomaly
        z_scores = [(abs(c - mean) / stdev) for c in cost_history]
        max_z_score = max(z_scores)
        
        # Normalize to 0-1 range
        return min(1.0, max_z_score / 5.0)
    
    def _calculate_trend(self, cost_history: List[float]) -> float:
        """Calculate trend direction (-1 to 1)"""
        if len(cost_history) < 2:
            return 0.0
        
        # Simple linear regression slope
        n = len(cost_history)
        x_values = list(range(n))
        
        x_mean = statistics.fmean(x_values)
        y_mean = statistics.fmean(cost_history)
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, cost_history))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        slope = numerator / (denominator or 1e-6)
        
        # Normalize slope
        return max(-1.0, min(1.0, slope * n / (y_mean or 1e-6)))
    
    def _calculate_volatility(self, cost_history: List[float]) -> float:
        """Calculate cost volatility"""
        if len(cost_history) < 2:
            return 0.0
        
        returns = [(cost_history[i] - cost_history[i-1]) / (cost_history[i-1] or 1e-6) 
                  for i in range(1, len(cost_history))]
        
        return statistics.pstdev(returns) if returns else 0.0
    
    def detect_cost_spikes(self, cost_history: List[float], k: float = 3.0) -> List[int]:
        """Comprehensive cost spike detection using multiple methods"""
        z_spikes = self._detect_zscore_spikes(cost_history, k)
        iqr_spikes = self._detect_iqr_spikes(cost_history)
        mad_spikes = self._detect_mad_spikes(cost_history, k)
        
        # Combine and deduplicate
        all_spikes = list(set(z_spikes + iqr_spikes + mad_spikes))
        return sorted(all_spikes)
    
    def calculate_economic_risk_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate comprehensive economic risk score"""
        risk_factors = {
            'cost_volatility': metrics.get('volatility', 0) * 0.3,
            'anomaly_score': metrics.get('anomaly_score', 0) * 0.25,
            'spike_frequency': len(metrics.get('spikes', [])) / max(1, len(metrics.get('cost_history', [1]))) * 0.2,
            'trend_severity': abs(metrics.get('trend', 0)) * 0.15,
            'pattern_complexity': len(metrics.get('patterns', [])) * 0.1
        }
        
        total_risk = sum(risk_factors.values())
        return min(1.0, max(0.0, total_risk))


class EconomicAbuseDetector:
    """
    Advanced economic abuse detector for serverless functions.
    Implements real-time detection of DoW, cryptomining, and amplification attacks.
    """
    
    def __init__(self, config: EconomicConfig):
        self.config = config
        self.billing_analyzer = BillingAnomalyAnalyzer(config)
        self.invocation_history: deque = deque(maxlen=1000)
        self.cost_baselines: Dict[str, float] = {}
        self.attack_signatures: Dict[EconomicAttackType, Dict[str, Any]] = self._initialize_attack_signatures()
        
    def _initialize_attack_signatures(self) -> Dict[EconomicAttackType, Dict[str, Any]]:
        """Initialize known attack signatures"""
        return {
            EconomicAttackType.DENIAL_OF_WALLET: {
                'min_invocation_rate': 100,  # per minute
                'min_cost_increase': 5.0,     # multiplier
                'duration_pattern': 'sustained',
                'resource_usage': 'high'
            },
            EconomicAttackType.CRYPTOMINING: {
                'min_cpu_utilization': 80.0,
                'min_duration': 30.0,         # seconds
                'memory_pattern': 'stable_high',
                'network_io': 'low'
            },
            EconomicAttackType.AMPLIFICATION: {
                'min_amplification_factor': 10.0,
                'rapid_scaling': True,
                'cost_per_second': 'exponential'
            },
            EconomicAttackType.COLD_START_ABUSE: {
                'cold_start_frequency': 'high',
                'initialization_cost_ratio': 0.8,
                'concurrent_instances': 'many'
            }
        }
    
    async def analyze_invocation(self, telemetry: TelemetryRecord, 
                               recent_invocations: List[TelemetryRecord]) -> Dict[str, Any]:
        """Analyze single invocation for economic abuse indicators"""
        
        # Calculate cost metrics
        estimated_cost = self._estimate_invocation_cost(telemetry)
        baseline_cost = self._get_baseline_cost(telemetry.function_id)
        cost_ratio = estimated_cost / (baseline_cost or 1e-6)
        
        # Analyze patterns
        temporal_analysis = self._analyze_temporal_patterns(telemetry, recent_invocations)
        resource_analysis = self._analyze_resource_usage(telemetry)
        economic_indicators = self._extract_economic_indicators(telemetry, recent_invocations)
        
        # Detect attack type
        attack_detection = self._detect_attack_type(telemetry, economic_indicators)
        
        return {
            'estimated_cost': estimated_cost,
            'baseline_cost': baseline_cost,
            'cost_ratio': cost_ratio,
            'risk_score': self._calculate_risk_score(economic_indicators, attack_detection),
            'attack_type': attack_detection['type'],
            'confidence': attack_detection['confidence'],
            'indicators': economic_indicators,
            'temporal_analysis': temporal_analysis,
            'resource_analysis': resource_analysis
        }
    
    def detect_economic_attack(self, records: Iterable[TelemetryRecord]) -> EconomicRiskReport:
        """Comprehensive economic attack detection"""
        recs = list(records)
        if not recs:
            return self._create_empty_report()
        
        # Cost analysis
        estimated_cost = self._estimate_total_cost(recs)
        cost_history = [self._estimate_invocation_cost(r) for r in recs]
        cost_analysis = self.billing_analyzer.analyze_cost_patterns(cost_history)
        
        # Extract comprehensive indicators
        indicators = self._extract_comprehensive_indicators(recs)
        
        # Pattern analysis
        temporal_patterns = self._analyze_batch_temporal_patterns(recs)
        
        # Attack type detection
        attack_analysis = self._detect_batch_attack_type(recs, indicators)
        
        # Risk calculation
        risk_score = self._calculate_comprehensive_risk_score(indicators, cost_analysis, attack_analysis)
        
        # Generate hypothesis and recommendations
        hypothesis = self._generate_attack_hypothesis(attack_analysis, indicators)
        recommendation = self._generate_recommendation(attack_analysis, risk_score)
        
        return EconomicRiskReport(
            total_invocations=len(recs),
            estimated_cost_usd=estimated_cost,
            risk_score=risk_score,
            attack_type=attack_analysis.get('primary_type'),
            indicators=indicators,
            attack_hypothesis=hypothesis,
            confidence=attack_analysis.get('confidence', 0.0),
            cost_per_invocation=estimated_cost / len(recs),
            cost_anomaly_score=cost_analysis.get('anomaly_score', 0.0),
            temporal_patterns=temporal_patterns,
            recommendation=recommendation
        )
    
    def _estimate_invocation_cost(self, record: TelemetryRecord) -> float:
        """Estimate cost of single invocation using AWS Lambda pricing model"""
        # AWS Lambda pricing (simplified):
        # - Request charge: $0.0000002 per request
        # - Duration charge: $0.0000166667 per GB-second
        
        request_cost = 0.0000002
        
        # Memory allocation (assume 128MB default if not specified)
        memory_gb = getattr(record, 'memory_limit_mb', 128) / 1024.0
        duration_seconds = record.duration
        
        duration_cost = 0.0000166667 * memory_gb * duration_seconds
        
        # Additional costs for high resource usage
        if record.cpu_utilization > 80:
            duration_cost *= 1.2  # High CPU penalty
        
        if record.memory_spike_kb > 100000:  # > 100MB
            duration_cost *= 1.1  # Memory spike penalty
        
        return request_cost + duration_cost
    
    def _estimate_total_cost(self, records: List[TelemetryRecord]) -> float:
        """Estimate total cost for batch of invocations"""
        return sum(self._estimate_invocation_cost(r) for r in records)
    
    def _get_baseline_cost(self, function_id: str) -> float:
        """Get baseline cost for function (from historical data)"""
        return self.cost_baselines.get(function_id, 0.0001)  # Default baseline
    
    def _analyze_temporal_patterns(self, telemetry: TelemetryRecord, 
                                 recent_invocations: List[TelemetryRecord]) -> Dict[str, Any]:
        """Analyze temporal patterns for single invocation context"""
        if not recent_invocations:
            return {'pattern': 'isolated', 'frequency': 0.0}
        
        # Calculate invocation frequency
        time_window = 60  # 1 minute
        current_time = telemetry.timestamp
        recent_count = sum(1 for r in recent_invocations 
                          if current_time - r.timestamp <= time_window)
        
        frequency = recent_count / time_window  # invocations per second
        
        # Detect patterns
        if frequency > 10:  # High frequency
            pattern = 'high_frequency'
        elif frequency > 1:
            pattern = 'moderate_frequency'
        else:
            pattern = 'normal_frequency'
        
        return {
            'pattern': pattern,
            'frequency': frequency,
            'recent_count': recent_count,
            'time_window': time_window
        }
    
    def _analyze_resource_usage(self, telemetry: TelemetryRecord) -> Dict[str, Any]:
        """Analyze resource usage patterns"""
        return {
            'cpu_intensity': 'high' if telemetry.cpu_utilization > 80 else 
                           'medium' if telemetry.cpu_utilization > 50 else 'low',
            'memory_intensity': 'high' if telemetry.memory_spike_kb > 200000 else
                              'medium' if telemetry.memory_spike_kb > 100000 else 'low',
            'duration_category': 'long' if telemetry.duration > 30 else
                               'medium' if telemetry.duration > 5 else 'short',
            'network_activity': 'high' if telemetry.network_io_bytes > 1048576 else
                              'medium' if telemetry.network_io_bytes > 10240 else 'low'
        }
    
    def _extract_economic_indicators(self, telemetry: TelemetryRecord, 
                                   recent_invocations: List[TelemetryRecord]) -> Dict[str, float]:
        """Extract economic abuse indicators"""
        indicators = {
            'cost_per_second': self._estimate_invocation_cost(telemetry) / max(telemetry.duration, 0.001),
            'cpu_cost_ratio': telemetry.cpu_utilization / 100.0,
            'memory_cost_ratio': telemetry.memory_spike_kb / 512000.0,  # Normalize to 512MB
            'duration_cost_factor': min(telemetry.duration / 300.0, 2.0),  # Cap at 2x for 5min+ functions
        }
        
        # Temporal indicators
        if recent_invocations:
            time_window = 60
            recent_costs = [self._estimate_invocation_cost(r) for r in recent_invocations
                          if telemetry.timestamp - r.timestamp <= time_window]
            
            if recent_costs:
                indicators.update({
                    'recent_cost_average': statistics.fmean(recent_costs),
                    'recent_cost_variance': statistics.pvariance(recent_costs),
                    'invocation_rate': len(recent_costs) / time_window
                })
        
        return indicators
    
    def _extract_comprehensive_indicators(self, records: List[TelemetryRecord]) -> Dict[str, float]:
        """Extract comprehensive economic indicators from batch"""
        if not records:
            return {}
        
        # Basic metrics
        durations = [r.duration for r in records]
        cpu_utils = [r.cpu_utilization for r in records]
        memory_spikes = [r.memory_spike_kb for r in records]
        costs = [self._estimate_invocation_cost(r) for r in records]
        
        # Temporal analysis
        timestamps = [r.timestamp for r in records]
        time_span = max(timestamps) - min(timestamps)
        invocation_rate = len(records) / max(time_span, 1.0)
        
        indicators = {
            # Cost indicators
            'avg_cost_per_invocation': statistics.fmean(costs),
            'total_cost': sum(costs),
            'cost_variance': statistics.pvariance(costs),
            'cost_per_second': sum(costs) / sum(durations),
            
            # Resource indicators
            'avg_duration': statistics.fmean(durations),
            'max_duration': max(durations),
            'avg_cpu_utilization': statistics.fmean(cpu_utils),
            'max_cpu_utilization': max(cpu_utils),
            'avg_memory_spike': statistics.fmean(memory_spikes),
            'max_memory_spike': max(memory_spikes),
            
            # Temporal indicators
            'invocation_rate': invocation_rate,
            'time_span': time_span,
            'burst_factor': self._calculate_burst_factor(timestamps),
            
            # Economic efficiency
            'cost_efficiency': sum(durations) / sum(costs) if sum(costs) > 0 else 0,
            'resource_efficiency': statistics.fmean(cpu_utils) * statistics.fmean(durations) / 100,
        }
        
        return indicators
    
    def _calculate_burst_factor(self, timestamps: List[float]) -> float:
        """Calculate burst factor (clustering of invocations)"""
        if len(timestamps) < 3:
            return 0.0
        
        sorted_times = sorted(timestamps)
        intervals = [sorted_times[i+1] - sorted_times[i] for i in range(len(sorted_times)-1)]
        
        if not intervals:
            return 0.0
        
        avg_interval = statistics.fmean(intervals)
        min_interval = min(intervals)
        
        # High burst factor if intervals are very uneven (some very short, some longer)
        return min(2.0, avg_interval / (min_interval or 1e-6) / 10)
    
    def _detect_attack_type(self, telemetry: TelemetryRecord, 
                           indicators: Dict[str, float]) -> Dict[str, Any]:
        """Detect attack type for single invocation"""
        attack_scores = {}
        
        # DoW attack detection
        dow_score = 0.0
        if indicators.get('invocation_rate', 0) > 5:  # High frequency
            dow_score += 0.3
        if indicators.get('cost_per_second', 0) > 0.001:  # High cost
            dow_score += 0.4
        if telemetry.cpu_utilization > 90:  # High CPU
            dow_score += 0.3
        attack_scores[EconomicAttackType.DENIAL_OF_WALLET] = dow_score
        
        # Cryptomining detection
        crypto_score = 0.0
        if telemetry.cpu_utilization > 80 and telemetry.duration > 10:
            crypto_score += 0.5
        if telemetry.network_io_bytes < 1024:  # Low network usage
            crypto_score += 0.2
        if telemetry.memory_spike_kb > 100000:  # High memory
            crypto_score += 0.3
        attack_scores[EconomicAttackType.CRYPTOMINING] = crypto_score
        
        # Find highest scoring attack type
        if not attack_scores or max(attack_scores.values()) < 0.3:
            return {'type': None, 'confidence': 0.0, 'scores': attack_scores}
        
        primary_attack = max(attack_scores.items(), key=lambda x: x[1])
        
        return {
            'type': primary_attack[0],
            'confidence': primary_attack[1],
            'scores': attack_scores
        }
    
    def _detect_batch_attack_type(self, records: List[TelemetryRecord], 
                                 indicators: Dict[str, float]) -> Dict[str, Any]:
        """Detect attack type from batch analysis"""
        attack_scores = defaultdict(float)
        
        # Analyze each attack type
        for attack_type, signature in self.attack_signatures.items():
            score = self._match_attack_signature(records, indicators, signature)
            attack_scores[attack_type] = score
        
        # Find primary attack type
        if not attack_scores or max(attack_scores.values()) < 0.4:
            return {'primary_type': None, 'confidence': 0.0, 'all_scores': dict(attack_scores)}
        
        primary_attack = max(attack_scores.items(), key=lambda x: x[1])
        
        return {
            'primary_type': primary_attack[0],
            'confidence': primary_attack[1],
            'all_scores': dict(attack_scores)
        }
    
    def _match_attack_signature(self, records: List[TelemetryRecord], 
                               indicators: Dict[str, float], 
                               signature: Dict[str, Any]) -> float:
        """Match records against attack signature"""
        score = 0.0
        
        # DoW signature matching
        if 'min_invocation_rate' in signature:
            if indicators.get('invocation_rate', 0) >= signature['min_invocation_rate']:
                score += 0.4
        
        if 'min_cost_increase' in signature:
            cost_ratio = indicators.get('total_cost', 0) / max(len(records) * 0.0001, 1e-6)
            if cost_ratio >= signature['min_cost_increase']:
                score += 0.3
        
        # Cryptomining signature matching
        if 'min_cpu_utilization' in signature:
            if indicators.get('avg_cpu_utilization', 0) >= signature['min_cpu_utilization']:
                score += 0.3
        
        if 'min_duration' in signature:
            if indicators.get('avg_duration', 0) >= signature['min_duration']:
                score += 0.2
        
        # Add more signature matching logic here
        
        return min(1.0, score)
    
    def _analyze_batch_temporal_patterns(self, records: List[TelemetryRecord]) -> Dict[str, Any]:
        """Analyze temporal patterns in batch of records"""
        if not records:
            return {}
        
        timestamps = [r.timestamp for r in records]
        costs = [self._estimate_invocation_cost(r) for r in records]
        
        return self.billing_analyzer.analyze_cost_patterns(costs)
    
    def _calculate_risk_score(self, indicators: Dict[str, float], 
                             attack_detection: Dict[str, Any]) -> float:
        """Calculate risk score for single invocation"""
        base_risk = attack_detection.get('confidence', 0.0) * 0.6
        
        # Add risk factors
        cost_factor = min(indicators.get('cost_per_second', 0) * 1000, 0.2)
        frequency_factor = min(indicators.get('invocation_rate', 0) / 10, 0.2)
        
        total_risk = base_risk + cost_factor + frequency_factor
        return min(1.0, max(0.0, total_risk))
    
    def _calculate_comprehensive_risk_score(self, indicators: Dict[str, float], 
                                          cost_analysis: Dict[str, Any],
                                          attack_analysis: Dict[str, Any]) -> float:
        """Calculate comprehensive risk score for batch analysis"""
        # Base risk from attack detection
        attack_risk = attack_analysis.get('confidence', 0.0) * 0.4
        
        # Cost anomaly risk
        cost_risk = cost_analysis.get('anomaly_score', 0.0) * 0.3
        
        # Resource usage risk
        resource_risk = 0.0
        if indicators.get('avg_cpu_utilization', 0) > 80:
            resource_risk += 0.1
        if indicators.get('invocation_rate', 0) > 5:
            resource_risk += 0.1
        if indicators.get('total_cost', 0) > 0.01:  # $0.01 threshold
            resource_risk += 0.1
        
        total_risk = attack_risk + cost_risk + resource_risk
        return min(1.0, max(0.0, total_risk))
    
    def _generate_attack_hypothesis(self, attack_analysis: Dict[str, Any], 
                                   indicators: Dict[str, float]) -> Optional[str]:
        """Generate human-readable attack hypothesis"""
        primary_type = attack_analysis.get('primary_type')
        confidence = attack_analysis.get('confidence', 0.0)
        
        if not primary_type or confidence < 0.4:
            return None
        
        if primary_type == EconomicAttackType.DENIAL_OF_WALLET:
            return f"Potential DoW attack: High frequency invocations ({indicators.get('invocation_rate', 0):.1f}/sec) with elevated costs"
        elif primary_type == EconomicAttackType.CRYPTOMINING:
            return f"Potential cryptomining: High CPU utilization ({indicators.get('avg_cpu_utilization', 0):.1f}%) with long durations"
        elif primary_type == EconomicAttackType.AMPLIFICATION:
            return f"Potential amplification attack: Burst pattern with cost scaling factor {indicators.get('burst_factor', 0):.1f}"
        else:
            return f"Potential {primary_type.value.lower()} attack detected"
    
    def _generate_recommendation(self, attack_analysis: Dict[str, Any], risk_score: float) -> str:
        """Generate security recommendation"""
        if risk_score < 0.3:
            return "No immediate action required. Continue monitoring."
        elif risk_score < 0.6:
            return "Moderate risk detected. Consider implementing rate limiting and cost alerts."
        else:
            attack_type = attack_analysis.get('primary_type')
            if attack_type == EconomicAttackType.DENIAL_OF_WALLET:
                return "HIGH RISK: Implement immediate rate limiting, cost caps, and function concurrency limits."
            elif attack_type == EconomicAttackType.CRYPTOMINING:
                return "HIGH RISK: Review function code, implement resource limits, and consider function isolation."
            else:
                return "HIGH RISK: Implement comprehensive monitoring, alerting, and access controls."
    
    def _create_empty_report(self) -> EconomicRiskReport:
        """Create empty risk report for no data scenarios"""
        return EconomicRiskReport(
            total_invocations=0,
            estimated_cost_usd=0.0,
            risk_score=0.0,
            attack_type=None,
            indicators={},
            attack_hypothesis=None,
            confidence=0.0,
            cost_per_invocation=0.0,
            cost_anomaly_score=0.0,
            temporal_patterns={},
            recommendation="Insufficient data for analysis."
        )
