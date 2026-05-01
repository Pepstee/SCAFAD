#!/usr/bin/env python3
"""
SCAFAD Layer 1: Semantic Analyzer Subsystem
===========================================

The Semantic Analyzer analyzes behavioral semantics and preserves critical
features for anomaly detection in Layer 1's behavioral intake zone. It provides:

- Behavioral feature extraction and analysis
- Semantic similarity computation
- Critical feature identification
- Anomaly signature preservation
- Behavioral pattern recognition
- Feature importance scoring

Author: SCAFAD Research Team
Institution: Birmingham Newman University
License: MIT
Version: 1.0.0
"""

import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from enum import Enum, auto
from datetime import datetime, timezone
import copy
import math
from collections import defaultdict

# =============================================================================
# Semantic Analyzer Data Models
# =============================================================================

class FeatureCategory(Enum):
    """Behavioral feature categories"""
    TEMPORAL = "temporal"           # Time-based features
    STRUCTURAL = "structural"        # Data structure features
    SEMANTIC = "semantic"           # Meaning-based features
    STATISTICAL = "statistical"     # Statistical features
    CONTEXTUAL = "contextual"       # Context-dependent features
    RELATIONAL = "relational"       # Relationship features

class FeatureImportance(Enum):
    """Feature importance levels"""
    CRITICAL = "critical"           # Essential for anomaly detection
    HIGH = "high"                   # Very important
    MEDIUM = "medium"               # Moderately important
    LOW = "low"                     # Less important
    MINIMAL = "minimal"             # Minimal importance

class SemanticSimilarity(Enum):
    """Semantic similarity levels"""
    IDENTICAL = "identical"         # 100% similar
    VERY_SIMILAR = "very_similar"   # 80-99% similar
    SIMILAR = "similar"             # 60-79% similar
    MODERATELY_SIMILAR = "moderately_similar"  # 40-59% similar
    DIFFERENT = "different"         # 20-39% similar
    VERY_DIFFERENT = "very_different"  # 0-19% similar

@dataclass
class BehavioralFeature:
    """Behavioral feature definition"""
    feature_id: str
    feature_name: str
    feature_type: str
    category: FeatureCategory
    importance: FeatureImportance
    value: Any
    confidence: float
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Post-initialization validation"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        
        if not isinstance(self.category, FeatureCategory):
            self.category = FeatureCategory(self.category)
        
        if not isinstance(self.importance, FeatureImportance):
            self.importance = FeatureImportance(self.importance)

@dataclass
class SemanticAnalysis:
    """Result of semantic analysis"""
    record_id: str
    features_extracted: List[BehavioralFeature]
    critical_features: List[BehavioralFeature]
    feature_importance_scores: Dict[str, float]
    semantic_signature: str
    analysis_confidence: float
    processing_time_ms: float
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class SimilarityAnalysis:
    """Result of similarity analysis"""
    source_record_id: str
    target_record_id: str
    overall_similarity: float
    similarity_level: SemanticSimilarity
    feature_similarities: Dict[str, float]
    critical_feature_similarity: float
    anomaly_preservation_score: float
    analysis_confidence: float
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class FeaturePreservationReport:
    """Report on feature preservation during transformations"""
    original_features: List[BehavioralFeature]
    preserved_features: List[BehavioralFeature]
    lost_features: List[BehavioralFeature]
    preservation_rate: float
    critical_preservation_rate: float
    transformation_impact: str
    recommendations: List[str]
    metadata: Optional[Dict[str, Any]] = None

# =============================================================================
# Semantic Analyzer Core Class
# =============================================================================

class SemanticAnalyzer:
    """
    Semantic Analyzer for behavioral feature extraction and preservation
    
    The Semantic Analyzer provides comprehensive analysis of behavioral
    patterns in telemetry data, ensuring critical features are preserved
    for downstream anomaly detection.
    """
    
    def __init__(self, config: Any = None):
        """Initialize the Semantic Analyzer"""
        self.config = config
        self.logger = logging.getLogger("SCAFAD.Layer1.SemanticAnalyzer")
        
        # Feature extraction patterns
        self.feature_patterns: Dict[str, Dict[str, Any]] = {}
        
        # Feature importance weights
        self.importance_weights: Dict[FeatureImportance, float] = {
            FeatureImportance.CRITICAL: 1.0,
            FeatureImportance.HIGH: 0.8,
            FeatureImportance.MEDIUM: 0.6,
            FeatureImportance.LOW: 0.4,
            FeatureImportance.MINIMAL: 0.2
        }
        
        # Performance tracking
        self.analyzer_stats = {
            'total_analyses': 0,
            'total_features_extracted': 0,
            'total_similarity_analyses': 0,
            'average_processing_time_ms': 0.0
        }
        
        # Initialize feature patterns
        self._initialize_feature_patterns()
        
        self.logger.info("Semantic Analyzer initialized")
    
    def analyze_record(self, record: Dict[str, Any]) -> SemanticAnalysis:
        """
        Analyze a telemetry record for behavioral features
        
        Args:
            record: Telemetry record to analyze
            
        Returns:
            SemanticAnalysis with extracted features and analysis
        """
        import time
        start_time = time.time()
        
        try:
            record_id = record.get('record_id', 'unknown')
            
            # Extract behavioral features
            features = self._extract_behavioral_features(record)
            
            # Identify critical features
            critical_features = self._identify_critical_features(features)
            
            # Calculate feature importance scores
            importance_scores = self._calculate_feature_importance_scores(features)
            
            # Generate semantic signature
            semantic_signature = self._generate_semantic_signature(features)
            
            # Calculate analysis confidence
            analysis_confidence = self._calculate_analysis_confidence(features)
            
            processing_time = (time.time() - start_time) * 1000
            
            # Update statistics
            self._update_analyzer_stats(len(features), processing_time)
            
            # Create analysis result
            analysis = SemanticAnalysis(
                record_id=record_id,
                features_extracted=features,
                critical_features=critical_features,
                feature_importance_scores=importance_scores,
                semantic_signature=semantic_signature,
                analysis_confidence=analysis_confidence,
                processing_time_ms=processing_time,
                metadata={
                    'schema_version': record.get('schema_version', 'unknown'),
                    'anomaly_type': record.get('anomaly_type', 'unknown')
                }
            )
            
            self.logger.debug(f"Semantic analysis completed for {record_id} in {processing_time:.2f}ms")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Semantic analysis failed: {str(e)}")
            raise
    
    def analyze_similarity(self, source_record: Dict[str, Any], 
                          target_record: Dict[str, Any]) -> SimilarityAnalysis:
        """
        Analyze semantic similarity between two records
        
        Args:
            source_record: Source telemetry record
            target_record: Target telemetry record
            
        Returns:
            SimilarityAnalysis with similarity details
        """
        try:
            # Analyze both records
            source_analysis = self.analyze_record(source_record)
            target_analysis = self.analyze_record(target_record)
            
            # Calculate feature similarities
            feature_similarities = self._calculate_feature_similarities(
                source_analysis.features_extracted,
                target_analysis.features_extracted
            )
            
            # Calculate overall similarity
            overall_similarity = self._calculate_overall_similarity(feature_similarities)
            
            # Determine similarity level
            similarity_level = self._determine_similarity_level(overall_similarity)
            
            # Calculate critical feature similarity
            critical_similarity = self._calculate_critical_feature_similarity(
                source_analysis.critical_features,
                target_analysis.critical_features
            )
            
            # Calculate anomaly preservation score
            preservation_score = self._calculate_anomaly_preservation_score(
                source_analysis, target_analysis, feature_similarities
            )
            
            # Calculate analysis confidence
            analysis_confidence = min(
                source_analysis.analysis_confidence,
                target_analysis.analysis_confidence
            )
            
            # Create similarity analysis
            similarity_analysis = SimilarityAnalysis(
                source_record_id=source_record.get('record_id', 'unknown'),
                target_record_id=target_record.get('record_id', 'unknown'),
                overall_similarity=overall_similarity,
                similarity_level=similarity_level,
                feature_similarities=feature_similarities,
                critical_feature_similarity=critical_similarity,
                anomaly_preservation_score=preservation_score,
                analysis_confidence=analysis_confidence,
                metadata={
                    'source_schema': source_record.get('schema_version', 'unknown'),
                    'target_schema': target_record.get('schema_version', 'unknown')
                }
            )
            
            self.analyzer_stats['total_similarity_analyses'] += 1
            return similarity_analysis
            
        except Exception as e:
            self.logger.error(f"Similarity analysis failed: {str(e)}")
            raise
    
    def assess_transformation_impact(self, original_record: Dict[str, Any],
                                   transformed_record: Dict[str, Any]) -> FeaturePreservationReport:
        """
        Assess the impact of data transformations on feature preservation
        
        Args:
            original_record: Original telemetry record
            transformed_record: Transformed telemetry record
            
        Returns:
            FeaturePreservationReport with preservation analysis
        """
        try:
            # Analyze both records
            original_analysis = self.analyze_record(original_record)
            transformed_analysis = self.analyze_record(transformed_record)
            
            # Identify preserved and lost features
            preserved_features = []
            lost_features = []
            
            for original_feature in original_analysis.features_extracted:
                # Find corresponding feature in transformed record
                corresponding_feature = self._find_corresponding_feature(
                    original_feature, transformed_analysis.features_extracted
                )
                
                if corresponding_feature:
                    preserved_features.append(corresponding_feature)
                else:
                    lost_features.append(original_feature)
            
            # Calculate preservation rates
            total_features = len(original_analysis.features_extracted)
            preserved_count = len(preserved_features)
            preservation_rate = preserved_count / total_features if total_features > 0 else 0.0
            
            # Calculate critical feature preservation rate
            critical_features = original_analysis.critical_features
            critical_preserved = [f for f in preserved_features if f in critical_features]
            critical_preservation_rate = len(critical_preserved) / len(critical_features) if critical_features else 0.0
            
            # Assess transformation impact
            transformation_impact = self._assess_transformation_severity(
                preservation_rate, critical_preservation_rate
            )
            
            # Generate recommendations
            recommendations = self._generate_preservation_recommendations(
                lost_features, critical_features, preservation_rate
            )
            
            # Create preservation report
            report = FeaturePreservationReport(
                original_features=original_analysis.features_extracted,
                preserved_features=preserved_features,
                lost_features=lost_features,
                preservation_rate=preservation_rate,
                critical_preservation_rate=critical_preservation_rate,
                transformation_impact=transformation_impact,
                recommendations=recommendations,
                metadata={
                    'original_schema': original_record.get('schema_version', 'unknown'),
                    'transformed_schema': transformed_record.get('schema_version', 'unknown')
                }
            )
            
            return report
            
        except Exception as e:
            self.logger.error(f"Transformation impact assessment failed: {str(e)}")
            raise
    
    def get_analyzer_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics"""
        return self.analyzer_stats.copy()
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _initialize_feature_patterns(self):
        """Initialize feature extraction patterns"""
        self.feature_patterns = {
            'temporal_features': {
                'execution_timing': {
                    'fields': ['timestamp', 'execution_phase'],
                    'category': FeatureCategory.TEMPORAL,
                    'importance': FeatureImportance.HIGH
                },
                'phase_duration': {
                    'fields': ['timestamp'],
                    'category': FeatureCategory.TEMPORAL,
                    'importance': FeatureImportance.MEDIUM
                }
            },
            'structural_features': {
                'data_complexity': {
                    'fields': ['telemetry_data'],
                    'category': FeatureCategory.STRUCTURAL,
                    'importance': FeatureImportance.MEDIUM
                },
                'field_presence': {
                    'fields': ['provenance_chain', 'context_metadata'],
                    'category': FeatureCategory.STRUCTURAL,
                    'importance': FeatureImportance.LOW
                }
            },
            'semantic_features': {
                'function_signature': {
                    'fields': ['function_name', 'execution_phase'],
                    'category': FeatureCategory.SEMANTIC,
                    'importance': FeatureImportance.CRITICAL
                },
                'anomaly_pattern': {
                    'fields': ['anomaly_type', 'execution_phase'],
                    'category': FeatureCategory.SEMANTIC,
                    'importance': FeatureImportance.CRITICAL
                }
            },
            'statistical_features': {
                'data_volume': {
                    'fields': ['telemetry_data'],
                    'category': FeatureCategory.STATISTICAL,
                    'importance': FeatureImportance.MEDIUM
                },
                'field_distribution': {
                    'fields': ['telemetry_data'],
                    'category': FeatureCategory.STATISTICAL,
                    'importance': FeatureImportance.LOW
                }
            }
        }
    
    def _extract_behavioral_features(self, record: Dict[str, Any]) -> List[BehavioralFeature]:
        """Extract behavioral features from a record"""
        features = []
        
        # Extract temporal features
        features.extend(self._extract_temporal_features(record))
        
        # Extract structural features
        features.extend(self._extract_structural_features(record))
        
        # Extract semantic features
        features.extend(self._extract_semantic_features(record))
        
        # Extract statistical features
        features.extend(self._extract_statistical_features(record))
        
        # Extract contextual features
        features.extend(self._extract_contextual_features(record))
        
        return features
    
    def _extract_temporal_features(self, record: Dict[str, Any]) -> List[BehavioralFeature]:
        """Extract temporal behavioral features"""
        features = []
        
        # Execution timing
        timestamp = record.get('timestamp')
        execution_phase = record.get('execution_phase')
        
        if timestamp and execution_phase:
            feature = BehavioralFeature(
                feature_id=f"temporal_execution_{execution_phase}",
                feature_name="execution_timing",
                feature_type="temporal",
                category=FeatureCategory.TEMPORAL,
                importance=FeatureImportance.HIGH,
                value={
                    'timestamp': timestamp,
                    'phase': execution_phase,
                    'hour_of_day': self._extract_hour_of_day(timestamp)
                },
                confidence=0.9
            )
            features.append(feature)
        
        return features
    
    def _extract_structural_features(self, record: Dict[str, Any]) -> List[BehavioralFeature]:
        """Extract structural behavioral features"""
        features = []
        
        # Data complexity
        telemetry_data = record.get('telemetry_data', {})
        if telemetry_data:
            complexity_score = self._calculate_data_complexity(telemetry_data)
            
            feature = BehavioralFeature(
                feature_id="structural_data_complexity",
                feature_name="data_complexity",
                feature_type="structural",
                category=FeatureCategory.STRUCTURAL,
                importance=FeatureImportance.MEDIUM,
                value=complexity_score,
                confidence=0.8
            )
            features.append(feature)
        
        # Field presence
        optional_fields = ['provenance_chain', 'context_metadata', 'schema_version']
        present_fields = [field for field in optional_fields if field in record]
        
        feature = BehavioralFeature(
            feature_id="structural_field_presence",
            feature_name="field_presence",
            feature_type="structural",
            category=FeatureCategory.STRUCTURAL,
            importance=FeatureImportance.LOW,
            value=present_fields,
            confidence=1.0
        )
        features.append(feature)
        
        return features
    
    def _extract_semantic_features(self, record: Dict[str, Any]) -> List[BehavioralFeature]:
        """Extract semantic behavioral features"""
        features = []
        
        # Function signature
        function_name = record.get('function_name')
        execution_phase = record.get('execution_phase')
        
        if function_name and execution_phase:
            feature = BehavioralFeature(
                feature_id="semantic_function_signature",
                feature_name="function_signature",
                feature_type="semantic",
                category=FeatureCategory.SEMANTIC,
                importance=FeatureImportance.CRITICAL,
                value={
                    'function_name': function_name,
                    'execution_phase': execution_phase,
                    'signature_hash': hashlib.md5(f"{function_name}:{execution_phase}".encode()).hexdigest()
                },
                confidence=1.0
            )
            features.append(feature)
        
        # Anomaly pattern
        anomaly_type = record.get('anomaly_type')
        if anomaly_type and execution_phase:
            feature = BehavioralFeature(
                feature_id="semantic_anomaly_pattern",
                feature_name="anomaly_pattern",
                feature_type="semantic",
                category=FeatureCategory.SEMANTIC,
                importance=FeatureImportance.CRITICAL,
                value={
                    'anomaly_type': anomaly_type,
                    'execution_phase': execution_phase,
                    'pattern_id': f"{anomaly_type}_{execution_phase}"
                },
                confidence=0.95
            )
            features.append(feature)
        
        return features
    
    def _extract_statistical_features(self, record: Dict[str, Any]) -> List[BehavioralFeature]:
        """Extract statistical behavioral features"""
        features = []
        
        # Data volume
        telemetry_data = record.get('telemetry_data', {})
        if telemetry_data:
            data_volume = self._calculate_data_volume(telemetry_data)
            
            feature = BehavioralFeature(
                feature_id="statistical_data_volume",
                feature_name="data_volume",
                feature_type="statistical",
                category=FeatureCategory.STATISTICAL,
                importance=FeatureImportance.MEDIUM,
                value=data_volume,
                confidence=0.85
            )
            features.append(feature)
        
        return features
    
    def _extract_contextual_features(self, record: Dict[str, Any]) -> List[BehavioralFeature]:
        """Extract contextual behavioral features"""
        features = []
        
        # Schema version context
        schema_version = record.get('schema_version')
        if schema_version:
            feature = BehavioralFeature(
                feature_id="contextual_schema_version",
                feature_name="schema_version",
                feature_type="contextual",
                category=FeatureCategory.CONTEXTUAL,
                importance=FeatureImportance.LOW,
                value=schema_version,
                confidence=1.0
            )
            features.append(feature)
        
        return features
    
    def _identify_critical_features(self, features: List[BehavioralFeature]) -> List[BehavioralFeature]:
        """Identify critical features for anomaly detection"""
        critical_features = []
        
        for feature in features:
            if feature.importance in [FeatureImportance.CRITICAL, FeatureImportance.HIGH]:
                critical_features.append(feature)
        
        return critical_features
    
    def _calculate_feature_importance_scores(self, features: List[BehavioralFeature]) -> Dict[str, float]:
        """Calculate importance scores for features"""
        importance_scores = {}
        
        for feature in features:
            base_score = self.importance_weights[feature.importance]
            confidence_multiplier = feature.confidence
            final_score = base_score * confidence_multiplier
            
            importance_scores[feature.feature_id] = final_score
        
        return importance_scores
    
    def _generate_semantic_signature(self, features: List[BehavioralFeature]) -> str:
        """Generate semantic signature from features"""
        # Sort features by importance and create signature
        sorted_features = sorted(
            features, 
            key=lambda f: (self.importance_weights[f.importance], f.confidence),
            reverse=True
        )
        
        # Create signature from top features
        signature_parts = []
        for feature in sorted_features[:10]:  # Top 10 features
            signature_parts.append(f"{feature.feature_id}:{feature.importance.value}")
        
        signature_string = "|".join(signature_parts)
        return hashlib.sha256(signature_string.encode()).hexdigest()[:16]
    
    def _calculate_analysis_confidence(self, features: List[BehavioralFeature]) -> float:
        """Calculate overall analysis confidence"""
        if not features:
            return 0.0
        
        total_confidence = sum(feature.confidence for feature in features)
        return total_confidence / len(features)
    
    def _calculate_feature_similarities(self, source_features: List[BehavioralFeature],
                                      target_features: List[BehavioralFeature]) -> Dict[str, float]:
        """Calculate similarities between feature sets"""
        similarities = {}
        
        # Create feature mapping
        source_feature_map = {f.feature_id: f for f in source_features}
        target_feature_map = {f.feature_id: f for f in target_features}
        
        # Calculate similarities for common features
        for feature_id in source_feature_map.keys() & target_feature_map.keys():
            source_feature = source_feature_map[feature_id]
            target_feature = target_feature_map[feature_id]
            
            similarity = self._calculate_feature_similarity(source_feature, target_feature)
            similarities[feature_id] = similarity
        
        return similarities
    
    def _calculate_feature_similarity(self, source_feature: BehavioralFeature,
                                    target_feature: BehavioralFeature) -> float:
        """Calculate similarity between two features"""
        # Base similarity on feature type and category
        if source_feature.feature_type != target_feature.feature_type:
            return 0.0
        
        if source_feature.category != target_feature.category:
            return 0.3  # Some similarity if categories differ
        
        # Calculate value similarity
        value_similarity = self._calculate_value_similarity(
            source_feature.value, target_feature.value
        )
        
        # Weight by confidence
        confidence_weight = (source_feature.confidence + target_feature.confidence) / 2
        
        return value_similarity * confidence_weight
    
    def _calculate_value_similarity(self, source_value: Any, target_value: Any) -> float:
        """Calculate similarity between feature values"""
        if source_value == target_value:
            return 1.0
        
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            return self._calculate_dict_similarity(source_value, target_value)
        elif isinstance(source_value, list) and isinstance(target_value, list):
            return self._calculate_list_similarity(source_value, target_value)
        elif isinstance(source_value, (int, float)) and isinstance(target_value, (int, float)):
            return self._calculate_numeric_similarity(source_value, target_value)
        else:
            return 0.0
    
    def _calculate_dict_similarity(self, source_dict: Dict[str, Any], 
                                 target_dict: Dict[str, Any]) -> float:
        """Calculate similarity between dictionaries"""
        if not source_dict and not target_dict:
            return 1.0
        
        if not source_dict or not target_dict:
            return 0.0
        
        common_keys = source_dict.keys() & target_dict.keys()
        total_keys = source_dict.keys() | target_dict.keys()
        
        if not total_keys:
            return 1.0
        
        # Calculate similarity for common keys
        common_similarities = []
        for key in common_keys:
            key_similarity = self._calculate_value_similarity(
                source_dict[key], target_dict[key]
            )
            common_similarities.append(key_similarity)
        
        common_avg = sum(common_similarities) / len(common_similarities) if common_similarities else 0.0
        
        # Weight by overlap
        overlap_ratio = len(common_keys) / len(total_keys)
        
        return common_avg * overlap_ratio
    
    def _calculate_list_similarity(self, source_list: List[Any], 
                                 target_list: List[Any]) -> float:
        """Calculate similarity between lists"""
        if not source_list and not target_list:
            return 1.0
        
        if not source_list or not target_list:
            return 0.0
        
        # Simple length-based similarity for now
        length_diff = abs(len(source_list) - len(target_list))
        max_length = max(len(source_list), len(target_list))
        
        if max_length == 0:
            return 1.0
        
        length_similarity = 1.0 - (length_diff / max_length)
        
        return length_similarity
    
    def _calculate_numeric_similarity(self, source_value: Union[int, float],
                                    target_value: Union[int, float]) -> float:
        """Calculate similarity between numeric values"""
        if source_value == target_value:
            return 1.0
        
        # Calculate relative difference
        max_value = max(abs(source_value), abs(target_value))
        if max_value == 0:
            return 1.0
        
        relative_diff = abs(source_value - target_value) / max_value
        return max(0.0, 1.0 - relative_diff)
    
    def _calculate_overall_similarity(self, feature_similarities: Dict[str, float]) -> float:
        """Calculate overall similarity from feature similarities"""
        if not feature_similarities:
            return 0.0
        
        return sum(feature_similarities.values()) / len(feature_similarities)
    
    def _determine_similarity_level(self, similarity_score: float) -> SemanticSimilarity:
        """Determine similarity level from similarity score"""
        if similarity_score >= 0.95:
            return SemanticSimilarity.IDENTICAL
        elif similarity_score >= 0.8:
            return SemanticSimilarity.VERY_SIMILAR
        elif similarity_score >= 0.6:
            return SemanticSimilarity.SIMILAR
        elif similarity_score >= 0.4:
            return SemanticSimilarity.MODERATELY_SIMILAR
        elif similarity_score >= 0.2:
            return SemanticSimilarity.DIFFERENT
        else:
            return SemanticSimilarity.VERY_DIFFERENT
    
    def _calculate_critical_feature_similarity(self, source_critical: List[BehavioralFeature],
                                             target_critical: List[BehavioralFeature]) -> float:
        """Calculate similarity for critical features"""
        if not source_critical and not target_critical:
            return 1.0
        
        if not source_critical or not target_critical:
            return 0.0
        
        # Calculate similarities for critical features
        critical_similarities = []
        for source_feature in source_critical:
            for target_feature in target_critical:
                if source_feature.feature_id == target_feature.feature_id:
                    similarity = self._calculate_feature_similarity(source_feature, target_feature)
                    critical_similarities.append(similarity)
        
        if not critical_similarities:
            return 0.0
        
        return sum(critical_similarities) / len(critical_similarities)
    
    def _calculate_anomaly_preservation_score(self, source_analysis: SemanticAnalysis,
                                             target_analysis: SemanticAnalysis,
                                             feature_similarities: Dict[str, Any]) -> float:
        """Calculate anomaly preservation score"""
        # Weight by feature importance
        weighted_similarities = []
        
        for feature_id, similarity in feature_similarities.items():
            source_importance = source_analysis.feature_importance_scores.get(feature_id, 0.0)
            target_importance = target_analysis.feature_importance_scores.get(feature_id, 0.0)
            
            # Use average importance
            avg_importance = (source_importance + target_importance) / 2
            weighted_similarity = similarity * avg_importance
            
            weighted_similarities.append(weighted_similarity)
        
        if not weighted_similarities:
            return 0.0
        
        return sum(weighted_similarities) / len(weighted_similarities)
    
    def _find_corresponding_feature(self, original_feature: BehavioralFeature,
                                   transformed_features: List[BehavioralFeature]) -> Optional[BehavioralFeature]:
        """Find corresponding feature in transformed record"""
        for transformed_feature in transformed_features:
            if (transformed_feature.feature_id == original_feature.feature_id and
                transformed_feature.feature_type == original_feature.feature_type):
                return transformed_feature
        
        return None
    
    def _assess_transformation_severity(self, preservation_rate: float, 
                                      critical_preservation_rate: float) -> str:
        """Assess the severity of transformation impact"""
        if preservation_rate >= 0.9 and critical_preservation_rate >= 0.95:
            return "minimal"
        elif preservation_rate >= 0.8 and critical_preservation_rate >= 0.9:
            return "low"
        elif preservation_rate >= 0.6 and critical_preservation_rate >= 0.8:
            return "moderate"
        elif preservation_rate >= 0.4 and critical_preservation_rate >= 0.6:
            return "high"
        else:
            return "severe"
    
    def _generate_preservation_recommendations(self, lost_features: List[BehavioralFeature],
                                             critical_features: List[BehavioralFeature],
                                             preservation_rate: float) -> List[str]:
        """Generate recommendations for feature preservation"""
        recommendations = []
        
        if preservation_rate < 0.8:
            recommendations.append("Review data transformation pipeline to preserve more features")
        
        # Check for lost critical features
        lost_critical = [f for f in lost_features if f in critical_features]
        if lost_critical:
            recommendations.append(f"Critical features lost: {len(lost_critical)}. Review transformation logic.")
        
        if preservation_rate < 0.6:
            recommendations.append("Consider implementing feature preservation mechanisms")
        
        return recommendations
    
    def _update_analyzer_stats(self, features_extracted: int, processing_time: float):
        """Update analyzer statistics"""
        self.analyzer_stats['total_features_extracted'] += features_extracted
        
        # Update average processing time
        current_avg = self.analyzer_stats['average_processing_time_ms']
        total_analyses = self.analyzer_stats['total_analyses']
        
        if total_analyses > 0:
            self.analyzer_stats['average_processing_time_ms'] = (
                (current_avg * (total_analyses - 1) + processing_time) / total_analyses
            )
    
    def _extract_hour_of_day(self, timestamp: Union[int, float]) -> int:
        """Extract hour of day from timestamp"""
        try:
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                return dt.hour
            else:
                return 0
        except Exception:
            return 0
    
    def _calculate_data_complexity(self, data: Any) -> float:
        """Calculate data complexity score"""
        if isinstance(data, dict):
            return len(data) / 10.0  # Normalize by expected size
        elif isinstance(data, list):
            return len(data) / 100.0  # Normalize by expected size
        else:
            return 0.1
    
    def _calculate_data_volume(self, data: Any) -> int:
        """Calculate data volume in bytes"""
        try:
            return len(json.dumps(data).encode('utf-8'))
        except Exception:
            return 0

# =============================================================================
# Semantic Analyzer Factory Functions
# =============================================================================

def create_semantic_analyzer(config: Optional[Any] = None) -> SemanticAnalyzer:
    """Create a semantic analyzer with default configuration"""
    return SemanticAnalyzer(config)

if __name__ == "__main__":
    # Example usage
    analyzer = create_semantic_analyzer()
    
    # Test record
    test_record = {
        'record_id': 'test123',
        'timestamp': 1640995200.0,
        'function_name': 'test_function',
        'execution_phase': 'invocation',
        'anomaly_type': 'performance',
        'telemetry_data': {'cpu_usage': 85.5, 'memory_usage': 67.2},
        'schema_version': 'v2.1'
    }
    
    # Analyze record
    analysis = analyzer.analyze_record(test_record)
    print(f"Features extracted: {len(analysis.features_extracted)}")
    print(f"Critical features: {len(analysis.critical_features)}")
    print(f"Analysis confidence: {analysis.analysis_confidence:.2f}")
    print(f"Semantic signature: {analysis.semantic_signature}")
    
    # Test similarity analysis
    similar_record = {
        'record_id': 'test124',
        'timestamp': 1640995260.0,
        'function_name': 'test_function',
        'execution_phase': 'invocation',
        'anomaly_type': 'performance',
        'telemetry_data': {'cpu_usage': 87.1, 'memory_usage': 68.9},
        'schema_version': 'v2.1'
    }
    
    similarity = analyzer.analyze_similarity(test_record, similar_record)
    print(f"\nSimilarity analysis:")
    print(f"Overall similarity: {similarity.overall_similarity:.2f}")
    print(f"Similarity level: {similarity.similarity_level.value}")
    print(f"Anomaly preservation score: {similarity.anomaly_preservation_score:.2f}")
    
    # Get analyzer stats
    stats = analyzer.get_analyzer_stats()
    print(f"\nAnalyzer stats: {stats}")

# Backward-compat alias
BehavioralFeatures = BehavioralFeature
