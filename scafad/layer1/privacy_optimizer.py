#!/usr/bin/env python3
"""
SCAFAD Layer 1: Privacy-Utility Trade-off Optimizer - COMPLETE IMPLEMENTATION
============================================================================

Formal privacy-utility optimization with differential privacy,
utility-aware redaction, and anomaly detectability preservation.

Integrates with existing Enhanced Anomaly Preservation Guard.

Author: SCAFAD Research Team
Version: 2.0.0
"""

import numpy as np
try:
    import pandas as pd
except ImportError:
    pass  # pandas not available; functionality degrades gracefully
import json
import time
import logging
import hashlib
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set, Union, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque
import warnings
import copy

# Scientific computing
try:
    from scipy import stats, optimize
except ImportError:
    pass  # scipy not available; functionality degrades gracefully
try:
    from scipy.spatial.distance import cosine, euclidean
except ImportError:
    pass  # scipy not available; functionality degrades gracefully
try:
    from sklearn.preprocessing import StandardScaler
except ImportError:
    pass  # sklearn not available; functionality degrades gracefully
try:
    from sklearn.metrics import mutual_info_score
except ImportError:
    pass  # sklearn not available; functionality degrades gracefully

# Privacy libraries
import math


class PrivacyMechanism(Enum):
    """Privacy protection mechanisms"""
    LAPLACE_NOISE = "laplace_noise"
    GAUSSIAN_NOISE = "gaussian_noise"
    EXPONENTIAL_MECHANISM = "exponential_mechanism"
    K_ANONYMITY = "k_anonymity"
    L_DIVERSITY = "l_diversity"
    T_CLOSENESS = "t_closeness"
    DIFFERENTIAL_PRIVACY = "differential_privacy"
    UTILITY_AWARE_REDACTION = "utility_aware_redaction"
    SELECTIVE_PRESERVATION = "selective_preservation"


class UtilityMetric(Enum):
    """Utility measurement metrics"""
    ANOMALY_DETECTABILITY = "anomaly_detectability"
    INFORMATION_PRESERVATION = "information_preservation"
    STATISTICAL_UTILITY = "statistical_utility"
    PATTERN_PRESERVATION = "pattern_preservation"
    CORRELATION_MAINTENANCE = "correlation_maintenance"
    DISTRIBUTIONAL_FIDELITY = "distributional_fidelity"


@dataclass
class PrivacyBudget:
    """Differential privacy budget management"""
    epsilon: float  # Privacy loss parameter
    delta: float    # Failure probability
    
    # Budget allocation
    allocated_epsilon: float = 0.0
    remaining_epsilon: float = 0.0
    allocation_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Composition tracking
    total_queries: int = 0
    composition_method: str = "basic"  # basic, advanced, moments_accountant
    
    # Budget constraints
    max_epsilon: float = 1.0
    max_delta: float = 1e-5
    min_remaining_threshold: float = 0.1
    
    def __post_init__(self):
        self.remaining_epsilon = self.epsilon
    
    def allocate_budget(self, operation: str, requested_epsilon: float) -> bool:
        """Allocate privacy budget for an operation"""
        if self.remaining_epsilon >= requested_epsilon:
            self.allocated_epsilon += requested_epsilon
            self.remaining_epsilon -= requested_epsilon
            self.total_queries += 1
            
            self.allocation_history.append({
                'operation': operation,
                'epsilon': requested_epsilon,
                'timestamp': time.time(),
                'remaining': self.remaining_epsilon
            })
            return True
        return False
    
    def is_budget_exhausted(self) -> bool:
        """Check if privacy budget is exhausted"""
        return self.remaining_epsilon < self.min_remaining_threshold


@dataclass
class UtilityMeasurement:
    """Utility measurement result"""
    metric_type: UtilityMetric
    value: float
    confidence: float
    baseline_value: float
    preservation_ratio: float
    
    # Detailed analysis
    component_scores: Dict[str, float] = field(default_factory=dict)
    quality_indicators: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    measurement_timestamp: float = field(default_factory=time.time)
    measurement_method: str = ""
    sample_size: int = 0


@dataclass
class PrivacyUtilityTradeoff:
    """Privacy-utility trade-off analysis result"""
    privacy_level: float
    utility_level: float
    pareto_optimal: bool
    
    # Trade-off metrics
    privacy_loss: float
    utility_loss: float
    trade_off_ratio: float
    
    # Mechanism details
    mechanism: PrivacyMechanism
    parameters: Dict[str, Any]
    
    # Optimization details
    optimization_score: float
    constraints_satisfied: bool
    constraint_violations: List[str] = field(default_factory=list)


class CompositionTracker:
    """Track privacy budget composition across multiple queries"""
    
    def __init__(self):
        self.query_history = []
        self.total_epsilon = 0.0
        self.total_delta = 0.0
        self.composition_method = "basic"
        
    def add_query(self, epsilon: float, delta: float, mechanism: str):
        """Add a new query to composition tracking"""
        self.query_history.append({
            'epsilon': epsilon,
            'delta': delta,
            'mechanism': mechanism,
            'timestamp': time.time()
        })
        
        # Basic composition (can be improved with advanced composition)
        self.total_epsilon += epsilon
        self.total_delta += delta
    
    def get_total_privacy_cost(self) -> Tuple[float, float]:
        """Get total privacy cost so far"""
        return self.total_epsilon, self.total_delta
    
    def get_composition_analysis(self) -> Dict[str, Any]:
        """Get detailed composition analysis"""
        if not self.query_history:
            return {'no_queries': True}
        
        return {
            'total_queries': len(self.query_history),
            'total_epsilon': self.total_epsilon,
            'total_delta': self.total_delta,
            'composition_method': self.composition_method,
            'query_breakdown': {
                'by_mechanism': self._get_mechanism_breakdown(),
                'temporal_distribution': self._get_temporal_distribution()
            }
        }
    
    def _get_mechanism_breakdown(self) -> Dict[str, Dict[str, float]]:
        """Get breakdown of privacy cost by mechanism"""
        mechanism_stats = defaultdict(lambda: {'epsilon': 0.0, 'delta': 0.0, 'count': 0})
        
        for query in self.query_history:
            mech = query['mechanism']
            mechanism_stats[mech]['epsilon'] += query['epsilon']
            mechanism_stats[mech]['delta'] += query['delta']
            mechanism_stats[mech]['count'] += 1
        
        return dict(mechanism_stats)
    
    def _get_temporal_distribution(self) -> Dict[str, Any]:
        """Get temporal distribution of queries"""
        if not self.query_history:
            return {}
        
        timestamps = [q['timestamp'] for q in self.query_history]
        
        return {
            'first_query': min(timestamps),
            'last_query': max(timestamps),
            'time_span': max(timestamps) - min(timestamps),
            'query_rate': len(self.query_history) / (max(timestamps) - min(timestamps) + 1)
        }
    
    def reset_composition(self):
        """Reset composition tracking"""
        self.query_history.clear()
        self.total_epsilon = 0.0
        self.total_delta = 0.0
    
    def set_composition_method(self, method: str):
        """Set composition method (basic, advanced, moments_accountant)"""
        if method in ['basic', 'advanced', 'moments_accountant']:
            self.composition_method = method
        else:
            raise ValueError(f"Unknown composition method: {method}")


class DifferentialPrivacyBudgetManager:
    """Advanced differential privacy budget management"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.privacy_budgets: Dict[str, PrivacyBudget] = {}
        self.composition_tracker = CompositionTracker()
        
        # Budget optimization parameters
        self.optimization_method = self.config.get('optimization_method', 'convex')
        self.budget_refresh_interval = self.config.get('refresh_interval', 3600)  # 1 hour
        
        self.logger = logging.getLogger(__name__ + ".DifferentialPrivacyBudgetManager")
    
    def create_budget(self, budget_id: str, epsilon: float, delta: float) -> PrivacyBudget:
        """Create a new privacy budget"""
        budget = PrivacyBudget(
            epsilon=epsilon,
            delta=delta,
            max_epsilon=self.config.get('max_epsilon', 1.0),
            max_delta=self.config.get('max_delta', 1e-5)
        )
        self.privacy_budgets[budget_id] = budget
        return budget
    
    def optimize_epsilon_delta(self, utility_requirements: Dict[str, float],
                             privacy_constraints: Dict[str, float]) -> Tuple[float, float]:
        """Optimize epsilon and delta parameters for given requirements"""
        
        # Define optimization objective
        def objective(params):
            epsilon, delta = params
            
            # Privacy cost (higher epsilon = higher cost)
            privacy_cost = epsilon / privacy_constraints.get('max_epsilon', 1.0)
            
            # Utility benefit estimation
            utility_benefit = self._estimate_utility_benefit(epsilon, delta, utility_requirements)
            
            # Combined objective (minimize privacy cost, maximize utility)
            return privacy_cost - utility_benefit
        
        # Constraints
        constraints = [
            {'type': 'ineq', 'fun': lambda x: privacy_constraints.get('max_epsilon', 1.0) - x[0]},
            {'type': 'ineq', 'fun': lambda x: privacy_constraints.get('max_delta', 1e-5) - x[1]},
            {'type': 'ineq', 'fun': lambda x: x[0] - 0.01},  # Minimum epsilon
            {'type': 'ineq', 'fun': lambda x: x[1] - 1e-10}  # Minimum delta
        ]
        
        # Initial guess
        x0 = [0.5, 1e-6]
        
        # Bounds
        bounds = [
            (0.01, privacy_constraints.get('max_epsilon', 1.0)),
            (1e-10, privacy_constraints.get('max_delta', 1e-5))
        ]
        
        try:
            result = optimize.minimize(
                objective, x0, method='SLSQP',
                constraints=constraints, bounds=bounds
            )
            
            if result.success:
                optimal_epsilon, optimal_delta = result.x
                self.logger.info(f"Optimized privacy parameters: ε={optimal_epsilon:.4f}, δ={optimal_delta:.2e}")
                return optimal_epsilon, optimal_delta
            else:
                self.logger.warning("Privacy parameter optimization failed, using defaults")
                return 0.5, 1e-6
                
        except Exception as e:
            self.logger.error(f"Privacy parameter optimization error: {e}")
            return 0.5, 1e-6
    
    def _estimate_utility_benefit(self, epsilon: float, delta: float, 
                                requirements: Dict[str, float]) -> float:
        """Estimate utility benefit for given privacy parameters"""
        
        # Utility generally increases with epsilon (less noise)
        base_utility = 1.0 - np.exp(-epsilon)  # Asymptotic utility gain
        
        # Adjust based on requirements
        for metric, required_level in requirements.items():
            if metric == 'anomaly_detectability':
                # Anomaly detection typically needs higher epsilon
                adjustment = max(0, required_level - 0.5) * 0.5
                base_utility += adjustment
            elif metric == 'information_preservation':
                # Information preservation benefits from lower noise
                adjustment = required_level * 0.3
                base_utility += adjustment
        
        # Delta penalty (higher delta = lower utility in some contexts)
        delta_penalty = delta * 1000  # Scale delta to reasonable range
        
        return base_utility - delta_penalty
    
    def allocate_adaptive_budget(self, operation: str, utility_target: float,
                               privacy_sensitivity: float) -> Tuple[bool, float]:
        """Adaptively allocate privacy budget based on utility needs"""
        
        # Calculate required epsilon for utility target
        required_epsilon = self._calculate_required_epsilon(utility_target, privacy_sensitivity)
        
        # Find best budget to allocate from
        best_budget_id = None
        best_budget = None
        
        for budget_id, budget in self.privacy_budgets.items():
            if budget.remaining_epsilon >= required_epsilon:
                if best_budget is None or budget.remaining_epsilon > best_budget.remaining_epsilon:
                    best_budget_id = budget_id
                    best_budget = budget
        
        if best_budget and best_budget.allocate_budget(operation, required_epsilon):
            self.logger.debug(f"Allocated ε={required_epsilon:.4f} for {operation} from budget {best_budget_id}")
            return True, required_epsilon
        
        # Try to find partial allocation
        available_epsilon = max((b.remaining_epsilon for b in self.privacy_budgets.values()), default=0)
        if available_epsilon > 0:
            # Allocate what's available and accept lower utility
            if best_budget and best_budget.allocate_budget(operation, available_epsilon):
                self.logger.warning(f"Partial allocation ε={available_epsilon:.4f} for {operation} (requested {required_epsilon:.4f})")
                return True, available_epsilon
        
        self.logger.error(f"Failed to allocate budget for {operation}")
        return False, 0.0
    
    def _calculate_required_epsilon(self, utility_target: float, sensitivity: float) -> float:
        """Calculate required epsilon for utility target"""
        
        # Simple model: higher utility target requires higher epsilon
        if utility_target >= 0.9:
            base_epsilon = 0.5
        elif utility_target >= 0.8:
            base_epsilon = 0.3
        elif utility_target >= 0.7:
            base_epsilon = 0.2
        else:
            base_epsilon = 0.1
        
        # Adjust for sensitivity
        epsilon = base_epsilon * sensitivity
        
        return min(epsilon, 1.0)  # Cap at maximum
    
    def refresh_budgets(self):
        """Refresh privacy budgets (for scenarios with periodic renewal)"""
        current_time = time.time()
        
        for budget_id, budget in self.privacy_budgets.items():
            # Check if budget should be refreshed
            if hasattr(budget, 'last_refresh'):
                time_since_refresh = current_time - budget.last_refresh
                if time_since_refresh >= self.budget_refresh_interval:
                    budget.remaining_epsilon = budget.epsilon
                    budget.allocated_epsilon = 0.0
                    budget.total_queries = 0
                    budget.allocation_history.clear()
                    budget.last_refresh = current_time
                    self.logger.info(f"Refreshed privacy budget {budget_id}")
            else:
                budget.last_refresh = current_time


class UtilityAwareRedactionEngine:
    """Utility-aware data redaction that minimizes anomaly detection impact"""
    
    def __init__(self, preservation_guard, config: Dict[str, Any] = None):
        self.preservation_guard = preservation_guard
        self.config = config or {}
        
        # Redaction strategies
        self.redaction_strategies = {
            'critical_preservation': self._critical_field_preservation_strategy,
            'statistical_preservation': self._statistical_preservation_strategy,
            'anomaly_aware': self._anomaly_aware_redaction_strategy,
            'selective_masking': self._selective_masking_strategy,
            'utility_maximizing': self._utility_maximizing_strategy
        }
        
        # Field importance cache
        self.field_importance_cache = {}
        self.importance_cache_ttl = self.config.get('importance_cache_ttl', 300)
        
        self.logger = logging.getLogger(__name__ + ".UtilityAwareRedactionEngine")
    
    async def minimize_anomaly_detection_impact(self, data: Dict[str, Any],
                                              redaction_requirements: Dict[str, Any],
                                              target_utility: float = 0.85) -> Dict[str, Any]:
        """Minimize impact on anomaly detection while satisfying redaction requirements"""
        
        start_time = time.perf_counter()
        
        try:
            # Analyze field importance for anomaly detection
            field_importance = await self._analyze_field_importance(data)
            
            # Create redaction plan
            redaction_plan = await self._create_optimal_redaction_plan(
                data, redaction_requirements, field_importance, target_utility
            )
            
            # Apply redaction
            redacted_data = await self._apply_redaction_plan(data, redaction_plan)
            
            # Validate utility preservation
            utility_preserved = await self._validate_utility_preservation(
                data, redacted_data, target_utility
            )
            
            if not utility_preserved:
                # Adjust redaction plan and retry
                adjusted_plan = await self._adjust_redaction_plan(
                    redaction_plan, field_importance, target_utility
                )
                redacted_data = await self._apply_redaction_plan(data, adjusted_plan)
            
            processing_time = (time.perf_counter() - start_time) * 1000
            self.logger.debug(f"Utility-aware redaction completed in {processing_time:.2f}ms")
            
            return redacted_data
            
        except Exception as e:
            self.logger.error(f"Utility-aware redaction failed: {e}")
            raise
    
    async def _analyze_field_importance(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Analyze importance of each field for anomaly detection"""
        
        # Check cache first
        data_hash = hashlib.md5(str(sorted(data.items())).encode()).hexdigest()
        if data_hash in self.field_importance_cache:
            cache_entry = self.field_importance_cache[data_hash]
            if time.time() - cache_entry['timestamp'] < self.importance_cache_ttl:
                return cache_entry['importance']
        
        importance_scores = {}
        
        # Use preservation guard to assess field importance
        for field_name in data.keys():
            # Create modified data without this field
            modified_data = {k: v for k, v in data.items() if k != field_name}
            
            # Assess preservation impact
            try:
                assessment = await self.preservation_guard.assess_preservation_impact(
                    data, modified_data, f"field_importance_{field_name}"
                )
                
                # Higher preservation loss = higher importance
                importance = 1.0 - assessment.preservation_effectiveness
                importance_scores[field_name] = importance
                
            except Exception as e:
                self.logger.debug(f"Field importance analysis failed for {field_name}: {e}")
                importance_scores[field_name] = 0.5  # Default medium importance
        
        # Cache the results
        self.field_importance_cache[data_hash] = {
            'importance': importance_scores,
            'timestamp': time.time()
        }
        
        return importance_scores
    
    async def _create_optimal_redaction_plan(self, data: Dict[str, Any],
                                           requirements: Dict[str, Any],
                                           field_importance: Dict[str, float],
                                           target_utility: float) -> Dict[str, Any]:
        """Create optimal redaction plan balancing privacy and utility"""
        
        redaction_plan = {
            'field_operations': {},
            'global_operations': [],
            'utility_target': target_utility,
            'strategy': requirements.get('strategy', 'anomaly_aware')
        }
        
        # Sort fields by importance (least important first for redaction)
        sorted_fields = sorted(field_importance.items(), key=lambda x: x[1])
        
        # Identify required redactions
        required_redactions = requirements.get('required_fields', [])
        optional_redactions = requirements.get('optional_fields', [])
        
        # Plan required redactions with minimal utility impact
        for field_name in required_redactions:
            if field_name in data:
                redaction_method = self._select_optimal_redaction_method(
                    field_name, data[field_name], field_importance.get(field_name, 0.5)
                )
                redaction_plan['field_operations'][field_name] = redaction_method
        
        # Plan optional redactions based on utility budget
        current_utility_estimate = await self._estimate_redaction_utility_impact(
            data, redaction_plan['field_operations']
        )
        
        for field_name, importance in sorted_fields:
            if field_name in optional_redactions and field_name not in redaction_plan['field_operations']:
                # Test if we can afford to redact this field
                test_operations = redaction_plan['field_operations'].copy()
                test_method = self._select_optimal_redaction_method(
                    field_name, data[field_name], importance
                )
                test_operations[field_name] = test_method
                
                test_utility = await self._estimate_redaction_utility_impact(data, test_operations)
                
                if test_utility >= target_utility:
                    redaction_plan['field_operations'][field_name] = test_method
                    current_utility_estimate = test_utility
                else:
                    break  # Can't afford more redactions
        
        return redaction_plan
    
    def _select_optimal_redaction_method(self, field_name: str, field_value: Any,
                                       importance: float) -> Dict[str, Any]:
        """Select optimal redaction method for a field"""
        
        method = {
            'type': 'preserve',
            'parameters': {},
            'importance': importance
        }
        
        if importance < 0.2:  # Low importance - can use aggressive redaction
            if isinstance(field_value, str):
                if len(field_value) > 20:
                    method = {'type': 'hash', 'parameters': {'algorithm': 'sha256'}}
                else:
                    method = {'type': 'mask', 'parameters': {'pattern': 'X' * len(field_value)}}
            elif isinstance(field_value, (int, float)):
                method = {'type': 'noise', 'parameters': {'noise_type': 'laplace', 'scale': 0.1}}
            else:
                method = {'type': 'remove', 'parameters': {}}
        
        elif importance < 0.5:  # Medium importance - use moderate redaction
            if isinstance(field_value, str):
                method = {'type': 'partial_mask', 'parameters': {'preserve_ratio': 0.3}}
            elif isinstance(field_value, (int, float)):
                method = {'type': 'noise', 'parameters': {'noise_type': 'gaussian', 'scale': 0.05}}
            elif isinstance(field_value, list):
                method = {'type': 'sample', 'parameters': {'sample_ratio': 0.7}}
            else:
                method = {'type': 'generalize', 'parameters': {'level': 1}}
        
        else:  # High importance - use minimal redaction
            if isinstance(field_value, str) and any(sensitive in field_name.lower() 
                                                   for sensitive in ['id', 'name', 'email', 'phone']):
                method = {'type': 'tokenize', 'parameters': {'preserve_format': True}}
            elif isinstance(field_value, (int, float)):
                method = {'type': 'noise', 'parameters': {'noise_type': 'gaussian', 'scale': 0.01}}
            else:
                method = {'type': 'preserve', 'parameters': {}}
        
        return method
    
    async def _estimate_redaction_utility_impact(self, original_data: Dict[str, Any],
                                               redaction_operations: Dict[str, Dict[str, Any]]) -> float:
        """Estimate utility impact of redaction operations"""
        
        # Apply redaction operations to create test data
        test_data = copy.deepcopy(original_data)
        
        for field_name, operation in redaction_operations.items():
            if field_name in test_data:
                test_data[field_name] = self._apply_redaction_operation(
                    test_data[field_name], operation
                )
        
        # Assess preservation impact
        try:
            assessment = await self.preservation_guard.assess_preservation_impact(
                original_data, test_data, "utility_estimation"
            )
            return assessment.preservation_effectiveness
            
        except Exception as e:
            self.logger.debug(f"Utility estimation failed: {e}")
            return 0.5  # Conservative estimate
    
    def _apply_redaction_operation(self, value: Any, operation: Dict[str, Any]) -> Any:
        """Apply a single redaction operation to a value"""
        
        op_type = operation['type']
        params = operation.get('parameters', {})
        
        if op_type == 'preserve':
            return value
        
        elif op_type == 'remove':
            return None
        
        elif op_type == 'hash':
            algorithm = params.get('algorithm', 'sha256')
            if algorithm == 'sha256':
                return hashlib.sha256(str(value).encode()).hexdigest()[:16]
            else:
                return hashlib.md5(str(value).encode()).hexdigest()[:16]
        
        elif op_type == 'mask':
            if isinstance(value, str):
                pattern = params.get('pattern', 'X' * len(value))
                return pattern[:len(value)]
            else:
                return '***MASKED***'
        
        elif op_type == 'partial_mask':
            if isinstance(value, str):
                preserve_ratio = params.get('preserve_ratio', 0.3)
                preserve_length = int(len(value) * preserve_ratio)
                masked_length = len(value) - preserve_length
                return value[:preserve_length] + 'X' * masked_length
            else:
                return value
        
        elif op_type == 'noise':
            if isinstance(value, (int, float)):
                noise_type = params.get('noise_type', 'gaussian')
                scale = params.get('scale', 0.1)
                
                if noise_type == 'gaussian':
                    noise = np.random.normal(0, scale * abs(value))
                elif noise_type == 'laplace':
                    noise = np.random.laplace(0, scale * abs(value))
                else:
                    noise = 0
                
                return value + noise
            else:
                return value
        
        elif op_type == 'sample':
            if isinstance(value, list):
                sample_ratio = params.get('sample_ratio', 0.7)
                sample_size = max(1, int(len(value) * sample_ratio))
                return np.random.choice(value, size=sample_size, replace=False).tolist()
            else:
                return value
        
        elif op_type == 'generalize':
            # Simple generalization - round numbers, truncate strings
            if isinstance(value, float):
                decimals = max(0, 2 - params.get('level', 1))
                return round(value, decimals)
            elif isinstance(value, int):
                magnitude = 10 ** params.get('level', 1)
                return (value // magnitude) * magnitude
            elif isinstance(value, str):
                max_length = max(1, len(value) - params.get('level', 1) * 2)
                return value[:max_length] + '...' if len(value) > max_length else value
            else:
                return value
        
        elif op_type == 'tokenize':
            # Create consistent token for same values
            token_hash = hashlib.md5(str(value).encode()).hexdigest()[:8]
            if params.get('preserve_format', False) and isinstance(value, str):
                # Try to preserve format (e.g., email structure)
                if '@' in value:
                    return f"user_{token_hash}@domain.com"
                elif value.isdigit():
                    return token_hash.zfill(len(value))[:len(value)]
                else:
                    return f"token_{token_hash}"
            else:
                return f"token_{token_hash}"
        
        else:
            self.logger.warning(f"Unknown redaction operation: {op_type}")
            return value
    
    async def _apply_redaction_plan(self, data: Dict[str, Any],
                                  plan: Dict[str, Any]) -> Dict[str, Any]:
        """Apply complete redaction plan to data"""
        
        redacted_data = copy.deepcopy(data)
        
        # Apply field operations
        for field_name, operation in plan['field_operations'].items():
            if field_name in redacted_data:
                redacted_data[field_name] = self._apply_redaction_operation(
                    redacted_data[field_name], operation
                )
        
        # Apply global operations
        for global_op in plan.get('global_operations', []):
            redacted_data = self._apply_global_operation(redacted_data, global_op)
        
        return redacted_data
    
    def _apply_global_operation(self, data: Dict[str, Any], operation: Dict[str, Any]) -> Dict[str, Any]:
        """Apply global redaction operations"""
        # Placeholder for global operations like k-anonymity, l-diversity
        return data
    
    async def _validate_utility_preservation(self, original_data: Dict[str, Any],
                                           redacted_data: Dict[str, Any],
                                           target_utility: float) -> bool:
        """Validate that utility preservation meets target"""
        
        try:
            assessment = await self.preservation_guard.assess_preservation_impact(
                original_data, redacted_data, "utility_validation"
            )
            
            return assessment.preservation_effectiveness >= target_utility
            
        except Exception as e:
            self.logger.error(f"Utility validation failed: {e}")
            return False
    
    async def _adjust_redaction_plan(self, plan: Dict[str, Any],
                                   field_importance: Dict[str, float],
                                   target_utility: float) -> Dict[str, Any]:
        """Adjust redaction plan to meet utility targets"""
        
        adjusted_plan = copy.deepcopy(plan)
        
        # Remove redactions for highest importance fields that are optional
        importance_sorted = sorted(field_importance.items(), key=lambda x: x[1], reverse=True)
        
        for field_name, importance in importance_sorted:
            if field_name in adjusted_plan['field_operations']:
                operation = adjusted_plan['field_operations'][field_name]
                
                # If this is a high-impact operation on important field, reduce it
                if importance > 0.7 and operation['type'] in ['remove', 'hash', 'mask']:
                    # Switch to less aggressive redaction
                    adjusted_plan['field_operations'][field_name] = {
                        'type': 'noise' if isinstance(field_name, (int, float)) else 'partial_mask',
                        'parameters': {'scale': 0.01} if isinstance(field_name, (int, float)) else {'preserve_ratio': 0.8}
                    }
                elif importance > 0.8:
                    # Preserve completely if very important
                    adjusted_plan['field_operations'][field_name] = {
                        'type': 'preserve',
                        'parameters': {}
                    }
        
        return adjusted_plan
    
    # Strategy implementations
    async def _critical_field_preservation_strategy(self, data: Dict[str, Any],
                                                   requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Strategy that preserves critical fields at all costs"""
        critical_fields = requirements.get('critical_fields', [])
        target_utility = requirements.get('target_utility', 0.9)
        
        redacted_data = copy.deepcopy(data)
        
        # Preserve critical fields completely
        for field in critical_fields:
            if field in redacted_data:
                # Mark as preserved (no-op)
                pass
        
        # Apply minimal redaction to non-critical fields
        for field_name, value in data.items():
            if field_name not in critical_fields:
                # Apply minimal redaction based on data type
                if isinstance(value, str) and any(sensitive in field_name.lower() 
                                                for sensitive in ['password', 'secret', 'key']):
                    redacted_data[field_name] = '***REDACTED***'
                elif isinstance(value, (int, float)) and 'id' not in field_name.lower():
                    # Add minimal noise to non-ID numeric fields
                    noise = np.random.normal(0, 0.01 * abs(value))
                    redacted_data[field_name] = value + noise
        
        return redacted_data
    
    async def _statistical_preservation_strategy(self, data: Dict[str, Any],
                                               requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Strategy that preserves statistical properties"""
        target_utility = requirements.get('target_utility', 0.8)
        preserve_distributions = requirements.get('preserve_distributions', True)
        
        redacted_data = copy.deepcopy(data)
        
        # Extract numeric values for statistical analysis
        numeric_fields = {}
        for field_name, value in data.items():
            if isinstance(value, (int, float)):
                numeric_fields[field_name] = value
        
        # Calculate original statistics
        if numeric_fields:
            field_means = {k: v for k, v in numeric_fields.items()}
            field_vars = {k: v**2 for k, v in numeric_fields.items()}  # Simplified variance
            
            # Add calibrated noise to preserve statistical properties
            for field_name, original_value in numeric_fields.items():
                # Use Laplace mechanism with calibrated scale
                sensitivity = abs(original_value) * 0.1  # Estimated sensitivity
                epsilon = 0.1  # Conservative epsilon for statistical preservation
                scale = sensitivity / epsilon
                
                noise = np.random.laplace(0, scale)
                redacted_data[field_name] = original_value + noise
        
        # Handle string fields with format-preserving tokenization
        for field_name, value in data.items():
            if isinstance(value, str) and field_name not in numeric_fields:
                if any(sensitive in field_name.lower() for sensitive in ['name', 'email', 'id']):
                    # Tokenize while preserving format
                    token_hash = hashlib.md5(value.encode()).hexdigest()[:8]
                    if '@' in value:
                        redacted_data[field_name] = f"user_{token_hash}@domain.com"
                    elif value.isdigit():
                        redacted_data[field_name] = token_hash.zfill(len(value))[:len(value)]
                    else:
                        redacted_data[field_name] = f"token_{token_hash}"
        
        return redacted_data
    
    async def _anomaly_aware_redaction_strategy(self, data: Dict[str, Any],
                                              requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Strategy specifically designed for anomaly detection preservation"""
        target_utility = requirements.get('target_utility', 0.85)
        anomaly_indicators = requirements.get('anomaly_indicators', [])
        
        # Use the main utility-aware redaction engine
        return await self.minimize_anomaly_detection_impact(
            data, requirements, target_utility
        )
    
    async def _selective_masking_strategy(self, data: Dict[str, Any],
                                        requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Strategy using selective masking based on context"""
        context_sensitivity = requirements.get('context_sensitivity', {})
        masking_intensity = requirements.get('masking_intensity', 'medium')
        
        redacted_data = copy.deepcopy(data)
        
        # Define masking intensity levels
        intensity_configs = {
            'low': {'preserve_ratio': 0.8, 'noise_scale': 0.01},
            'medium': {'preserve_ratio': 0.5, 'noise_scale': 0.05},
            'high': {'preserve_ratio': 0.2, 'noise_scale': 0.1}
        }
        
        config = intensity_configs.get(masking_intensity, intensity_configs['medium'])
        
        for field_name, value in data.items():
            field_sensitivity = context_sensitivity.get(field_name, 0.5)
            
            if field_sensitivity > 0.7:  # High sensitivity
                if isinstance(value, str):
                    # Heavy masking for sensitive strings
                    preserve_length = max(1, int(len(value) * config['preserve_ratio']))
                    redacted_data[field_name] = value[:preserve_length] + 'X' * (len(value) - preserve_length)
                elif isinstance(value, (int, float)):
                    # Add significant noise to sensitive numbers
                    noise = np.random.laplace(0, config['noise_scale'] * abs(value))
                    redacted_data[field_name] = value + noise
                else:
                    # Hash complex objects
                    redacted_data[field_name] = hashlib.md5(str(value).encode()).hexdigest()[:16]
            
            elif field_sensitivity > 0.3:  # Medium sensitivity
                if isinstance(value, str):
                    # Partial masking
                    mid_point = len(value) // 2
                    redacted_data[field_name] = value[:mid_point] + 'X' * (len(value) - mid_point)
                elif isinstance(value, (int, float)):
                    # Moderate noise
                    noise = np.random.normal(0, config['noise_scale'] * abs(value))
                    redacted_data[field_name] = value + noise
            
            # Low sensitivity fields preserved as-is
        
        return redacted_data
    
    async def _utility_maximizing_strategy(self, data: Dict[str, Any],
                                         requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Strategy that maximizes utility given privacy constraints"""
        privacy_budget = requirements.get('privacy_budget', 1.0)
        min_privacy_level = requirements.get('min_privacy_level', 0.3)
        
        redacted_data = copy.deepcopy(data)
        
        # Analyze utility impact of each potential redaction
        field_utility_impact = {}
        
        for field_name in data.keys():
            # Estimate utility impact of redacting this field
            test_data = {k: v if k != field_name else None for k, v in data.items()}
            
            try:
                assessment = await self.preservation_guard.assess_preservation_impact(
                    data, test_data, f"utility_impact_{field_name}"
                )
                field_utility_impact[field_name] = 1.0 - assessment.preservation_effectiveness
            except:
                field_utility_impact[field_name] = 0.5  # Default impact
        
        # Sort fields by utility impact (redact low-impact fields first)
        sorted_by_impact = sorted(field_utility_impact.items(), key=lambda x: x[1])
        
        # Calculate privacy achieved and stop when minimum is reached
        current_privacy = 0.0
        
        for field_name, impact in sorted_by_impact:
            if current_privacy >= min_privacy_level:
                break
            
            value = data[field_name]
            
            # Apply minimal redaction to achieve privacy target
            if isinstance(value, str):
                if 'id' in field_name.lower() or 'key' in field_name.lower():
                    redacted_data[field_name] = hashlib.md5(value.encode()).hexdigest()[:12]
                    current_privacy += 0.2
                else:
                    # Tokenize
                    token = hashlib.md5(value.encode()).hexdigest()[:8]
                    redacted_data[field_name] = f"token_{token}"
                    current_privacy += 0.1
            
            elif isinstance(value, (int, float)):
                # Add minimal noise
                noise = np.random.normal(0, 0.01 * abs(value))
                redacted_data[field_name] = value + noise
                current_privacy += 0.05
        
        return redacted_data


class PrivacyUtilityOptimizer:
    """Main privacy-utility trade-off optimizer"""
    
    def __init__(self, preservation_guard, config: Dict[str, Any] = None):
        self.preservation_guard = preservation_guard
        self.config = config or {}
        
        # Initialize components
        self.budget_manager = DifferentialPrivacyBudgetManager(self.config.get('budget_config', {}))
        self.redaction_engine = UtilityAwareRedactionEngine(preservation_guard, self.config.get('redaction_config', {}))
        self.utility_calculator = UtilityCalculator(preservation_guard)
        
        # Optimization parameters
        self.optimization_algorithm = self.config.get('optimization_algorithm', 'multi_objective')
        self.pareto_iterations = self.config.get('pareto_iterations', 100)
        
        # Trade-off history for learning
        self.trade_off_history = deque(maxlen=self.config.get('history_size', 1000))
        self.pareto_front = []
        
        self.logger = logging.getLogger(__name__ + ".PrivacyUtilityOptimizer")
    
    async def optimize_privacy_utility_tradeoff(self, data: Dict[str, Any],
                                              privacy_requirements: Dict[str, Any],
                                              utility_requirements: Dict[str, Any]) -> PrivacyUtilityTradeoff:
        """Optimize privacy-utility trade-off for given requirements"""
        
        start_time = time.perf_counter()
        
        try:
            # Create privacy budget if not exists
            budget_id = privacy_requirements.get('budget_id', 'default')
            if budget_id not in self.budget_manager.privacy_budgets:
                epsilon = privacy_requirements.get('epsilon', 0.5)
                delta = privacy_requirements.get('delta', 1e-6)
                
                # Optimize epsilon and delta
                optimal_epsilon, optimal_delta = self.budget_manager.optimize_epsilon_delta(
                    utility_requirements, privacy_requirements
                )
                
                self.budget_manager.create_budget(budget_id, optimal_epsilon, optimal_delta)
            
            # Find optimal mechanism and parameters
            optimal_mechanism, optimal_params = await self._find_optimal_mechanism(
                data, privacy_requirements, utility_requirements
            )
            
            # Apply privacy mechanism
            private_data = await self._apply_privacy_mechanism(
                data, optimal_mechanism, optimal_params
            )
            
            # Measure actual privacy and utility
            privacy_level = self._measure_privacy_level(data, private_data, optimal_mechanism, optimal_params)
            utility_level = await self._measure_utility_level(data, private_data, utility_requirements)
            
            # Calculate trade-off metrics
            privacy_loss = privacy_requirements.get('max_privacy_loss', 0.0) - privacy_level
            utility_loss = utility_requirements.get('target_utility', 1.0) - utility_level
            trade_off_ratio = utility_level / privacy_level if privacy_level > 0 else 0
            
            # Check constraints
            constraints_satisfied = self._check_constraints(
                privacy_level, utility_level, privacy_requirements, utility_requirements
            )
            
            # Calculate optimization score
            optimization_score = self._calculate_optimization_score(
                privacy_level, utility_level, privacy_requirements, utility_requirements
            )
            
            # Check if Pareto optimal
            pareto_optimal = self._is_pareto_optimal(privacy_level, utility_level)
            
            # Create trade-off result
            tradeoff = PrivacyUtilityTradeoff(
                privacy_level=privacy_level,
                utility_level=utility_level,
                pareto_optimal=pareto_optimal,
                privacy_loss=privacy_loss,
                utility_loss=utility_loss,
                trade_off_ratio=trade_off_ratio,
                mechanism=optimal_mechanism,
                parameters=optimal_params,
                optimization_score=optimization_score,
                constraints_satisfied=constraints_satisfied,
                constraint_violations=[]
            )
            
            # Update history and Pareto front
            self.trade_off_history.append(tradeoff)
            self._update_pareto_front(privacy_level, utility_level)
            
            processing_time = (time.perf_counter() - start_time) * 1000
            self.logger.info(f"Privacy-utility optimization completed in {processing_time:.2f}ms: "
                           f"privacy={privacy_level:.3f}, utility={utility_level:.3f}")
            
            return tradeoff
            
        except Exception as e:
            self.logger.error(f"Privacy-utility optimization failed: {e}")
            raise
    
    async def _find_optimal_mechanism(self, data: Dict[str, Any],
                                     privacy_req: Dict[str, Any],
                                     utility_req: Dict[str, Any]) -> Tuple[PrivacyMechanism, Dict[str, Any]]:
        """Find optimal privacy mechanism and parameters"""
        
        # Test different mechanisms
        mechanisms_to_test = [
            PrivacyMechanism.DIFFERENTIAL_PRIVACY,
            PrivacyMechanism.UTILITY_AWARE_REDACTION,
            PrivacyMechanism.LAPLACE_NOISE,
            PrivacyMechanism.GAUSSIAN_NOISE
        ]
        
        best_mechanism = None
        best_params = {}
        best_score = -float('inf')
        
        for mechanism in mechanisms_to_test:
            try:
                # Generate candidate parameters
                param_candidates = self._generate_parameter_candidates(mechanism, privacy_req, utility_req)
                
                for params in param_candidates:
                    # Test this configuration
                    test_data = await self._apply_privacy_mechanism(data, mechanism, params)
                    
                    # Measure privacy and utility
                    privacy_level = self._measure_privacy_level(data, test_data, mechanism, params)
                    utility_level = await self._measure_utility_level(data, test_data, utility_req)
                    
                    # Calculate score
                    score = self._calculate_mechanism_score(
                        privacy_level, utility_level, privacy_req, utility_req
                    )
                    
                    if score > best_score:
                        best_score = score
                        best_mechanism = mechanism
                        best_params = params
                        
            except Exception as e:
                self.logger.debug(f"Mechanism {mechanism} testing failed: {e}")
        
        if best_mechanism is None:
            # Fallback to utility-aware redaction
            best_mechanism = PrivacyMechanism.UTILITY_AWARE_REDACTION
            best_params = {'target_utility': utility_req.get('target_utility', 0.8)}
        
        return best_mechanism, best_params
    
    def _generate_parameter_candidates(self, mechanism: PrivacyMechanism,
                                     privacy_req: Dict[str, Any],
                                     utility_req: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate parameter candidates for mechanism"""
        
        candidates = []
        
        if mechanism == PrivacyMechanism.DIFFERENTIAL_PRIVACY:
            epsilon_values = [0.1, 0.5, 1.0, 2.0]
            delta_values = [1e-8, 1e-6, 1e-5]
            
            for eps in epsilon_values:
                for delta in delta_values:
                    candidates.append({'epsilon': eps, 'delta': delta})
        
        elif mechanism == PrivacyMechanism.LAPLACE_NOISE:
            scale_values = [0.01, 0.05, 0.1, 0.2]
            for scale in scale_values:
                candidates.append({'scale': scale})
        
        elif mechanism == PrivacyMechanism.GAUSSIAN_NOISE:
            sigma_values = [0.01, 0.05, 0.1, 0.2]
            for sigma in sigma_values:
                candidates.append({'sigma': sigma})
        
        elif mechanism == PrivacyMechanism.UTILITY_AWARE_REDACTION:
            utility_targets = [0.7, 0.8, 0.85, 0.9]
            for target in utility_targets:
                candidates.append({'target_utility': target})
        
        return candidates[:10]  # Limit to avoid explosion
    
    async def _apply_privacy_mechanism(self, data: Dict[str, Any],
                                     mechanism: PrivacyMechanism,
                                     params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply privacy mechanism to data"""
        
        if mechanism == PrivacyMechanism.UTILITY_AWARE_REDACTION:
            redaction_requirements = {
                'required_fields': params.get('required_fields', []),
                'optional_fields': params.get('optional_fields', list(data.keys())),
                'strategy': 'anomaly_aware'
            }
            return await self.redaction_engine.minimize_anomaly_detection_impact(
                data, redaction_requirements, params.get('target_utility', 0.8)
            )
        
        elif mechanism == PrivacyMechanism.DIFFERENTIAL_PRIVACY:
            return self._apply_differential_privacy(data, params)
        
        elif mechanism == PrivacyMechanism.LAPLACE_NOISE:
            return self._apply_laplace_noise(data, params)
        
        elif mechanism == PrivacyMechanism.GAUSSIAN_NOISE:
            return self._apply_gaussian_noise(data, params)
        
        else:
            self.logger.warning(f"Unknown mechanism {mechanism}, returning original data")
            return data
    
    def _apply_differential_privacy(self, data: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply differential privacy mechanism"""
        
        epsilon = params.get('epsilon', 1.0)
        delta = params.get('delta', 1e-6)
        
        private_data = copy.deepcopy(data)
        
        # Add Laplace noise to numeric fields (simplified DP)
        for key, value in private_data.items():
            if isinstance(value, (int, float)):
                # Calculate sensitivity (simplified)
                sensitivity = max(1.0, abs(value) * 0.1)
                
                # Add Laplace noise
                noise = np.random.laplace(0, sensitivity / epsilon)
                private_data[key] = value + noise
        
        return private_data
    
    def _apply_laplace_noise(self, data: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Laplace noise to numeric fields"""
        
        scale = params.get('scale', 0.1)
        noisy_data = copy.deepcopy(data)
        
        for key, value in noisy_data.items():
            if isinstance(value, (int, float)):
                noise = np.random.laplace(0, scale * abs(value))
                noisy_data[key] = value + noise
        
        return noisy_data
    
    def _apply_gaussian_noise(self, data: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply Gaussian noise to numeric fields"""
        
        sigma = params.get('sigma', 0.1)
        noisy_data = copy.deepcopy(data)
        
        for key, value in noisy_data.items():
            if isinstance(value, (int, float)):
                noise = np.random.normal(0, sigma * abs(value))
                noisy_data[key] = value + noise
        
        return noisy_data
    
    def _measure_privacy_level(self, original: Dict[str, Any], private: Dict[str, Any],
                              mechanism: PrivacyMechanism, params: Dict[str, Any]) -> float:
        """Measure privacy level achieved"""
        
        if mechanism == PrivacyMechanism.DIFFERENTIAL_PRIVACY:
            # Privacy level based on epsilon (lower epsilon = higher privacy)
            epsilon = params.get('epsilon', 1.0)
            return max(0.0, 1.0 - epsilon / 2.0)  # Normalize to [0,1]
        
        # For other mechanisms, calculate privacy based on information loss
        total_distance = 0.0
        field_count = 0
        
        for key in original.keys():
            if key in private:
                orig_val = original[key]
                priv_val = private[key]
                
                if isinstance(orig_val, (int, float)) and isinstance(priv_val, (int, float)):
                    if orig_val != 0:
                        distance = abs(orig_val - priv_val) / abs(orig_val)
                    else:
                        distance = abs(priv_val)
                    total_distance += distance
                    field_count += 1
                elif orig_val != priv_val:
                    total_distance += 1.0
                    field_count += 1
        
        if field_count > 0:
            avg_distance = total_distance / field_count
            return min(1.0, avg_distance)  # Higher distance = more privacy
        
        return 0.0
    
    async def _measure_utility_level(self, original: Dict[str, Any], private: Dict[str, Any],
                                   utility_req: Dict[str, Any]) -> float:
        """Measure utility level preserved"""
        
        try:
            # Use preservation guard to assess utility
            assessment = await self.preservation_guard.assess_preservation_impact(
                original, private, "utility_measurement"
            )
            
            return assessment.preservation_effectiveness
            
        except Exception as e:
            self.logger.debug(f"Utility measurement failed: {e}")
            return 0.5
    
    def _calculate_mechanism_score(self, privacy_level: float, utility_level: float,
                                 privacy_req: Dict[str, Any], utility_req: Dict[str, Any]) -> float:
        """Calculate score for mechanism configuration"""
        
        # Multi-objective score combining privacy and utility
        privacy_weight = privacy_req.get('privacy_weight', 0.5)
        utility_weight = utility_req.get('utility_weight', 0.5)
        
        # Normalize weights
        total_weight = privacy_weight + utility_weight
        privacy_weight /= total_weight
        utility_weight /= total_weight
        
        # Calculate weighted score
        score = privacy_weight * privacy_level + utility_weight * utility_level
        
        # Apply penalties for constraint violations
        if privacy_level < privacy_req.get('min_privacy', 0.0):
            score *= 0.5  # Heavy penalty
        
        if utility_level < utility_req.get('min_utility', 0.0):
            score *= 0.5  # Heavy penalty
        
        return score
    
    def _check_constraints(self, privacy_level: float, utility_level: float,
                          privacy_req: Dict[str, Any], utility_req: Dict[str, Any]) -> bool:
        """Check if privacy and utility constraints are satisfied"""
        
        min_privacy = privacy_req.get('min_privacy', 0.0)
        min_utility = utility_req.get('min_utility', 0.0)
        
        return privacy_level >= min_privacy and utility_level >= min_utility
    
    def _calculate_optimization_score(self, privacy_level: float, utility_level: float,
                                    privacy_req: Dict[str, Any], utility_req: Dict[str, Any]) -> float:
        """Calculate overall optimization score"""
        
        # Use mechanism score with additional factors
        base_score = self._calculate_mechanism_score(privacy_level, utility_level, privacy_req, utility_req)
        
        # Bonus for Pareto optimality
        if self._is_pareto_optimal(privacy_level, utility_level):
            base_score *= 1.1
        
        # Bonus for exceeding targets
        target_privacy = privacy_req.get('target_privacy', privacy_level)
        target_utility = utility_req.get('target_utility', utility_level)
        
        if privacy_level > target_privacy:
            base_score *= 1.05
        
        if utility_level > target_utility:
            base_score *= 1.05
        
        return min(1.0, base_score)
    
    def _is_pareto_optimal(self, privacy_level: float, utility_level: float) -> bool:
        """Check if point is Pareto optimal"""
        
        for front_point in self.pareto_front:
            front_privacy, front_utility = front_point
            
            # Check if dominated (worse in both dimensions)
            if front_privacy >= privacy_level and front_utility >= utility_level:
                if front_privacy > privacy_level or front_utility > utility_level:
                    return False
        
        return True
    
    def _update_pareto_front(self, privacy_level: float, utility_level: float):
        """Update Pareto front with new point"""
        
        new_point = (privacy_level, utility_level)
        
        # Remove dominated points
        self.pareto_front = [
            point for point in self.pareto_front
            if not (privacy_level >= point[0] and utility_level >= point[1] and
                   (privacy_level > point[0] or utility_level > point[1]))
        ]
        
        # Add new point if not dominated
        if self._is_pareto_optimal(privacy_level, utility_level):
            self.pareto_front.append(new_point)
    
    def get_pareto_front(self) -> List[Tuple[float, float]]:
        """Get current Pareto front"""
        return self.pareto_front.copy()
    
    def get_trade_off_recommendations(self) -> Dict[str, Any]:
        """Get recommendations for privacy-utility trade-offs"""
        
        if not self.trade_off_history:
            return {'no_history': True}
        
        recent_trades = list(self.trade_off_history)[-50:]  # Last 50 trade-offs
        
        # Calculate average performance by mechanism
        mechanism_performance = defaultdict(list)
        for trade in recent_trades:
            mechanism_performance[trade.mechanism.value].append(trade.optimization_score)
        
        best_mechanism = max(mechanism_performance.keys(),
                           key=lambda m: np.mean(mechanism_performance[m]))
        
        # Calculate trade-off trends
        privacy_levels = [t.privacy_level for t in recent_trades]
        utility_levels = [t.utility_level for t in recent_trades]
        
        recommendations = {
            'best_mechanism': best_mechanism,
            'average_privacy': np.mean(privacy_levels),
            'average_utility': np.mean(utility_levels),
            'pareto_front_size': len(self.pareto_front),
            'mechanism_performance': {
                mech: {
                    'avg_score': np.mean(scores),
                    'std_score': np.std(scores),
                    'count': len(scores)
                } for mech, scores in mechanism_performance.items()
            }
        }
        
        return recommendations


class UtilityCalculator:
    """Calculate utility metrics for privacy-utility trade-offs"""
    
    def __init__(self, preservation_guard):
        self.preservation_guard = preservation_guard
        self.logger = logging.getLogger(__name__ + ".UtilityCalculator")
    
    async def calculate_utility_metrics(self, original: Dict[str, Any], 
                                      processed: Dict[str, Any],
                                      metrics: List[UtilityMetric]) -> Dict[UtilityMetric, UtilityMeasurement]:
        """Calculate specified utility metrics"""
        
        results = {}
        
        for metric in metrics:
            try:
                if metric == UtilityMetric.ANOMALY_DETECTABILITY:
                    measurement = await self._calculate_anomaly_detectability(original, processed)
                elif metric == UtilityMetric.INFORMATION_PRESERVATION:
                    measurement = await self._calculate_information_preservation(original, processed)
                elif metric == UtilityMetric.STATISTICAL_UTILITY:
                    measurement = await self._calculate_statistical_utility(original, processed)
                elif metric == UtilityMetric.PATTERN_PRESERVATION:
                    measurement = await self._calculate_pattern_preservation(original, processed)
                elif metric == UtilityMetric.CORRELATION_MAINTENANCE:
                    measurement = await self._calculate_correlation_maintenance(original, processed)
                elif metric == UtilityMetric.DISTRIBUTIONAL_FIDELITY:
                    measurement = await self._calculate_distributional_fidelity(original, processed)
                else:
                    measurement = UtilityMeasurement(
                        metric_type=metric, value=0.5, confidence=0.0,
                        baseline_value=1.0, preservation_ratio=0.5
                    )
                
                results[metric] = measurement
                
            except Exception as e:
                self.logger.error(f"Utility metric {metric} calculation failed: {e}")
                results[metric] = UtilityMeasurement(
                    metric_type=metric, value=0.0, confidence=0.0,
                    baseline_value=1.0, preservation_ratio=0.0
                )
        
        return results
    
    async def _calculate_anomaly_detectability(self, original: Dict[str, Any],
                                             processed: Dict[str, Any]) -> UtilityMeasurement:
        """Calculate anomaly detectability preservation"""
        
        assessment = await self.preservation_guard.assess_preservation_impact(
            original, processed, "anomaly_detectability"
        )
        
        return UtilityMeasurement(
            metric_type=UtilityMetric.ANOMALY_DETECTABILITY,
            value=assessment.preservation_effectiveness,
            confidence=assessment.confidence_score,
            baseline_value=1.0,
            preservation_ratio=assessment.preservation_effectiveness,
            measurement_method="preservation_guard_assessment"
        )
    
    async def _calculate_information_preservation(self, original: Dict[str, Any],
                                                processed: Dict[str, Any]) -> UtilityMeasurement:
        """Calculate information preservation using entropy measures"""
        
        # Use preservation guard's information analyzer
        info_analyzer = self.preservation_guard.info_analyzer
        info_analysis = info_analyzer.analyze_information_loss(original, processed)
        
        preservation_ratio = 1.0 - info_analysis['total_entropy_loss']
        
        return UtilityMeasurement(
            metric_type=UtilityMetric.INFORMATION_PRESERVATION,
            value=preservation_ratio,
            confidence=0.9,  # High confidence in entropy measures
            baseline_value=1.0,
            preservation_ratio=preservation_ratio,
            component_scores={
                'entropy_preservation': 1.0 - info_analysis['total_entropy_loss'],
                'mutual_information_preservation': 1.0 - info_analysis['mutual_information_loss'],
                'structural_preservation': 1.0 - info_analysis['structural_information_loss']
            },
            measurement_method="entropy_analysis"
        )
    
    async def _calculate_statistical_utility(self, original: Dict[str, Any],
                                           processed: Dict[str, Any]) -> UtilityMeasurement:
        """Calculate statistical utility preservation"""
        
        # Extract numeric values for statistical comparison
        orig_numeric = self._extract_numeric_values(original)
        proc_numeric = self._extract_numeric_values(processed)
        
        if not orig_numeric or not proc_numeric:
            return UtilityMeasurement(
                metric_type=UtilityMetric.STATISTICAL_UTILITY,
                value=0.5, confidence=0.0, baseline_value=1.0, preservation_ratio=0.5
            )
        
        # Statistical tests
        component_scores = {}
        
        # Mean preservation
        orig_mean = np.mean(orig_numeric)
        proc_mean = np.mean(proc_numeric)
        mean_preservation = 1.0 - abs(orig_mean - proc_mean) / (abs(orig_mean) + 1e-10)
        component_scores['mean_preservation'] = max(0.0, mean_preservation)
        
        # Variance preservation
        orig_var = np.var(orig_numeric)
        proc_var = np.var(proc_numeric)
        var_preservation = 1.0 - abs(orig_var - proc_var) / (abs(orig_var) + 1e-10)
        component_scores['variance_preservation'] = max(0.0, var_preservation)
        
        # Distribution similarity (KS test)
        try:
            ks_stat, ks_p = stats.ks_2samp(orig_numeric, proc_numeric)
            distribution_similarity = 1.0 - ks_stat
            component_scores['distribution_similarity'] = max(0.0, distribution_similarity)
        except:
            component_scores['distribution_similarity'] = 0.5
        
        overall_utility = np.mean(list(component_scores.values()))
        
        return UtilityMeasurement(
            metric_type=UtilityMetric.STATISTICAL_UTILITY,
            value=overall_utility,
            confidence=0.8,
            baseline_value=1.0,
            preservation_ratio=overall_utility,
            component_scores=component_scores,
            measurement_method="statistical_tests"
        )
    
    def _extract_numeric_values(self, data: Dict[str, Any]) -> List[float]:
        """Extract all numeric values from data"""
        numeric_values = []
        
        for value in data.values():
            if isinstance(value, (int, float)):
                numeric_values.append(float(value))
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, (int, float)):
                        numeric_values.append(float(item))
        
        return numeric_values
    
    async def _calculate_pattern_preservation(self, original: Dict[str, Any],
                                            processed: Dict[str, Any]) -> UtilityMeasurement:
        """Calculate pattern preservation utility"""
        
        # Analyze structural patterns between original and processed data
        component_scores = {}
        
        # Field presence pattern
        orig_fields = set(original.keys())
        proc_fields = set(processed.keys())
        field_preservation = len(orig_fields & proc_fields) / len(orig_fields) if orig_fields else 1.0
        component_scores['field_presence'] = field_preservation
        
        # Data type pattern preservation
        type_preservation_scores = []
        for field in orig_fields & proc_fields:
            orig_type = type(original[field]).__name__
            proc_type = type(processed[field]).__name__
            type_match = 1.0 if orig_type == proc_type else 0.5  # Partial credit for compatible types
            type_preservation_scores.append(type_match)
        
        type_preservation = np.mean(type_preservation_scores) if type_preservation_scores else 0.0
        component_scores['type_preservation'] = type_preservation
        
        # Value pattern preservation (for numeric data)
        numeric_pattern_scores = []
        for field in orig_fields & proc_fields:
            if isinstance(original[field], (int, float)) and isinstance(processed[field], (int, float)):
                orig_val = original[field]
                proc_val = processed[field]
                
                # Check if the relative magnitude is preserved
                if orig_val != 0:
                    relative_error = abs(orig_val - proc_val) / abs(orig_val)
                    pattern_score = max(0.0, 1.0 - relative_error)
                else:
                    pattern_score = 1.0 if proc_val == 0 else 0.5
                
                numeric_pattern_scores.append(pattern_score)
        
        numeric_pattern_preservation = np.mean(numeric_pattern_scores) if numeric_pattern_scores else 1.0
        component_scores['numeric_patterns'] = numeric_pattern_preservation
        
        # String pattern preservation
        string_pattern_scores = []
        for field in orig_fields & proc_fields:
            if isinstance(original[field], str) and isinstance(processed[field], str):
                orig_str = original[field]
                proc_str = processed[field]
                
                # Check format preservation
                if len(orig_str) > 0 and len(proc_str) > 0:
                    # Length ratio preservation
                    length_ratio = min(len(orig_str), len(proc_str)) / max(len(orig_str), len(proc_str))
                    
                    # Character pattern preservation (simple heuristic)
                    orig_alpha_ratio = sum(c.isalpha() for c in orig_str) / len(orig_str)
                    proc_alpha_ratio = sum(c.isalpha() for c in proc_str) / len(proc_str)
                    alpha_pattern_preservation = 1.0 - abs(orig_alpha_ratio - proc_alpha_ratio)
                    
                    pattern_score = (length_ratio + alpha_pattern_preservation) / 2
                else:
                    pattern_score = 1.0 if len(orig_str) == len(proc_str) == 0 else 0.0
                
                string_pattern_scores.append(pattern_score)
        
        string_pattern_preservation = np.mean(string_pattern_scores) if string_pattern_scores else 1.0
        component_scores['string_patterns'] = string_pattern_preservation
        
        overall_pattern_preservation = np.mean(list(component_scores.values()))
        
        return UtilityMeasurement(
            metric_type=UtilityMetric.PATTERN_PRESERVATION,
            value=overall_pattern_preservation,
            confidence=0.7,
            baseline_value=1.0,
            preservation_ratio=overall_pattern_preservation,
            component_scores=component_scores,
            measurement_method="pattern_analysis"
        )
    
    async def _calculate_correlation_maintenance(self, original: Dict[str, Any],
                                               processed: Dict[str, Any]) -> UtilityMeasurement:
        """Calculate correlation maintenance utility"""
        
        # Extract numeric fields for correlation analysis
        orig_numeric_fields = {}
        proc_numeric_fields = {}
        
        for field, value in original.items():
            if isinstance(value, (int, float)):
                orig_numeric_fields[field] = value
                if field in processed and isinstance(processed[field], (int, float)):
                    proc_numeric_fields[field] = processed[field]
        
        if len(orig_numeric_fields) < 2 or len(proc_numeric_fields) < 2:
            # Not enough numeric fields for correlation analysis
            return UtilityMeasurement(
                metric_type=UtilityMetric.CORRELATION_MAINTENANCE,
                value=1.0,  # No correlations to preserve
                confidence=1.0,
                baseline_value=1.0,
                preservation_ratio=1.0,
                measurement_method="insufficient_data"
            )
        
        # Calculate pairwise correlations
        orig_values = list(orig_numeric_fields.values())
        proc_values = list(proc_numeric_fields.values())
        
        component_scores = {}
        
        if len(orig_values) >= 2 and len(proc_values) >= 2:
            # Calculate correlation matrices
            try:
                # Create correlation matrix for original data
                orig_corr_matrix = np.corrcoef(orig_values)
                proc_corr_matrix = np.corrcoef(proc_values)
                
                # Compare correlation structures
                if orig_corr_matrix.shape == proc_corr_matrix.shape:
                    # Calculate correlation between correlation matrices
                    orig_corr_flat = orig_corr_matrix[np.triu_indices_from(orig_corr_matrix, k=1)]
                    proc_corr_flat = proc_corr_matrix[np.triu_indices_from(proc_corr_matrix, k=1)]
                    
                    if len(orig_corr_flat) > 0:
                        correlation_preservation = np.corrcoef(orig_corr_flat, proc_corr_flat)[0, 1]
                        correlation_preservation = max(0.0, correlation_preservation)
                    else:
                        correlation_preservation = 1.0
                else:
                    correlation_preservation = 0.5  # Partial preservation if dimensions differ
                
                component_scores['correlation_structure'] = correlation_preservation
                
                # Calculate mean absolute difference in correlations
                if orig_corr_matrix.shape == proc_corr_matrix.shape:
                    correlation_diff = np.mean(np.abs(orig_corr_matrix - proc_corr_matrix))
                    correlation_fidelity = max(0.0, 1.0 - correlation_diff)
                    component_scores['correlation_fidelity'] = correlation_fidelity
                
            except Exception as e:
                self.logger.debug(f"Correlation calculation failed: {e}")
                component_scores['correlation_structure'] = 0.5
                component_scores['correlation_fidelity'] = 0.5
        
        # Calculate rank correlation preservation
        try:
            orig_ranks = stats.rankdata(orig_values)
            proc_ranks = stats.rankdata(proc_values)
            
            rank_correlation = stats.spearmanr(orig_ranks, proc_ranks)[0]
            rank_correlation = max(0.0, rank_correlation)
            component_scores['rank_correlation'] = rank_correlation
            
        except Exception as e:
            self.logger.debug(f"Rank correlation calculation failed: {e}")
            component_scores['rank_correlation'] = 0.5
        
        overall_correlation_maintenance = np.mean(list(component_scores.values()))
        
        return UtilityMeasurement(
            metric_type=UtilityMetric.CORRELATION_MAINTENANCE,
            value=overall_correlation_maintenance,
            confidence=0.8,
            baseline_value=1.0,
            preservation_ratio=overall_correlation_maintenance,
            component_scores=component_scores,
            measurement_method="correlation_analysis"
        )
    
    async def _calculate_distributional_fidelity(self, original: Dict[str, Any],
                                                processed: Dict[str, Any]) -> UtilityMeasurement:
        """Calculate distributional fidelity utility"""
        
        # Extract numeric values for distributional analysis
        orig_numeric = self._extract_numeric_values(original)
        proc_numeric = self._extract_numeric_values(processed)
        
        if not orig_numeric or not proc_numeric:
            return UtilityMeasurement(
                metric_type=UtilityMetric.DISTRIBUTIONAL_FIDELITY,
                value=1.0,  # No distribution to preserve
                confidence=1.0,
                baseline_value=1.0,
                preservation_ratio=1.0,
                measurement_method="no_numeric_data"
            )
        
        component_scores = {}
        
        # Statistical moments preservation
        try:
            # Mean preservation
            orig_mean = np.mean(orig_numeric)
            proc_mean = np.mean(proc_numeric)
            mean_fidelity = 1.0 - abs(orig_mean - proc_mean) / (abs(orig_mean) + 1e-10)
            component_scores['mean_fidelity'] = max(0.0, mean_fidelity)
            
            # Variance preservation
            orig_var = np.var(orig_numeric)
            proc_var = np.var(proc_numeric)
            var_fidelity = 1.0 - abs(orig_var - proc_var) / (abs(orig_var) + 1e-10)
            component_scores['variance_fidelity'] = max(0.0, var_fidelity)
            
            # Skewness preservation
            orig_skew = stats.skew(orig_numeric)
            proc_skew = stats.skew(proc_numeric)
            skew_fidelity = 1.0 - abs(orig_skew - proc_skew) / (abs(orig_skew) + 1e-10)
            component_scores['skewness_fidelity'] = max(0.0, skew_fidelity)
            
            # Kurtosis preservation
            orig_kurtosis = stats.kurtosis(orig_numeric)
            proc_kurtosis = stats.kurtosis(proc_numeric)
            kurtosis_fidelity = 1.0 - abs(orig_kurtosis - proc_kurtosis) / (abs(orig_kurtosis) + 1e-10)
            component_scores['kurtosis_fidelity'] = max(0.0, kurtosis_fidelity)
            
        except Exception as e:
            self.logger.debug(f"Statistical moments calculation failed: {e}")
            component_scores.update({
                'mean_fidelity': 0.5,
                'variance_fidelity': 0.5,
                'skewness_fidelity': 0.5,
                'kurtosis_fidelity': 0.5
            })
        
        # Kolmogorov-Smirnov test for distribution similarity
        try:
            ks_stat, ks_p = stats.ks_2samp(orig_numeric, proc_numeric)
            ks_fidelity = 1.0 - ks_stat  # Lower KS statistic = higher fidelity
            component_scores['ks_test_fidelity'] = max(0.0, ks_fidelity)
        except Exception as e:
            self.logger.debug(f"KS test failed: {e}")
            component_scores['ks_test_fidelity'] = 0.5
        
        # Earth Mover's Distance (Wasserstein distance)
        try:
            emd = stats.wasserstein_distance(orig_numeric, proc_numeric)
            # Normalize EMD by the range of original data
            orig_range = np.max(orig_numeric) - np.min(orig_numeric)
            normalized_emd = emd / (orig_range + 1e-10)
            emd_fidelity = max(0.0, 1.0 - normalized_emd)
            component_scores['emd_fidelity'] = emd_fidelity
        except Exception as e:
            self.logger.debug(f"EMD calculation failed: {e}")
            component_scores['emd_fidelity'] = 0.5
        
        # Quantile preservation
        try:
            quantiles = [0.1, 0.25, 0.5, 0.75, 0.9]
            quantile_fidelities = []
            
            for q in quantiles:
                orig_quantile = np.quantile(orig_numeric, q)
                proc_quantile = np.quantile(proc_numeric, q)
                
                quantile_error = abs(orig_quantile - proc_quantile) / (abs(orig_quantile) + 1e-10)
                quantile_fidelity = max(0.0, 1.0 - quantile_error)
                quantile_fidelities.append(quantile_fidelity)
            
            avg_quantile_fidelity = np.mean(quantile_fidelities)
            component_scores['quantile_fidelity'] = avg_quantile_fidelity
            
        except Exception as e:
            self.logger.debug(f"Quantile calculation failed: {e}")
            component_scores['quantile_fidelity'] = 0.5
        
        # Overall distributional fidelity
        overall_fidelity = np.mean(list(component_scores.values()))
        
        return UtilityMeasurement(
            metric_type=UtilityMetric.DISTRIBUTIONAL_FIDELITY,
            value=overall_fidelity,
            confidence=0.9,
            baseline_value=1.0,
            preservation_ratio=overall_fidelity,
            component_scores=component_scores,
            measurement_method="distributional_analysis"
        )


# Main module interface functions
async def optimize_privacy_utility_tradeoff(data: Dict[str, Any],
                                          preservation_guard,
                                          privacy_requirements: Dict[str, Any],
                                          utility_requirements: Dict[str, Any],
                                          config: Dict[str, Any] = None) -> PrivacyUtilityTradeoff:
    """
    Main function to optimize privacy-utility trade-off
    
    Args:
        data: Input data to be processed
        preservation_guard: Anomaly preservation guard instance
        privacy_requirements: Privacy constraints and requirements
        utility_requirements: Utility targets and constraints
        config: Configuration parameters
        
    Returns:
        PrivacyUtilityTradeoff: Optimization result
    """
    optimizer = PrivacyUtilityOptimizer(preservation_guard, config)
    return await optimizer.optimize_privacy_utility_tradeoff(
        data, privacy_requirements, utility_requirements
    )


def create_differential_privacy_budget(budget_id: str, epsilon: float, delta: float,
                                     config: Dict[str, Any] = None) -> PrivacyBudget:
    """
    Create a differential privacy budget
    
    Args:
        budget_id: Unique identifier for the budget
        epsilon: Privacy loss parameter
        delta: Failure probability
        config: Configuration parameters
        
    Returns:
        PrivacyBudget: Created budget instance
    """
    manager = DifferentialPrivacyBudgetManager(config)
    return manager.create_budget(budget_id, epsilon, delta)


async def apply_utility_aware_redaction(data: Dict[str, Any],
                                      preservation_guard,
                                      redaction_requirements: Dict[str, Any],
                                      target_utility: float = 0.85,
                                      config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Apply utility-aware redaction to data
    
    Args:
        data: Input data to be redacted
        preservation_guard: Anomaly preservation guard instance
        redaction_requirements: Redaction requirements and constraints
        target_utility: Target utility preservation level
        config: Configuration parameters
        
    Returns:
        Dict[str, Any]: Redacted data
    """
    engine = UtilityAwareRedactionEngine(preservation_guard, config)
    return await engine.minimize_anomaly_detection_impact(
        data, redaction_requirements, target_utility
    )


async def calculate_utility_metrics(original: Dict[str, Any],
                                  processed: Dict[str, Any],
                                  preservation_guard,
                                  metrics: List[UtilityMetric] = None) -> Dict[UtilityMetric, UtilityMeasurement]:
    """
    Calculate utility metrics for processed data
    
    Args:
        original: Original data before processing
        processed: Processed data after privacy mechanisms
        preservation_guard: Anomaly preservation guard instance
        metrics: List of utility metrics to calculate
        
    Returns:
        Dict[UtilityMetric, UtilityMeasurement]: Calculated utility measurements
    """
    if metrics is None:
        metrics = list(UtilityMetric)
    
    calculator = UtilityCalculator(preservation_guard)
    return await calculator.calculate_utility_metrics(original, processed, metrics)


# Export main classes and functions
__all__ = [
    'PrivacyMechanism',
    'UtilityMetric', 
    'PrivacyBudget',
    'UtilityMeasurement',
    'PrivacyUtilityTradeoff',
    'DifferentialPrivacyBudgetManager',
    'UtilityAwareRedactionEngine',
    'PrivacyUtilityOptimizer',
    'UtilityCalculator',
    'CompositionTracker',
    'optimize_privacy_utility_tradeoff',
    'create_differential_privacy_budget',
    'apply_utility_aware_redaction',
    'calculate_utility_metrics'
]


if __name__ == "__main__":
    # Example usage and testing
    import asyncio
    
    async def example_usage():
        """Example of how to use the privacy-utility optimizer"""
        
        # Mock preservation guard for demonstration
        class MockPreservationGuard:
            async def assess_preservation_impact(self, original, processed, context):
                # Simple mock assessment
                class MockAssessment:
                    preservation_effectiveness = 0.85
                    confidence_score = 0.9
                return MockAssessment()
            
            class MockInfoAnalyzer:
                def analyze_information_loss(self, original, processed):
                    return {
                        'total_entropy_loss': 0.15,
                        'mutual_information_loss': 0.12,
                        'structural_information_loss': 0.08
                    }
            
            info_analyzer = MockInfoAnalyzer()
        
        # Sample data
        sample_data = {
            'user_id': 'user_12345',
            'transaction_amount': 150.50,
            'location': 'New York',
            'timestamp': 1640995200,
            'device_type': 'mobile',
            'risk_score': 0.3
        }
        
        # Privacy requirements
        privacy_req = {
            'epsilon': 1.0,
            'delta': 1e-6,
            'min_privacy': 0.6,
            'privacy_weight': 0.4
        }
        
        # Utility requirements
        utility_req = {
            'target_utility': 0.8,
            'min_utility': 0.7,
            'utility_weight': 0.6
        }
        
        # Configuration
        config = {
            'budget_config': {
                'max_epsilon': 2.0,
                'max_delta': 1e-5
            },
            'redaction_config': {
                'importance_cache_ttl': 300
            }
        }
        
        # Create mock preservation guard
        preservation_guard = MockPreservationGuard()
        
        # Optimize privacy-utility trade-off
        result = await optimize_privacy_utility_tradeoff(
            sample_data, preservation_guard, privacy_req, utility_req, config
        )
        
        print(f"Privacy level: {result.privacy_level:.3f}")
        print(f"Utility level: {result.utility_level:.3f}")
        print(f"Pareto optimal: {result.pareto_optimal}")
        print(f"Mechanism: {result.mechanism.value}")
        print(f"Optimization score: {result.optimization_score:.3f}")
        
        # Apply utility-aware redaction
        redaction_req = {
            'required_fields': ['user_id'],
            'optional_fields': ['location', 'device_type'],
            'strategy': 'anomaly_aware'
        }
        
        redacted_data = await apply_utility_aware_redaction(
            sample_data, preservation_guard, redaction_req, 0.85, config
        )
        
        print("\nRedacted data:")
        for key, value in redacted_data.items():
            print(f"  {key}: {value}")
        
        # Calculate utility metrics
        metrics = [
            UtilityMetric.ANOMALY_DETECTABILITY,
            UtilityMetric.STATISTICAL_UTILITY,
            UtilityMetric.PATTERN_PRESERVATION
        ]
        
        utility_measurements = await calculate_utility_metrics(
            sample_data, redacted_data, preservation_guard, metrics
        )
        
        print("\nUtility measurements:")
        for metric, measurement in utility_measurements.items():
            print(f"  {metric.value}: {measurement.value:.3f} (confidence: {measurement.confidence:.3f})")
    
    # Run example if script is executed directly
    asyncio.run(example_usage())