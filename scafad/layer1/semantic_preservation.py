#!/usr/bin/env python3
"""
SCAFAD Layer 1: Enhanced Semantic Preservation Engine
====================================================

Advanced semantic preservation with behavioral fingerprinting,
formal preservation bounds, and multi-dimensional analysis.

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
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque, Counter
import warnings
import copy
import math

# Scientific computing
try:
    from scipy import stats, signal, spatial
except ImportError:
    pass  # scipy not available; functionality degrades gracefully
try:
    from scipy.spatial.distance import cosine, euclidean, jensen_shannon_divergence
except ImportError:
    pass  # scipy not available; functionality degrades gracefully
try:
    from scipy.stats import entropy, wasserstein_distance, ks_2samp
except ImportError:
    pass  # scipy not available; functionality degrades gracefully
try:
    from sklearn.feature_extraction import DictVectorizer
except ImportError:
    pass  # sklearn not available; functionality degrades gracefully
try:
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
except ImportError:
    pass  # sklearn not available; functionality degrades gracefully
try:
    from sklearn.decomposition import PCA, FastICA
except ImportError:
    pass  # sklearn not available; functionality degrades gracefully
try:
    from sklearn.manifold import TSNE
except ImportError:
    pass  # sklearn not available; functionality degrades gracefully
try:
    from sklearn.cluster import DBSCAN
except ImportError:
    pass  # sklearn not available; functionality degrades gracefully
try:
    from sklearn.metrics import mutual_info_score
except ImportError:
    pass  # sklearn not available; functionality degrades gracefully
import networkx as nx


class SemanticAnalysisMode(Enum):
    """Semantic analysis operation modes"""
    SURFACE = "surface"
    DISTRIBUTIONAL = "distributional"
    BEHAVIORAL = "behavioral"
    STRUCTURAL = "structural"
    COMPREHENSIVE = "comprehensive"


class PreservationConstraintType(Enum):
    """Types of preservation constraints"""
    HARD_BOUND = "hard_bound"
    SOFT_BOUND = "soft_bound"
    STATISTICAL = "statistical"
    INFORMATION_THEORETIC = "information_theoretic"


@dataclass
class BehavioralFingerprint:
    """Multi-dimensional behavioral fingerprint"""
    fingerprint_id: str
    timestamp: float
    
    # Statistical fingerprints
    statistical_signature: Dict[str, float]
    distributional_properties: Dict[str, Any]
    
    # Information-theoretic measures
    entropy_measures: Dict[str, float]
    mutual_information_matrix: np.ndarray
    information_content: float
    
    # Temporal characteristics
    temporal_patterns: Dict[str, Any]
    frequency_signature: Dict[str, float]
    spectral_features: Dict[str, float]
    
    # Structural properties
    graph_topology_features: Dict[str, float]
    field_correlation_matrix: np.ndarray
    dependency_graph: Dict[str, List[str]]
    
    # Semantic features
    semantic_consistency_score: float
    content_coherence_metrics: Dict[str, float]
    pattern_regularity_index: float
    
    # Neural embeddings
    neural_embedding: Optional[np.ndarray] = None
    embedding_confidence: float = 0.0
    
    # Preservation metadata
    preservation_priority: float = 1.0
    critical_features: Set[str] = field(default_factory=set)
    preservation_constraints: Dict[str, float] = field(default_factory=dict)


@dataclass
class PreservationBounds:
    """Formal preservation bounds using information theory"""
    mutual_information_lower_bound: float
    entropy_preservation_ratio: float
    fisher_information_bound: float
    kl_divergence_upper_bound: float
    wasserstein_distance_bound: float
    
    # Theoretical limits
    theoretical_max_preservation: float
    achievable_preservation_range: Tuple[float, float]
    
    # Confidence intervals
    bounds_confidence_level: float
    lower_confidence_bound: float
    upper_confidence_bound: float
    
    # Constraint satisfaction
    hard_constraints: Dict[str, float]
    soft_constraints: Dict[str, float]
    constraint_violations: List[str]


class BehavioralFingerprintEngine:
    """Advanced behavioral fingerprinting for anomaly preservation"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.fingerprint_cache = {}
        self.statistical_baseline = {}
        self.spectral_analyzer = SpectralAnalyzer()
        self.graph_analyzer = StructuralGraphAnalyzer()
        self.semantic_analyzer = ContentSemanticAnalyzer()
        
        # Feature extraction parameters
        self.temporal_window_size = self.config.get('temporal_window', 10)
        self.spectral_bands = self.config.get('spectral_bands', 8)
        self.graph_features = self.config.get('graph_features', 15)
        
        self.logger = logging.getLogger(__name__ + ".BehavioralFingerprintEngine")
    
    async def extract_behavioral_fingerprint(self, data: Dict[str, Any], 
                                           mode: SemanticAnalysisMode = SemanticAnalysisMode.COMPREHENSIVE) -> BehavioralFingerprint:
        """Extract comprehensive behavioral fingerprint"""
        
        fingerprint_id = f"fp_{int(time.time() * 1000)}_{hash(str(data))}"
        start_time = time.perf_counter()
        
        try:
            # Check cache first
            cache_key = self._generate_fingerprint_cache_key(data, mode)
            if cache_key in self.fingerprint_cache:
                return self.fingerprint_cache[cache_key]
            
            # Initialize fingerprint components
            statistical_signature = {}
            distributional_properties = {}
            entropy_measures = {}
            temporal_patterns = {}
            frequency_signature = {}
            spectral_features = {}
            graph_topology_features = {}
            content_coherence_metrics = {}
            
            # Extract statistical fingerprint
            if mode in [SemanticAnalysisMode.DISTRIBUTIONAL, SemanticAnalysisMode.COMPREHENSIVE]:
                statistical_signature = await self._extract_statistical_signature(data)
                distributional_properties = await self._extract_distributional_properties(data)
            
            # Extract information-theoretic fingerprint
            if mode in [SemanticAnalysisMode.BEHAVIORAL, SemanticAnalysisMode.COMPREHENSIVE]:
                entropy_measures = await self._extract_entropy_measures(data)
            
            # Extract temporal fingerprint
            if mode in [SemanticAnalysisMode.BEHAVIORAL, SemanticAnalysisMode.COMPREHENSIVE]:
                temporal_patterns = await self._extract_temporal_patterns(data)
                frequency_signature = await self._extract_frequency_signature(data)
                spectral_features = await self._extract_spectral_features(data)
            
            # Extract structural fingerprint
            if mode in [SemanticAnalysisMode.STRUCTURAL, SemanticAnalysisMode.COMPREHENSIVE]:
                graph_topology_features = await self._extract_graph_topology_features(data)
            
            # Extract semantic fingerprint
            if mode == SemanticAnalysisMode.COMPREHENSIVE:
                content_coherence_metrics = await self._extract_content_coherence_metrics(data)
            
            # Calculate mutual information matrix
            mutual_info_matrix = await self._calculate_mutual_information_matrix(data)
            
            # Calculate field correlation matrix
            field_correlation_matrix = await self._calculate_field_correlation_matrix(data)
            
            # Extract dependency graph
            dependency_graph = await self._extract_dependency_graph(data)
            
            # Calculate semantic consistency
            semantic_consistency_score = await self._calculate_semantic_consistency(data)
            
            # Calculate pattern regularity
            pattern_regularity_index = await self._calculate_pattern_regularity(data)
            
            # Calculate information content
            information_content = self._calculate_total_information_content(entropy_measures)
            
            # Identify critical features
            critical_features = await self._identify_critical_features(data, statistical_signature)
            
            # Create fingerprint
            fingerprint = BehavioralFingerprint(
                fingerprint_id=fingerprint_id,
                timestamp=time.time(),
                statistical_signature=statistical_signature,
                distributional_properties=distributional_properties,
                entropy_measures=entropy_measures,
                mutual_information_matrix=mutual_info_matrix,
                information_content=information_content,
                temporal_patterns=temporal_patterns,
                frequency_signature=frequency_signature,
                spectral_features=spectral_features,
                graph_topology_features=graph_topology_features,
                field_correlation_matrix=field_correlation_matrix,
                dependency_graph=dependency_graph,
                semantic_consistency_score=semantic_consistency_score,
                content_coherence_metrics=content_coherence_metrics,
                pattern_regularity_index=pattern_regularity_index,
                critical_features=critical_features
            )
            
            # Cache the fingerprint
            self.fingerprint_cache[cache_key] = fingerprint
            
            processing_time = (time.perf_counter() - start_time) * 1000
            self.logger.debug(f"Behavioral fingerprint extracted in {processing_time:.2f}ms")
            
            return fingerprint
            
        except Exception as e:
            self.logger.error(f"Behavioral fingerprint extraction failed: {e}")
            raise
    
    async def _extract_statistical_signature(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract statistical signature from data"""
        
        signature = {}
        numeric_values = []
        
        # Extract numeric features
        for key, value in data.items():
            if isinstance(value, (int, float)):
                numeric_values.append(value)
                signature[f"{key}_value"] = float(value)
            elif isinstance(value, str):
                signature[f"{key}_length"] = len(value)
                signature[f"{key}_entropy"] = self._calculate_string_entropy(value)
            elif isinstance(value, (list, tuple)):
                if value:
                    signature[f"{key}_count"] = len(value)
                    if all(isinstance(x, (int, float)) for x in value):
                        signature[f"{key}_mean"] = np.mean(value)
                        signature[f"{key}_std"] = np.std(value)
                        signature[f"{key}_skew"] = stats.skew(value) if len(value) > 2 else 0.0
            elif isinstance(value, dict):
                signature[f"{key}_dict_size"] = len(value)
                signature[f"{key}_depth"] = self._calculate_dict_depth(value)
        
        # Global statistical measures
        if numeric_values:
            signature['global_mean'] = np.mean(numeric_values)
            signature['global_std'] = np.std(numeric_values)
            signature['global_median'] = np.median(numeric_values)
            signature['global_iqr'] = np.percentile(numeric_values, 75) - np.percentile(numeric_values, 25)
            signature['global_skewness'] = stats.skew(numeric_values)
            signature['global_kurtosis'] = stats.kurtosis(numeric_values)
            signature['global_range'] = max(numeric_values) - min(numeric_values)
        
        # Field count and type distribution
        signature['total_fields'] = len(data)
        signature['numeric_field_ratio'] = sum(1 for v in data.values() if isinstance(v, (int, float))) / len(data)
        signature['string_field_ratio'] = sum(1 for v in data.values() if isinstance(v, str)) / len(data)
        signature['complex_field_ratio'] = sum(1 for v in data.values() if isinstance(v, (dict, list))) / len(data)
        
        return signature
    
    async def _extract_distributional_properties(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract distributional properties from data"""
        
        properties = {}
        
        # Extract all numeric sequences
        numeric_sequences = []
        for key, value in data.items():
            if isinstance(value, (int, float)):
                numeric_sequences.append([value])
            elif isinstance(value, (list, tuple)):
                if value and all(isinstance(x, (int, float)) for x in value):
                    numeric_sequences.append(list(value))
        
        if not numeric_sequences:
            return properties
        
        # Flatten all numeric values
        all_values = []
        for seq in numeric_sequences:
            all_values.extend(seq)
        
        if not all_values:
            return properties
        
        try:
            # Test for normality
            _, p_normal = stats.normaltest(all_values)
            properties['normality_p_value'] = p_normal
            properties['is_normal'] = p_normal > 0.05
            
            # Test for exponential distribution
            _, p_exp = stats.kstest(all_values, 'expon')
            properties['exponential_p_value'] = p_exp
            properties['is_exponential'] = p_exp > 0.05
            
            # Calculate distribution moments
            properties['mean'] = np.mean(all_values)
            properties['variance'] = np.var(all_values)
            properties['skewness'] = stats.skew(all_values)
            properties['kurtosis'] = stats.kurtosis(all_values)
            
            # Percentile analysis
            percentiles = [5, 10, 25, 50, 75, 90, 95, 99]
            properties['percentiles'] = {
                f'p{p}': np.percentile(all_values, p) for p in percentiles
            }
            
            # Outlier detection
            q75, q25 = np.percentile(all_values, [75, 25])
            iqr = q75 - q25
            lower_bound = q25 - 1.5 * iqr
            upper_bound = q75 + 1.5 * iqr
            outliers = [x for x in all_values if x < lower_bound or x > upper_bound]
            properties['outlier_count'] = len(outliers)
            properties['outlier_ratio'] = len(outliers) / len(all_values)
            
            # Multimodality test
            properties['multimodal_score'] = self._calculate_multimodality_score(all_values)
            
        except Exception as e:
            self.logger.debug(f"Distribution analysis failed: {e}")
            properties['analysis_failed'] = True
        
        return properties
    
    async def _extract_entropy_measures(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract entropy-based measures"""
        
        measures = {}
        
        # Shannon entropy for each field
        for key, value in data.items():
            if isinstance(value, str):
                measures[f"{key}_shannon_entropy"] = self._calculate_string_entropy(value)
            elif isinstance(value, (list, tuple)):
                if value:
                    measures[f"{key}_sequence_entropy"] = self._calculate_sequence_entropy(value)
            elif isinstance(value, dict):
                measures[f"{key}_structure_entropy"] = self._calculate_structure_entropy(value)
        
        # Global entropy measures
        all_text = json.dumps(data, sort_keys=True, default=str)
        measures['global_shannon_entropy'] = self._calculate_string_entropy(all_text)
        
        # Conditional entropy between fields
        field_pairs = [(k1, k2) for k1 in data.keys() for k2 in data.keys() if k1 != k2]
        conditional_entropies = []
        
        for k1, k2 in field_pairs[:10]:  # Limit to avoid explosion
            cond_entropy = self._calculate_conditional_entropy(data[k1], data[k2])
            if cond_entropy is not None:
                conditional_entropies.append(cond_entropy)
                measures[f"conditional_entropy_{k1}_{k2}"] = cond_entropy
        
        if conditional_entropies:
            measures['avg_conditional_entropy'] = np.mean(conditional_entropies)
            measures['max_conditional_entropy'] = np.max(conditional_entropies)
        
        # Cross-entropy measures
        measures['cross_entropy_complexity'] = self._calculate_cross_entropy_complexity(data)
        
        return measures
    
    async def _extract_temporal_patterns(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract temporal patterns from data"""
        
        patterns = {}
        
        # Look for timestamp fields
        timestamp_fields = []
        for key, value in data.items():
            if 'time' in key.lower() or 'timestamp' in key.lower():
                if isinstance(value, (int, float)):
                    timestamp_fields.append((key, value))
        
        if timestamp_fields:
            timestamps = [v for _, v in timestamp_fields]
            patterns['timestamp_count'] = len(timestamps)
            patterns['timestamp_range'] = max(timestamps) - min(timestamps) if len(timestamps) > 1 else 0
            patterns['timestamp_variance'] = np.var(timestamps) if len(timestamps) > 1 else 0
        
        # Look for sequential patterns
        sequences = []
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 3:
                if all(isinstance(x, (int, float)) for x in value):
                    sequences.append((key, value))
        
        if sequences:
            patterns['sequence_count'] = len(sequences)
            
            # Analyze each sequence
            for seq_name, seq_values in sequences:
                # Trend analysis
                if len(seq_values) > 2:
                    trend_slope = self._calculate_trend_slope(seq_values)
                    patterns[f"{seq_name}_trend_slope"] = trend_slope
                    patterns[f"{seq_name}_trend_strength"] = abs(trend_slope)
                
                # Periodicity detection
                periodicity = self._detect_periodicity(seq_values)
                if periodicity:
                    patterns[f"{seq_name}_period"] = periodicity
                
                # Volatility measure
                if len(seq_values) > 1:
                    volatility = np.std(np.diff(seq_values))
                    patterns[f"{seq_name}_volatility"] = volatility
        
        # Duration patterns
        duration_fields = [k for k in data.keys() if 'duration' in k.lower()]
        if duration_fields:
            durations = []
            for field in duration_fields:
                value = data[field]
                if isinstance(value, (int, float)):
                    durations.append(value)
            
            if durations:
                patterns['duration_pattern_mean'] = np.mean(durations)
                patterns['duration_pattern_std'] = np.std(durations)
                patterns['duration_pattern_cv'] = np.std(durations) / np.mean(durations) if np.mean(durations) > 0 else 0
        
        return patterns
    
    async def _extract_frequency_signature(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract frequency domain signature"""
        
        signature = {}
        
        # Find numeric sequences suitable for frequency analysis
        numeric_sequences = []
        for key, value in data.items():
            if isinstance(value, list) and len(value) >= 8:  # Minimum for meaningful FFT
                if all(isinstance(x, (int, float)) for x in value):
                    numeric_sequences.append((key, value))
        
        if not numeric_sequences:
            return signature
        
        for seq_name, seq_values in numeric_sequences:
            try:
                # Compute FFT
                fft_result = np.fft.fft(seq_values)
                magnitudes = np.abs(fft_result)
                frequencies = np.fft.fftfreq(len(seq_values))
                
                # Extract frequency domain features
                signature[f"{seq_name}_dominant_freq"] = frequencies[np.argmax(magnitudes[1:])] if len(magnitudes) > 1 else 0
                signature[f"{seq_name}_spectral_centroid"] = np.sum(frequencies * magnitudes) / np.sum(magnitudes) if np.sum(magnitudes) > 0 else 0
                signature[f"{seq_name}_spectral_spread"] = np.sqrt(np.sum(((frequencies - signature[f"{seq_name}_spectral_centroid"]) ** 2) * magnitudes) / np.sum(magnitudes)) if np.sum(magnitudes) > 0 else 0
                signature[f"{seq_name}_spectral_rolloff"] = self._calculate_spectral_rolloff(frequencies, magnitudes)
                signature[f"{seq_name}_spectral_flatness"] = self._calculate_spectral_flatness(magnitudes)
                
                # Energy in different frequency bands
                total_energy = np.sum(magnitudes ** 2)
                if total_energy > 0:
                    low_freq_energy = np.sum(magnitudes[:len(magnitudes)//4] ** 2) / total_energy
                    mid_freq_energy = np.sum(magnitudes[len(magnitudes)//4:3*len(magnitudes)//4] ** 2) / total_energy
                    high_freq_energy = np.sum(magnitudes[3*len(magnitudes)//4:] ** 2) / total_energy
                    
                    signature[f"{seq_name}_low_freq_energy"] = low_freq_energy
                    signature[f"{seq_name}_mid_freq_energy"] = mid_freq_energy
                    signature[f"{seq_name}_high_freq_energy"] = high_freq_energy
                
            except Exception as e:
                self.logger.debug(f"Frequency analysis failed for {seq_name}: {e}")
        
        return signature
    
    async def _extract_spectral_features(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract advanced spectral features"""
        return await self.spectral_analyzer.extract_features(data)
    
    async def _extract_graph_topology_features(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract graph topology features"""
        return await self.graph_analyzer.extract_topology_features(data)
    
    async def _extract_content_coherence_metrics(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract content coherence metrics"""
        return await self.semantic_analyzer.extract_coherence_metrics(data)
    
    async def _calculate_mutual_information_matrix(self, data: Dict[str, Any]) -> np.ndarray:
        """Calculate mutual information matrix between fields"""
        
        fields = list(data.keys())
        n_fields = len(fields)
        
        if n_fields < 2:
            return np.array([[1.0]])
        
        mi_matrix = np.zeros((n_fields, n_fields))
        
        for i, field1 in enumerate(fields):
            for j, field2 in enumerate(fields):
                if i == j:
                    mi_matrix[i, j] = 1.0
                elif i < j:  # Calculate only upper triangle
                    mi = self._calculate_mutual_info_between_fields(data[field1], data[field2])
                    mi_matrix[i, j] = mi
                    mi_matrix[j, i] = mi  # Symmetric
        
        return mi_matrix
    
    async def _calculate_field_correlation_matrix(self, data: Dict[str, Any]) -> np.ndarray:
        """Calculate correlation matrix between fields"""
        
        # Extract numeric values for correlation calculation
        numeric_fields = {}
        for key, value in data.items():
            if isinstance(value, (int, float)):
                numeric_fields[key] = [value]
            elif isinstance(value, (list, tuple)):
                if value and all(isinstance(x, (int, float)) for x in value):
                    numeric_fields[key] = list(value)
        
        if len(numeric_fields) < 2:
            return np.array([[1.0]])
        
        # Convert to matrix format
        field_names = list(numeric_fields.keys())
        max_length = max(len(values) for values in numeric_fields.values())
        
        # Pad sequences to same length
        matrix_data = []
        for field in field_names:
            values = numeric_fields[field]
            padded = values + [values[-1]] * (max_length - len(values))  # Repeat last value
            matrix_data.append(padded)
        
        matrix_data = np.array(matrix_data)
        
        try:
            correlation_matrix = np.corrcoef(matrix_data)
            return correlation_matrix
        except Exception as e:
            self.logger.debug(f"Correlation matrix calculation failed: {e}")
            return np.eye(len(field_names))
    
    async def _extract_dependency_graph(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Extract dependency relationships between fields"""
        
        dependencies = {}
        
        # Simple dependency detection based on field names and values
        for key, value in data.items():
            deps = []
            
            # Check for naming patterns indicating dependencies
            for other_key in data.keys():
                if key != other_key:
                    # Check if field names suggest dependency
                    if key.lower() in other_key.lower() or other_key.lower() in key.lower():
                        deps.append(other_key)
                    # Check for common prefixes/suffixes
                    elif self._have_common_prefix_suffix(key, other_key):
                        deps.append(other_key)
            
            # Check for value-based dependencies (for numeric fields)
            if isinstance(value, (int, float)):
                for other_key, other_value in data.items():
                    if key != other_key and isinstance(other_value, (int, float)):
                        # Check if values have mathematical relationship
                        if self._detect_mathematical_relationship(value, other_value):
                            if other_key not in deps:
                                deps.append(other_key)
            
            dependencies[key] = deps
        
        return dependencies
    
    async def _calculate_semantic_consistency(self, data: Dict[str, Any]) -> float:
        """Calculate semantic consistency score"""
        
        consistency_scores = []
        
        # Type consistency
        type_counts = defaultdict(int)
        for value in data.values():
            type_counts[type(value).__name__] += 1
        
        total_fields = len(data)
        if total_fields > 0:
            # Calculate type diversity (lower is more consistent)
            type_diversity = len(type_counts) / total_fields
            type_consistency = 1.0 - min(1.0, type_diversity)
            consistency_scores.append(type_consistency)
        
        # Naming consistency
        field_names = list(data.keys())
        naming_consistency = self._calculate_naming_consistency(field_names)
        consistency_scores.append(naming_consistency)
        
        # Value range consistency (for numeric fields)
        numeric_values = [v for v in data.values() if isinstance(v, (int, float))]
        if len(numeric_values) > 1:
            # Coefficient of variation as consistency measure
            cv = np.std(numeric_values) / np.mean(numeric_values) if np.mean(numeric_values) > 0 else 0
            range_consistency = 1.0 / (1.0 + cv)  # Higher CV = lower consistency
            consistency_scores.append(range_consistency)
        
        # Structural consistency (for nested objects)
        nested_objects = [v for v in data.values() if isinstance(v, dict)]
        if len(nested_objects) > 1:
            structure_consistency = self._calculate_structure_consistency(nested_objects)
            consistency_scores.append(structure_consistency)
        
        return np.mean(consistency_scores) if consistency_scores else 1.0
    
    async def _calculate_pattern_regularity(self, data: Dict[str, Any]) -> float:
        """Calculate pattern regularity index"""
        
        regularity_scores = []
        
        # Field name pattern regularity
        field_names = list(data.keys())
        name_regularity = self._calculate_name_pattern_regularity(field_names)
        regularity_scores.append(name_regularity)
        
        # Value pattern regularity
        for key, value in data.items():
            if isinstance(value, (list, tuple)) and len(value) > 3:
                if all(isinstance(x, (int, float)) for x in value):
                    sequence_regularity = self._calculate_sequence_regularity(value)
                    regularity_scores.append(sequence_regularity)
            elif isinstance(value, str) and len(value) > 10:
                string_regularity = self._calculate_string_pattern_regularity(value)
                regularity_scores.append(string_regularity)
        
        return np.mean(regularity_scores) if regularity_scores else 0.5
    
    async def _identify_critical_features(self, data: Dict[str, Any], 
                                        statistical_signature: Dict[str, float]) -> Set[str]:
        """Identify critical features for anomaly detection"""
        
        critical_features = set()
        
        # High variance features (likely important for anomaly detection)
        variance_threshold = np.mean(list(statistical_signature.values())) + np.std(list(statistical_signature.values()))
        
        for key, value in data.items():
            # Features with high information content
            if isinstance(value, (int, float)):
                if abs(value) > variance_threshold:
                    critical_features.add(key)
            
            # Features indicating anomalous behavior patterns
            if any(anomaly_keyword in key.lower() for anomaly_keyword in 
                   ['error', 'fail', 'timeout', 'spike', 'anomaly', 'violation', 'breach']):
                critical_features.add(key)
            
            # Features with extreme values
            if isinstance(value, (list, tuple)) and value:
                if all(isinstance(x, (int, float)) for x in value):
                    if np.std(value) > np.mean(value):  # High coefficient of variation
                        critical_features.add(key)
            
            # Temporal features (often critical for anomaly detection)
            if any(temporal_keyword in key.lower() for temporal_keyword in 
                   ['time', 'duration', 'latency', 'delay', 'interval']):
                critical_features.add(key)
        
        return critical_features
    
    def _calculate_total_information_content(self, entropy_measures: Dict[str, float]) -> float:
        """Calculate total information content from entropy measures"""
        
        if not entropy_measures:
            return 0.0
        
        # Weight different entropy types
        weights = {
            'shannon_entropy': 0.4,
            'conditional_entropy': 0.3,
            'cross_entropy': 0.2,
            'sequence_entropy': 0.1
        }
        
        total_content = 0.0
        total_weight = 0.0
        
        for measure_name, value in entropy_measures.items():
            weight = 0.1  # Default weight
            
            for entropy_type, type_weight in weights.items():
                if entropy_type in measure_name:
                    weight = type_weight
                    break
            
            total_content += value * weight
            total_weight += weight
        
        return total_content / total_weight if total_weight > 0 else 0.0
    
    # Helper methods for calculations
    def _calculate_string_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of string"""
        if not text:
            return 0.0
        
        char_counts = Counter(text)
        text_length = len(text)
        
        entropy = 0.0
        for count in char_counts.values():
            prob = count / text_length
            if prob > 0:
                entropy -= prob * math.log2(prob)
        
        return entropy
    
    def _calculate_sequence_entropy(self, sequence: List[Any]) -> float:
        """Calculate entropy of sequence"""
        if not sequence:
            return 0.0
        
        # Convert to string representation for entropy calculation
        str_sequence = [str(item) for item in sequence]
        combined_string = ''.join(str_sequence)
        
        return self._calculate_string_entropy(combined_string)
    
    def _calculate_structure_entropy(self, structure: Dict[str, Any]) -> float:
        """Calculate entropy of nested structure"""
        if not structure:
            return 0.0
        
        # Flatten structure and calculate entropy
        flattened = json.dumps(structure, sort_keys=True, default=str)
        return self._calculate_string_entropy(flattened)
    
    def _calculate_conditional_entropy(self, field1: Any, field2: Any) -> Optional[float]:
        """Calculate conditional entropy H(X|Y)"""
        try:
            # Convert to strings for analysis
            str1 = str(field1) if field1 is not None else ""
            str2 = str(field2) if field2 is not None else ""
            
            if not str1 or not str2:
                return None
            
            # Simple conditional entropy approximation
            joint_string = str1 + str2
            joint_entropy = self._calculate_string_entropy(joint_string)
            field2_entropy = self._calculate_string_entropy(str2)
            
            conditional_entropy = joint_entropy - field2_entropy
            return max(0.0, conditional_entropy)
            
        except Exception:
            return None
    
    def _calculate_cross_entropy_complexity(self, data: Dict[str, Any]) -> float:
        """Calculate cross-entropy complexity measure"""
        
        # Extract all string values
        text_values = []
        for value in data.values():
            if isinstance(value, str):
                text_values.append(value)
            elif isinstance(value, (list, tuple)):
                text_values.extend([str(item) for item in value])
        
        if len(text_values) < 2:
            return 0.0
        
        # Calculate pairwise cross-entropies
        cross_entropies = []
        for i in range(len(text_values)):
            for j in range(i + 1, len(text_values)):
                combined = text_values[i] + text_values[j]
                cross_entropy = self._calculate_string_entropy(combined)
                cross_entropies.append(cross_entropy)
        
        return np.mean(cross_entropies) if cross_entropies else 0.0
    
    def _calculate_multimodality_score(self, values: List[float]) -> float:
        """Calculate multimodality score using kernel density estimation"""
        try:
            try:
                from scipy.stats import gaussian_kde
            except ImportError:
                pass  # scipy not available; functionality degrades gracefully
            
            if len(values) < 10:
                return 0.0
            
            # Create KDE
            kde = gaussian_kde(values)
            
            # Sample points for peak detection
            x_range = np.linspace(min(values), max(values), 100)
            density = kde(x_range)
            
            # Find peaks (simplified)
            peaks = []
            for i in range(1, len(density) - 1):
                if density[i] > density[i-1] and density[i] > density[i+1]:
                    peaks.append((x_range[i], density[i]))
            
            # Multimodality score based on number of significant peaks
            significant_peaks = [p for p in peaks if p[1] > np.max(density) * 0.1]
            multimodal_score = min(1.0, len(significant_peaks) / 3.0)  # Normalize
            
            return multimodal_score
            
        except Exception:
            return 0.0
    
    def _calculate_trend_slope(self, sequence: List[float]) -> float:
        """Calculate trend slope of sequence"""
        if len(sequence) < 2:
            return 0.0
        
        x = np.arange(len(sequence))
        slope, _ = np.polyfit(x, sequence, 1)
        return slope
    
    def _detect_periodicity(self, sequence: List[float]) -> Optional[int]:
        """Detect periodicity in sequence using autocorrelation"""
        if len(sequence) < 6:
            return None
        
        try:
            # Calculate autocorrelation
            autocorr = np.correlate(sequence, sequence, mode='full')
            autocorr = autocorr[autocorr.size // 2:]
            
            # Find peaks in autocorrelation (excluding lag 0)
            if len(autocorr) > 3:
                peaks = []
                for i in range(2, min(len(autocorr), len(sequence) // 2)):
                    if autocorr[i] > autocorr[i-1] and autocorr[i] > autocorr[i+1]:
                        if autocorr[i] > np.max(autocorr) * 0.3:  # Significant peak
                            peaks.append(i)
                
                # Return first significant period
                return peaks[0] if peaks else None
            
        except Exception:
            pass
        
        return None
    
    def _calculate_spectral_rolloff(self, frequencies: np.ndarray, magnitudes: np.ndarray) -> float:
        """Calculate spectral rolloff frequency"""
        try:
            # Find frequency below which 85% of energy is contained
            total_energy = np.sum(magnitudes ** 2)
            cumulative_energy = np.cumsum(magnitudes ** 2)
            
            rolloff_threshold = 0.85 * total_energy
            rolloff_idx = np.where(cumulative_energy >= rolloff_threshold)[0]
            
            if len(rolloff_idx) > 0:
                return frequencies[rolloff_idx[0]]
            else:
                return frequencies[-1] if len(frequencies) > 0 else 0.0
                
        except Exception:
            return 0.0
    
    def _calculate_spectral_flatness(self, magnitudes: np.ndarray) -> float:
        """Calculate spectral flatness (Wiener entropy)"""
        try:
            # Avoid log(0) by adding small epsilon
            epsilon = 1e-10
            magnitudes = magnitudes + epsilon
            
            # Geometric mean / Arithmetic mean
            geometric_mean = np.exp(np.mean(np.log(magnitudes)))
            arithmetic_mean = np.mean(magnitudes)
            
            if arithmetic_mean > 0:
                return geometric_mean / arithmetic_mean
            else:
                return 0.0
                
        except Exception:
            return 0.0
    
    def _calculate_dict_depth(self, d: Dict[str, Any], current_depth: int = 0) -> int:
        """Calculate maximum depth of nested dictionary"""
        if not isinstance(d, dict):
            return current_depth
        
        if not d:
            return current_depth
        
        max_depth = current_depth
        for value in d.values():
            if isinstance(value, dict):
                depth = self._calculate_dict_depth(value, current_depth + 1)
                max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _calculate_mutual_info_between_fields(self, field1: Any, field2: Any) -> float:
        """Calculate mutual information between two fields"""
        try:
            # Convert to comparable format
            str1 = str(field1) if field1 is not None else ""
            str2 = str(field2) if field2 is not None else ""
            
            if not str1 or not str2:
                return 0.0
            
            # Use character-level mutual information
            chars1 = list(str1)
            chars2 = list(str2)
            
            # Align sequences
            min_len = min(len(chars1), len(chars2))
            if min_len == 0:
                return 0.0
            
            chars1 = chars1[:min_len]
            chars2 = chars2[:min_len]
            
            # Calculate mutual information
            return mutual_info_score(chars1, chars2)
        except Exception as e:
            self.logger.debug(f"Mutual information calculation failed: {e}")
            return 0.0
    
    def _have_common_prefix_suffix(self, str1: str, str2: str) -> bool:
        """Check if strings have common prefix or suffix"""
        if len(str1) < 2 or len(str2) < 2:
            return False
        
        # Check prefix (first 3 characters)
        if str1[:3].lower() == str2[:3].lower():
            return True
        
        # Check suffix (last 3 characters)
        if str1[-3:].lower() == str2[-3:].lower():
            return True
        
        return False
    
    def _detect_mathematical_relationship(self, val1: float, val2: float) -> bool:
        """Detect if two values have mathematical relationship"""
        if val1 == 0 or val2 == 0:
            return val1 == val2
        
        # Check for simple ratios
        ratio = val1 / val2
        simple_ratios = [0.5, 2.0, 1.5, 1.0/3.0, 3.0, 0.25, 4.0]
        
        for simple_ratio in simple_ratios:
            if abs(ratio - simple_ratio) < 0.1:
                return True
        
        # Check for additive relationships
        diff = abs(val1 - val2)
        avg = (abs(val1) + abs(val2)) / 2
        
        if avg > 0 and diff / avg < 0.1:  # Within 10%
            return True
        
        return False
    
    def _calculate_naming_consistency(self, field_names: List[str]) -> float:
        """Calculate consistency of field naming patterns"""
        if len(field_names) < 2:
            return 1.0
        
        # Check for common patterns
        patterns = {
            'camelCase': 0,
            'snake_case': 0,
            'kebab-case': 0,
            'PascalCase': 0,
            'lowercase': 0,
            'UPPERCASE': 0
        }
        
        for name in field_names:
            if '_' in name and name.lower() == name:
                patterns['snake_case'] += 1
            elif '-' in name:
                patterns['kebab-case'] += 1
            elif name[0].isupper() and any(c.isupper() for c in name[1:]):
                patterns['PascalCase'] += 1
            elif name[0].islower() and any(c.isupper() for c in name[1:]):
                patterns['camelCase'] += 1
            elif name.isupper():
                patterns['UPPERCASE'] += 1
            elif name.islower():
                patterns['lowercase'] += 1
        
        # Calculate consistency as max pattern ratio
        max_pattern_count = max(patterns.values())
        consistency = max_pattern_count / len(field_names)
        
        return consistency
    
    def _calculate_structure_consistency(self, nested_objects: List[Dict[str, Any]]) -> float:
        """Calculate structural consistency between nested objects"""
        if len(nested_objects) < 2:
            return 1.0
        
        # Compare key sets
        key_sets = [set(obj.keys()) for obj in nested_objects]
        
        # Calculate Jaccard similarity between key sets
        similarities = []
        for i in range(len(key_sets)):
            for j in range(i + 1, len(key_sets)):
                intersection = len(key_sets[i] & key_sets[j])
                union = len(key_sets[i] | key_sets[j])
                similarity = intersection / union if union > 0 else 0
                similarities.append(similarity)
        
        return np.mean(similarities) if similarities else 0.0
    
    def _calculate_name_pattern_regularity(self, field_names: List[str]) -> float:
        """Calculate regularity of naming patterns"""
        if len(field_names) < 2:
            return 1.0
        
        # Check for common prefixes/suffixes
        prefix_groups = defaultdict(list)
        suffix_groups = defaultdict(list)
        
        for name in field_names:
            if len(name) >= 3:
                prefix = name[:3]
                suffix = name[-3:]
                prefix_groups[prefix].append(name)
                suffix_groups[suffix].append(name)
        
        # Calculate regularity based on grouping
        max_prefix_group = max(len(group) for group in prefix_groups.values()) if prefix_groups else 1
        max_suffix_group = max(len(group) for group in suffix_groups.values()) if suffix_groups else 1
        
        prefix_regularity = max_prefix_group / len(field_names)
        suffix_regularity = max_suffix_group / len(field_names)
        
        return max(prefix_regularity, suffix_regularity)
    
    def _calculate_sequence_regularity(self, sequence: List[float]) -> float:
        """Calculate regularity of numeric sequence"""
        if len(sequence) < 3:
            return 0.5
        
        # Check for arithmetic progression
        diffs = np.diff(sequence)
        diff_variance = np.var(diffs)
        diff_mean = np.mean(np.abs(diffs))
        
        if diff_mean > 0:
            arithmetic_regularity = 1.0 / (1.0 + diff_variance / diff_mean)
        else:
            arithmetic_regularity = 1.0
        
        # Check for geometric progression
        if all(x > 0 for x in sequence):
            ratios = [sequence[i+1] / sequence[i] for i in range(len(sequence)-1)]
            ratio_variance = np.var(ratios)
            ratio_mean = np.mean(ratios)
            
            if ratio_mean > 0:
                geometric_regularity = 1.0 / (1.0 + ratio_variance / ratio_mean)
            else:
                geometric_regularity = 0.0
        else:
            geometric_regularity = 0.0
        
        return max(arithmetic_regularity, geometric_regularity)
    
    def _calculate_string_pattern_regularity(self, text: str) -> float:
        """Calculate regularity of patterns in string"""
        if len(text) < 10:
            return 0.5
        
        # Check for repeated substrings
        substring_counts = defaultdict(int)
        
        # Check substrings of length 2-5
        for length in range(2, min(6, len(text))):
            for i in range(len(text) - length + 1):
                substring = text[i:i+length]
                substring_counts[substring] += 1
        
        # Calculate regularity based on repetition
        if substring_counts:
            max_count = max(substring_counts.values())
            total_substrings = sum(substring_counts.values())
            regularity = max_count / total_substrings
        else:
            regularity = 0.0
        
        return min(1.0, regularity * 2)  # Scale up since perfect regularity is rare
    
    def _generate_fingerprint_cache_key(self, data: Dict[str, Any], mode: SemanticAnalysisMode) -> str:
        """Generate cache key for fingerprint"""
        data_hash = hashlib.md5(str(sorted(data.items())).encode()).hexdigest()
        return f"{mode.value}_{data_hash[:16]}"


class SpectralAnalyzer:
    """Advanced spectral analysis for temporal patterns"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SpectralAnalyzer")
    
    async def extract_features(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract spectral features from data"""
        
        features = {}
        
        # Find numeric sequences for spectral analysis
        sequences = []
        for key, value in data.items():
            if isinstance(value, list) and len(value) >= 8:
                if all(isinstance(x, (int, float)) for x in value):
                    sequences.append((key, value))
        
        if not sequences:
            return features
        
        for seq_name, seq_values in sequences:
            try:
                # Compute power spectral density
                freqs, psd = signal.periodogram(seq_values)
                
                # Extract spectral features
                features[f"{seq_name}_spectral_energy"] = np.sum(psd)
                features[f"{seq_name}_spectral_centroid"] = np.sum(freqs * psd) / np.sum(psd) if np.sum(psd) > 0 else 0
                features[f"{seq_name}_spectral_bandwidth"] = np.sqrt(np.sum(((freqs - features[f"{seq_name}_spectral_centroid"]) ** 2) * psd) / np.sum(psd)) if np.sum(psd) > 0 else 0
                
                # Peak frequency
                peak_idx = np.argmax(psd)
                features[f"{seq_name}_peak_frequency"] = freqs[peak_idx] if len(freqs) > peak_idx else 0
                
                # Spectral entropy
                normalized_psd = psd / np.sum(psd) if np.sum(psd) > 0 else psd
                spectral_entropy = -np.sum(normalized_psd * np.log2(normalized_psd + 1e-10))
                features[f"{seq_name}_spectral_entropy"] = spectral_entropy
                
            except Exception as e:
                self.logger.debug(f"Spectral analysis failed for {seq_name}: {e}")
        
        return features


class StructuralGraphAnalyzer:
    """Graph-based structural analysis"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".StructuralGraphAnalyzer")
    
    async def extract_topology_features(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract graph topology features"""
        
        features = {}
        
        try:
            # Build graph from data structure
            G = self._build_data_graph(data)
            
            if G.number_of_nodes() == 0:
                return features
            
            # Basic graph metrics
            features['node_count'] = G.number_of_nodes()
            features['edge_count'] = G.number_of_edges()
            features['density'] = nx.density(G)
            
            # Centrality measures
            if G.number_of_nodes() > 1:
                degree_centrality = nx.degree_centrality(G)
                features['avg_degree_centrality'] = np.mean(list(degree_centrality.values()))
                features['max_degree_centrality'] = np.max(list(degree_centrality.values()))
                
                if nx.is_connected(G):
                    betweenness_centrality = nx.betweenness_centrality(G)
                    features['avg_betweenness_centrality'] = np.mean(list(betweenness_centrality.values()))
                    
                    closeness_centrality = nx.closeness_centrality(G)
                    features['avg_closeness_centrality'] = np.mean(list(closeness_centrality.values()))
            
            # Clustering coefficient
            clustering = nx.clustering(G)
            features['avg_clustering'] = np.mean(list(clustering.values()))
            
            # Path length (if connected)
            if nx.is_connected(G):
                features['avg_shortest_path_length'] = nx.average_shortest_path_length(G)
                features['diameter'] = nx.diameter(G)
            
            # Degree distribution
            degrees = [d for n, d in G.degree()]
            if degrees:
                features['degree_mean'] = np.mean(degrees)
                features['degree_std'] = np.std(degrees)
                features['degree_max'] = np.max(degrees)
        
        except Exception as e:
            self.logger.debug(f"Graph topology analysis failed: {e}")
        
        return features
    
    def _build_data_graph(self, data: Dict[str, Any]) -> nx.Graph:
        """Build graph representation of data structure"""
        
        G = nx.Graph()
        
        # Add nodes for each field
        for key in data.keys():
            G.add_node(key)
        
        # Add edges based on relationships
        keys = list(data.keys())
        for i, key1 in enumerate(keys):
            for key2 in keys[i+1:]:
                # Add edge if fields seem related
                if self._fields_are_related(key1, key2, data[key1], data[key2]):
                    G.add_edge(key1, key2)
        
        return G
    
    def _fields_are_related(self, key1: str, key2: str, val1: Any, val2: Any) -> bool:
        """Determine if two fields are related"""
        
        # Name-based relationships
        if key1.lower() in key2.lower() or key2.lower() in key1.lower():
            return True
        
        # Type-based relationships
        if type(val1) == type(val2):
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                # Check for mathematical relationship
                if val1 != 0 and val2 != 0:
                    ratio = val1 / val2
                    if 0.5 <= ratio <= 2.0:  # Similar magnitude
                        return True
        
        return False


class ContentSemanticAnalyzer:
    """Semantic analysis of content coherence"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".ContentSemanticAnalyzer")
    
    async def extract_coherence_metrics(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract content coherence metrics"""
        
        metrics = {}
        
        # Extract text content
        text_fields = []
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 10:
                text_fields.append((key, value))
        
        if not text_fields:
            return metrics
        
        # Calculate text-based coherence
        for field_name, text in text_fields:
            try:
                # Lexical diversity
                words = text.lower().split()
                unique_words = set(words)
                lexical_diversity = len(unique_words) / len(words) if words else 0
                metrics[f"{field_name}_lexical_diversity"] = lexical_diversity
                
                # Sentence structure consistency
                sentences = text.split('.')
                sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
                if sentence_lengths:
                    metrics[f"{field_name}_sentence_length_cv"] = np.std(sentence_lengths) / np.mean(sentence_lengths) if np.mean(sentence_lengths) > 0 else 0
                
                # Character-level patterns
                char_entropy = self._calculate_character_entropy(text)
                metrics[f"{field_name}_character_entropy"] = char_entropy
                
            except Exception as e:
                self.logger.debug(f"Content analysis failed for {field_name}: {e}")
        
        # Cross-field coherence
        if len(text_fields) > 1:
            coherence_scores = []
            for i, (name1, text1) in enumerate(text_fields):
                for name2, text2 in text_fields[i+1:]:
                    coherence = self._calculate_text_coherence(text1, text2)
                    coherence_scores.append(coherence)
            
            if coherence_scores:
                metrics['cross_field_coherence'] = np.mean(coherence_scores)
        
        return metrics
    
    def _calculate_character_entropy(self, text: str) -> float:
        """Calculate character-level entropy"""
        if not text:
            return 0.0
        
        char_counts = Counter(text.lower())
        total_chars = len(text)
        
        entropy = 0.0
        for count in char_counts.values():
            prob = count / total_chars
            if prob > 0:
                entropy -= prob * math.log2(prob)
        
        return entropy
    
    def _calculate_text_coherence(self, text1: str, text2: str) -> float:
        """Calculate coherence between two text fields"""
        
        # Simple word overlap-based coherence
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        jaccard_similarity = intersection / union if union > 0 else 0
        return jaccard_similarity


class PreservationBoundsCalculator:
    """Calculate formal preservation bounds using information theory"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".PreservationBoundsCalculator")
    
    def calculate_preservation_bounds(self, original_fingerprint: BehavioralFingerprint,
                                    processed_fingerprint: BehavioralFingerprint,
                                    confidence_level: float = 0.95) -> PreservationBounds:
        """Calculate formal preservation bounds"""
        
        try:
            # Mutual information bounds
            mi_lower_bound = self._calculate_mutual_information_lower_bound(
                original_fingerprint, processed_fingerprint
            )
            
            # Entropy preservation ratio
            entropy_preservation = processed_fingerprint.information_content / original_fingerprint.information_content if original_fingerprint.information_content > 0 else 1.0
            
            # Fisher information bound (simplified)
            fisher_bound = self._calculate_fisher_information_bound(
                original_fingerprint, processed_fingerprint
            )
            
            # KL divergence upper bound
            kl_upper_bound = self._calculate_kl_divergence_bound(
                original_fingerprint, processed_fingerprint
            )
            
            # Wasserstein distance bound
            wasserstein_bound = self._calculate_wasserstein_bound(
                original_fingerprint, processed_fingerprint
            )
            
            # Theoretical bounds
            theoretical_max = self._calculate_theoretical_maximum_preservation(original_fingerprint)
            achievable_range = self._calculate_achievable_preservation_range(
                original_fingerprint, processed_fingerprint
            )
            
            # Confidence bounds
            lower_confidence, upper_confidence = self._calculate_confidence_bounds(
                entropy_preservation, confidence_level
            )
            
            return PreservationBounds(
                mutual_information_lower_bound=mi_lower_bound,
                entropy_preservation_ratio=entropy_preservation,
                fisher_information_bound=fisher_bound,
                kl_divergence_upper_bound=kl_upper_bound,
                wasserstein_distance_bound=wasserstein_bound,
                theoretical_max_preservation=theoretical_max,
                achievable_preservation_range=achievable_range,
                bounds_confidence_level=confidence_level,
                lower_confidence_bound=lower_confidence,
                upper_confidence_bound=upper_confidence,
                hard_constraints={},
                soft_constraints={},
                constraint_violations=[]
            )
            
        except Exception as e:
            self.logger.error(f"Preservation bounds calculation failed: {e}")
            # Return conservative bounds
            return PreservationBounds(
                mutual_information_lower_bound=0.0,
                entropy_preservation_ratio=0.5,
                fisher_information_bound=0.0,
                kl_divergence_upper_bound=float('inf'),
                wasserstein_distance_bound=1.0,
                theoretical_max_preservation=1.0,
                achievable_preservation_range=(0.0, 1.0),
                bounds_confidence_level=confidence_level,
                lower_confidence_bound=0.0,
                upper_confidence_bound=1.0,
                hard_constraints={},
                soft_constraints={},
                constraint_violations=[]
            )
    
    def _calculate_mutual_information_lower_bound(self, orig: BehavioralFingerprint,
                                                proc: BehavioralFingerprint) -> float:
        """Calculate lower bound on mutual information preservation"""
        
        # Compare mutual information matrices
        if orig.mutual_information_matrix.size > 0 and proc.mutual_information_matrix.size > 0:
            # Ensure same dimensions
            min_dim = min(orig.mutual_information_matrix.shape[0], proc.mutual_information_matrix.shape[0])
            
            orig_matrix = orig.mutual_information_matrix[:min_dim, :min_dim]
            proc_matrix = proc.mutual_information_matrix[:min_dim, :min_dim]
            
            # Calculate preservation ratio
            orig_total_mi = np.sum(orig_matrix)
            proc_total_mi = np.sum(proc_matrix)
            
            if orig_total_mi > 0:
                return proc_total_mi / orig_total_mi
        
        return 0.0
    
    def _calculate_fisher_information_bound(self, orig: BehavioralFingerprint,
                                          proc: BehavioralFingerprint) -> float:
        """Calculate Fisher information bound (simplified)"""
        
        # Use statistical signature preservation as proxy
        orig_stats = list(orig.statistical_signature.values())
        proc_stats = list(proc.statistical_signature.values())
        
        if not orig_stats or not proc_stats:
            return 0.0
        
        # Calculate statistical distance
        min_len = min(len(orig_stats), len(proc_stats))
        orig_stats = orig_stats[:min_len]
        proc_stats = proc_stats[:min_len]
        
        # Normalized Euclidean distance
        if np.std(orig_stats) > 0:
            normalized_distance = euclidean(orig_stats, proc_stats) / np.std(orig_stats)
            fisher_bound = max(0.0, 1.0 - normalized_distance)
        else:
            fisher_bound = 1.0 if orig_stats == proc_stats else 0.0
        
        return fisher_bound
    
    def _calculate_kl_divergence_bound(self, orig: BehavioralFingerprint,
                                     proc: BehavioralFingerprint) -> float:
        """Calculate KL divergence upper bound"""
        
        # Use entropy measures for KL divergence approximation
        orig_entropies = list(orig.entropy_measures.values())
        proc_entropies = list(proc.entropy_measures.values())
        
        if not orig_entropies or not proc_entropies:
            return float('inf')
        
        # Align entropy measures
        min_len = min(len(orig_entropies), len(proc_entropies))
        orig_entropies = orig_entropies[:min_len]
        proc_entropies = proc_entropies[:min_len]
        
        # Calculate approximate KL divergence
        kl_divergence = 0.0
        for orig_h, proc_h in zip(orig_entropies, proc_entropies):
            if orig_h > 0 and proc_h > 0:
                kl_divergence += abs(orig_h - proc_h) / orig_h
        
        return kl_divergence / len(orig_entropies) if orig_entropies else 0.0
    
    def _calculate_wasserstein_bound(self, orig: BehavioralFingerprint,
                                   proc: BehavioralFingerprint) -> float:
        """Calculate Wasserstein distance bound"""
        
        # Use statistical signatures for Wasserstein approximation
        orig_values = list(orig.statistical_signature.values())
        proc_values = list(proc.statistical_signature.values())
        
        if not orig_values or not proc_values:
            return 1.0
        
        # Normalize values
        orig_values = np.array(orig_values)
        proc_values = np.array(proc_values)
        
        # Pad to same length
        max_len = max(len(orig_values), len(proc_values))
        if len(orig_values) < max_len:
            orig_values = np.pad(orig_values, (0, max_len - len(orig_values)), mode='constant')
        if len(proc_values) < max_len:
            proc_values = np.pad(proc_values, (0, max_len - len(proc_values)), mode='constant')
        
        # Simple Wasserstein-1 approximation (Earth Mover's Distance)
        sorted_orig = np.sort(orig_values)
        sorted_proc = np.sort(proc_values)
        
        wasserstein_distance = np.mean(np.abs(sorted_orig - sorted_proc))
        
        # Normalize by data range
        data_range = max(np.max(orig_values) - np.min(orig_values), 1e-10)
        normalized_distance = wasserstein_distance / data_range
        
        return min(1.0, normalized_distance)
    
    def _calculate_theoretical_maximum_preservation(self, orig: BehavioralFingerprint) -> float:
        """Calculate theoretical maximum preservation possible"""
        
        # Theoretical maximum is always 1.0 (perfect preservation)
        # But practical maximum depends on data characteristics
        
        # Adjust based on information content
        if orig.information_content > 0:
            # Higher information content allows for better preservation
            content_factor = min(1.0, orig.information_content / 10.0)  # Normalize
        else:
            content_factor = 0.5
        
        # Adjust based on pattern regularity
        regularity_factor = orig.pattern_regularity_index
        
        # Adjust based on critical features
        critical_factor = min(1.0, len(orig.critical_features) / 10.0)  # Normalize
        
        # Theoretical maximum considering practical constraints
        theoretical_max = 0.7 + 0.1 * content_factor + 0.1 * regularity_factor + 0.1 * critical_factor
        
        return min(1.0, theoretical_max)
    
    def _calculate_achievable_preservation_range(self, orig: BehavioralFingerprint,
                                               proc: BehavioralFingerprint) -> Tuple[float, float]:
        """Calculate achievable preservation range"""
        
        # Lower bound based on critical feature preservation
        critical_preserved = sum(1 for feature in orig.critical_features 
                               if feature in proc.critical_features)
        lower_bound = critical_preserved / len(orig.critical_features) if orig.critical_features else 0.3
        
        # Upper bound based on theoretical maximum
        upper_bound = self._calculate_theoretical_maximum_preservation(orig)
        
        # Adjust bounds based on processing complexity
        semantic_consistency_ratio = proc.semantic_consistency_score / orig.semantic_consistency_score if orig.semantic_consistency_score > 0 else 1.0
        
        # Tighten bounds if semantic consistency is low
        if semantic_consistency_ratio < 0.7:
            upper_bound *= 0.9
            lower_bound *= 0.8
        
        return (max(0.0, lower_bound), min(1.0, upper_bound))
    
    def _calculate_confidence_bounds(self, preservation_estimate: float,
                                   confidence_level: float) -> Tuple[float, float]:
        """Calculate confidence bounds for preservation estimate"""
        
        # Estimate uncertainty based on data characteristics
        base_uncertainty = 0.05  # 5% base uncertainty
        
        # Increase uncertainty for edge cases
        if preservation_estimate < 0.3 or preservation_estimate > 0.95:
            uncertainty = base_uncertainty * 2
        else:
            uncertainty = base_uncertainty
        
        # Calculate confidence interval
        z_score = 1.96 if confidence_level == 0.95 else 2.576  # For 99% confidence
        margin_of_error = z_score * uncertainty
        
        lower_bound = max(0.0, preservation_estimate - margin_of_error)
        upper_bound = min(1.0, preservation_estimate + margin_of_error)
        
        return (lower_bound, upper_bound)


class SemanticPreservationOptimizer:
    """Optimize semantic preservation strategies"""
    
    def __init__(self, fingerprint_engine: BehavioralFingerprintEngine):
        self.fingerprint_engine = fingerprint_engine
        self.optimization_history = deque(maxlen=1000)
        self.logger = logging.getLogger(__name__ + ".SemanticPreservationOptimizer")
    
    def optimize_preservation_strategy(self, original_fingerprint: BehavioralFingerprint,
                                      target_preservation: float = 0.9) -> Dict[str, Any]:
        """Optimize preservation strategy for target preservation level"""
        
        optimization_result = {
            'target_preservation': target_preservation,
            'recommended_strategy': SemanticAnalysisMode.COMPREHENSIVE,
            'optimization_parameters': {},
            'expected_preservation': 0.0,
            'confidence': 0.0,
            'alternatives': []
        }
        
        try:
            # Analyze fingerprint characteristics
            complexity_score = self._calculate_complexity_score(original_fingerprint)
            
            # Determine optimal strategy based on characteristics
            if complexity_score < 0.3:
                recommended_strategy = SemanticAnalysisMode.DISTRIBUTIONAL
                expected_preservation = 0.85
            elif complexity_score < 0.6:
                recommended_strategy = SemanticAnalysisMode.BEHAVIORAL
                expected_preservation = 0.90
            elif complexity_score < 0.8:
                recommended_strategy = SemanticAnalysisMode.STRUCTURAL
                expected_preservation = 0.88
            else:
                recommended_strategy = SemanticAnalysisMode.COMPREHENSIVE
                expected_preservation = 0.92
            
            # Optimize parameters for chosen strategy
            optimization_parameters = self._optimize_strategy_parameters(
                original_fingerprint, recommended_strategy, target_preservation
            )
            
            # Calculate confidence in recommendation
            confidence = self._calculate_optimization_confidence(
                original_fingerprint, recommended_strategy, expected_preservation
            )
            
            optimization_result.update({
                'recommended_strategy': recommended_strategy,
                'optimization_parameters': optimization_parameters,
                'expected_preservation': expected_preservation,
                'confidence': confidence,
                'complexity_score': complexity_score
            })
            
            # Generate alternatives
            alternatives = self._generate_alternative_strategies(
                original_fingerprint, target_preservation
            )
            optimization_result['alternatives'] = alternatives
            
            # Store optimization history
            self.optimization_history.append(optimization_result)
            
        except Exception as e:
            self.logger.error(f"Preservation strategy optimization failed: {e}")
            # Return safe default
            optimization_result.update({
                'recommended_strategy': SemanticAnalysisMode.COMPREHENSIVE,
                'expected_preservation': 0.8,
                'confidence': 0.5
            })
        
        return optimization_result
    
    def _calculate_complexity_score(self, fingerprint: BehavioralFingerprint) -> float:
        """Calculate complexity score of behavioral fingerprint"""
        
        complexity_factors = []
        
        # Information content complexity
        if fingerprint.information_content > 0:
            info_complexity = min(1.0, fingerprint.information_content / 10.0)
            complexity_factors.append(info_complexity)
        
        # Statistical signature complexity
        stat_values = list(fingerprint.statistical_signature.values())
        if stat_values:
            stat_variance = np.var(stat_values)
            stat_complexity = min(1.0, stat_variance / (np.mean(stat_values) + 1e-10))
            complexity_factors.append(stat_complexity)
        
        # Temporal pattern complexity
        temporal_features = len(fingerprint.temporal_patterns)
        temporal_complexity = min(1.0, temporal_features / 20.0)
        complexity_factors.append(temporal_complexity)
        
        # Graph topology complexity
        graph_features = len(fingerprint.graph_topology_features)
        graph_complexity = min(1.0, graph_features / 15.0)
        complexity_factors.append(graph_complexity)
        
        # Pattern regularity (inverse complexity)
        regularity_complexity = 1.0 - fingerprint.pattern_regularity_index
        complexity_factors.append(regularity_complexity)
        
        return np.mean(complexity_factors) if complexity_factors else 0.5
    
    def _optimize_strategy_parameters(self, fingerprint: BehavioralFingerprint,
                                    strategy: SemanticAnalysisMode,
                                    target_preservation: float) -> Dict[str, Any]:
        """Optimize parameters for specific strategy"""
        
        parameters = {}
        
        if strategy == SemanticAnalysisMode.COMPREHENSIVE:
            parameters = {
                'enable_statistical_analysis': True,
                'enable_temporal_analysis': True,
                'enable_spectral_analysis': True,
                'enable_graph_analysis': True,
                'enable_semantic_analysis': True,
                'analysis_depth': 'deep',
                'feature_selection_threshold': 0.1
            }
        elif strategy == SemanticAnalysisMode.BEHAVIORAL:
            parameters = {
                'enable_statistical_analysis': True,
                'enable_temporal_analysis': True,
                'enable_spectral_analysis': True,
                'enable_graph_analysis': False,
                'enable_semantic_analysis': False,
                'analysis_depth': 'medium',
                'temporal_window_size': 15,
                'spectral_bands': 10
            }
        elif strategy == SemanticAnalysisMode.DISTRIBUTIONAL:
            parameters = {
                'enable_statistical_analysis': True,
                'enable_temporal_analysis': False,
                'enable_spectral_analysis': False,
                'enable_graph_analysis': False,
                'enable_semantic_analysis': False,
                'analysis_depth': 'shallow',
                'statistical_tests': ['normality', 'outliers', 'moments']
            }
        elif strategy == SemanticAnalysisMode.STRUCTURAL:
            parameters = {
                'enable_statistical_analysis': True,
                'enable_temporal_analysis': False,
                'enable_spectral_analysis': False,
                'enable_graph_analysis': True,
                'enable_semantic_analysis': True,
                'analysis_depth': 'medium',
                'graph_features': 20,
                'semantic_coherence_threshold': 0.7
            }
        
        # Adjust parameters based on target preservation
        if target_preservation > 0.95:
            parameters['analysis_depth'] = 'deep'
            parameters['feature_selection_threshold'] = 0.05
        elif target_preservation < 0.8:
            parameters['analysis_depth'] = 'shallow'
            parameters['feature_selection_threshold'] = 0.2
        
        return parameters
    
    def _calculate_optimization_confidence(self, fingerprint: BehavioralFingerprint,
                                         strategy: SemanticAnalysisMode,
                                         expected_preservation: float) -> float:
        """Calculate confidence in optimization recommendation"""
        
        confidence_factors = []
        
        # Historical performance of strategy
        historical_performance = self._get_historical_strategy_performance(strategy)
        if historical_performance:
            performance_consistency = 1.0 - np.std(historical_performance)
            confidence_factors.append(performance_consistency)
        
        # Data characteristics alignment
        if strategy == SemanticAnalysisMode.COMPREHENSIVE:
            confidence_factors.append(0.9)
        elif strategy == SemanticAnalysisMode.BEHAVIORAL:
            temporal_confidence = 0.8 if fingerprint.temporal_patterns else 0.6
            confidence_factors.append(temporal_confidence)
        elif strategy == SemanticAnalysisMode.DISTRIBUTIONAL:
            stat_confidence = 0.8 if len(fingerprint.statistical_signature) > 10 else 0.6
            confidence_factors.append(stat_confidence)
        elif strategy == SemanticAnalysisMode.STRUCTURAL:
            graph_confidence = 0.8 if fingerprint.graph_topology_features else 0.5
            confidence_factors.append(graph_confidence)
        
        # Expected preservation alignment with target
        if abs(expected_preservation - 0.9) < 0.05:
            confidence_factors.append(0.9)
        else:
            confidence_factors.append(0.7)
        
        return np.mean(confidence_factors) if confidence_factors else 0.5
    
    def _get_historical_strategy_performance(self, strategy: SemanticAnalysisMode) -> List[float]:
        """Get historical performance data for strategy"""
        
        performance_data = []
        for result in self.optimization_history:
            if result.get('recommended_strategy') == strategy:
                if 'actual_preservation' in result:
                    performance_data.append(result['actual_preservation'])
        
        return performance_data
    
    def _generate_alternative_strategies(self, fingerprint: BehavioralFingerprint,
                                       target_preservation: float) -> List[Dict[str, Any]]:
        """Generate alternative preservation strategies"""
        
        alternatives = []
        
        # Fast strategy (lower preservation, faster processing)
        alternatives.append({
            'strategy': SemanticAnalysisMode.DISTRIBUTIONAL,
            'expected_preservation': 0.82,
            'expected_processing_time_ms': 0.5,
            'trade_off': 'speed_optimized'
        })
        
        # Balanced strategy
        alternatives.append({
            'strategy': SemanticAnalysisMode.BEHAVIORAL,
            'expected_preservation': 0.88,
            'expected_processing_time_ms': 1.2,
            'trade_off': 'balanced'
        })
        
        # Maximum preservation strategy
        alternatives.append({
            'strategy': SemanticAnalysisMode.COMPREHENSIVE,
            'expected_preservation': 0.94,
            'expected_processing_time_ms': 2.5,
            'trade_off': 'preservation_optimized'
        })
        
        return alternatives


# Integration functions for existing Enhanced Anomaly Preservation Guard
def integrate_semantic_preservation_engine(preservation_guard, config: Dict[str, Any] = None):
    """Integrate semantic preservation engine with existing preservation guard"""
    
    # Initialize semantic components
    preservation_guard.semantic_engine = BehavioralFingerprintEngine(config.get('semantic_config', {}))
    preservation_guard.bounds_calculator = PreservationBoundsCalculator()
    preservation_guard.semantic_optimizer = SemanticPreservationOptimizer(preservation_guard.semantic_engine)
    
    # Add semantic assessment to existing workflow
    original_assess_method = preservation_guard.assess_preservation_impact
    
    async def enhanced_assess_preservation_impact(original_data, processed_data, processing_stage, 
                                                analysis_depth=None, processing_mode=None):
        """Enhanced assessment with semantic preservation"""
        
        # Call original assessment
        assessment = await original_assess_method(original_data, processed_data, processing_stage, 
                                                analysis_depth, processing_mode)
        
        # Add semantic analysis
        try:
            # Extract behavioral fingerprints
            original_fingerprint = await preservation_guard.semantic_engine.extract_behavioral_fingerprint(
                original_data, SemanticAnalysisMode.COMPREHENSIVE
            )
            
            processed_fingerprint = await preservation_guard.semantic_engine.extract_behavioral_fingerprint(
                processed_data, SemanticAnalysisMode.COMPREHENSIVE
            )
            
            # Calculate preservation bounds
            preservation_bounds = preservation_guard.bounds_calculator.calculate_preservation_bounds(
                original_fingerprint, processed_fingerprint
            )
            
            # Add semantic metrics to assessment
            assessment.semantic_consistency_score = processed_fingerprint.semantic_consistency_score
            assessment.behavioral_fingerprint_similarity = calculate_fingerprint_similarity(
                original_fingerprint, processed_fingerprint
            )
            assessment.preservation_bounds = preservation_bounds
            assessment.information_theoretic_bounds = {
                'mutual_information_lower_bound': preservation_bounds.mutual_information_lower_bound,
                'entropy_preservation_ratio': preservation_bounds.entropy_preservation_ratio,
                'theoretical_max_preservation': preservation_bounds.theoretical_max_preservation
            }
            
        except Exception as e:
            preservation_guard.logger.debug(f"Semantic analysis failed: {e}")
        
        return assessment
    
    # Replace the method
    preservation_guard.assess_preservation_impact = enhanced_assess_preservation_impact
    
    return preservation_guard


def calculate_fingerprint_similarity(fp1: BehavioralFingerprint, fp2: BehavioralFingerprint) -> float:
    """Calculate similarity between two behavioral fingerprints"""
    
    similarity_scores = []
    
    # Statistical signature similarity
    if fp1.statistical_signature and fp2.statistical_signature:
        common_keys = set(fp1.statistical_signature.keys()) & set(fp2.statistical_signature.keys())
        if common_keys:
            stat_similarities = []
            for key in common_keys:
                val1, val2 = fp1.statistical_signature[key], fp2.statistical_signature[key]
                if val1 != 0:
                    similarity = 1.0 - abs(val1 - val2) / abs(val1)
                else:
                    similarity = 1.0 if val2 == 0 else 0.0
                stat_similarities.append(max(0.0, similarity))
            
            if stat_similarities:
                similarity_scores.append(np.mean(stat_similarities))
    
    # Information content similarity
    if fp1.information_content > 0 and fp2.information_content > 0:
        info_similarity = min(fp1.information_content, fp2.information_content) / max(fp1.information_content, fp2.information_content)
        similarity_scores.append(info_similarity)
    
    # Semantic consistency similarity
    semantic_similarity = min(fp1.semantic_consistency_score, fp2.semantic_consistency_score) / max(fp1.semantic_consistency_score, fp2.semantic_consistency_score) if max(fp1.semantic_consistency_score, fp2.semantic_consistency_score) > 0 else 1.0
    similarity_scores.append(semantic_similarity)
    
    # Pattern regularity similarity
    pattern_similarity = min(fp1.pattern_regularity_index, fp2.pattern_regularity_index) / max(fp1.pattern_regularity_index, fp2.pattern_regularity_index) if max(fp1.pattern_regularity_index, fp2.pattern_regularity_index) > 0 else 1.0
    similarity_scores.append(pattern_similarity)
    
    # Critical features overlap
    if fp1.critical_features or fp2.critical_features:
        critical_overlap = len(fp1.critical_features & fp2.critical_features) / len(fp1.critical_features | fp2.critical_features) if (fp1.critical_features | fp2.critical_features) else 1.0
        similarity_scores.append(critical_overlap)
    
    return np.mean(similarity_scores) if similarity_scores else 0.0


# Export main classes and functions
__all__ = [
    'BehavioralFingerprintEngine',
    'PreservationBoundsCalculator', 
    'SemanticPreservationOptimizer',
    'BehavioralFingerprint',
    'PreservationBounds',
    'SemanticAnalysisMode',
    'PreservationConstraintType',
    'SpectralAnalyzer',
    'StructuralGraphAnalyzer',
    'ContentSemanticAnalyzer',
    'integrate_semantic_preservation_engine',
    'calculate_fingerprint_similarity'
]