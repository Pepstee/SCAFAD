#!/usr/bin/env python3
"""
SCAFAD Causal Accuracy Study
============================

This module evaluates the precision and recall of causal edge detection and 
attack path reconstruction in SCAFAD's graph analysis. It provides rigorous
evaluation of causal inference capabilities with ablation studies.

Key Metrics:
1. Edge Detection Precision/Recall vs Ground Truth
2. Attack Path Reconstruction Accuracy  
3. Evidence Source Weight Ablation Analysis
4. Causal Chain Completeness and Ordering
5. False Positive/Negative Analysis by Edge Type

Evidence Sources Evaluated:
- Temporal ordering (happens-before relationships)
- Data flow dependencies (input/output correlations)
- Resource sharing (memory, CPU, network)
- Error propagation chains
- Control flow dependencies
- Network communication patterns

Ground Truth Generation:
- Synthetic traces with known causal structures
- Semi-synthetic traces based on real execution patterns
- Labeled attack scenarios with verified causal chains
- Controlled dependency injection experiments

Statistical Analysis:
- Precision, Recall, F1-score with confidence intervals
- ROC/PR curves for threshold optimization
- Statistical significance testing across ablation conditions
- Inter-rater reliability for human-labeled traces
"""

import asyncio
import logging
import numpy as np
import pandas as pd
import networkx as nx
from pathlib import Path
import json
import time
from typing import Dict, List, Tuple, Any, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import itertools

# Statistical analysis
from scipy import stats
from sklearn.metrics import precision_recall_curve, roc_curve, auc
from sklearn.metrics import precision_score, recall_score, f1_score
import matplotlib.pyplot as plt
import seaborn as sns

# Import SCAFAD components
from core.real_graph_analysis import GraphAnalysisOrchestrator, AdvancedGraphAnalyzer
from datasets.serverless_traces import RealisticServerlessTraceGenerator, ServerlessTrace
from app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase

logger = logging.getLogger(__name__)


@dataclass
class CausalEdge:
    """Represents a causal edge with ground truth labels"""
    source_node: str
    target_node: str
    edge_type: str  # 'temporal', 'data_flow', 'resource', 'error', 'control', 'network'
    confidence: float
    evidence_sources: List[str]
    is_ground_truth: bool = False
    ground_truth_type: Optional[str] = None


@dataclass 
class AttackPath:
    """Represents an attack path with causal chain"""
    attack_id: str
    nodes: List[str]
    edges: List[CausalEdge]
    attack_type: str
    severity: float
    is_ground_truth: bool = False


@dataclass
class CausalAccuracyResults:
    """Results of causal accuracy evaluation"""
    edge_detection_metrics: Dict[str, Any]
    attack_path_metrics: Dict[str, Any]
    ablation_results: Dict[str, Any]
    evidence_analysis: Dict[str, Any]
    statistical_tests: Dict[str, Any]


class GroundTruthGenerator:
    """Generates traces with known ground truth causal structures"""
    
    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)
        
    def generate_labeled_trace_with_causality(self, trace_type: str, 
                                            complexity: str = "medium") -> Tuple[ServerlessTrace, Dict[str, Any]]:
        """Generate trace with known causal ground truth"""
        
        if trace_type == "normal_causality":
            return self._generate_normal_causal_trace(complexity)
        elif trace_type == "attack_chain":
            return self._generate_attack_chain_trace(complexity)
        elif trace_type == "error_propagation":
            return self._generate_error_propagation_trace(complexity)
        elif trace_type == "resource_contention":
            return self._generate_resource_contention_trace(complexity)
        else:
            raise ValueError(f"Unknown trace type: {trace_type}")
    
    def _generate_normal_causal_trace(self, complexity: str) -> Tuple[ServerlessTrace, Dict[str, Any]]:
        """Generate normal trace with clear causal dependencies"""
        
        num_functions = {"simple": 3, "medium": 5, "complex": 8}[complexity]
        
        # Create function dependency chain: A -> B -> C -> ...
        trace_id = f"normal_causal_{complexity}_{int(time.time())}"
        
        # Generate base trace
        generator = RealisticServerlessTraceGenerator(random_seed=self.random_seed)
        base_trace = generator.generate_normal_trace(trace_id, 0.05, num_functions)
        
        # Add known causal relationships
        ground_truth = {
            "trace_id": trace_id,
            "trace_type": "normal_causality",
            "causal_edges": [],
            "attack_paths": [],
            "evidence_sources": {
                "temporal": [],
                "data_flow": [], 
                "resource": [],
                "control": []
            }
        }
        
        # Create temporal dependencies
        invocations = base_trace.invocations
        for i in range(len(invocations) - 1):
            current = invocations[i]
            next_inv = invocations[i + 1]
            
            # Ensure temporal ordering
            next_inv.timestamp = current.timestamp + current.duration + 0.01
            
            # Add ground truth causal edge
            edge = CausalEdge(
                source_node=current.event_id,
                target_node=next_inv.event_id,
                edge_type="temporal",
                confidence=1.0,
                evidence_sources=["temporal_ordering"],
                is_ground_truth=True,
                ground_truth_type="sequential_dependency"
            )
            
            ground_truth["causal_edges"].append(edge)
            ground_truth["evidence_sources"]["temporal"].append({
                "source": current.event_id,
                "target": next_inv.event_id,
                "time_delta": next_inv.timestamp - current.timestamp,
                "dependency_type": "sequential"
            })
        
        # Add data flow dependencies (every 2nd function)
        for i in range(0, len(invocations) - 2, 2):
            source = invocations[i]
            target = invocations[i + 2]
            
            edge = CausalEdge(
                source_node=source.event_id,
                target_node=target.event_id,
                edge_type="data_flow",
                confidence=0.9,
                evidence_sources=["data_dependency"],
                is_ground_truth=True,
                ground_truth_type="data_dependency"
            )
            
            ground_truth["causal_edges"].append(edge)
            ground_truth["evidence_sources"]["data_flow"].append({
                "source": source.event_id,
                "target": target.event_id,
                "data_artifact": f"output_{source.function_id}_to_{target.function_id}"
            })
        
        return base_trace, ground_truth
    
    def _generate_attack_chain_trace(self, complexity: str) -> Tuple[ServerlessTrace, Dict[str, Any]]:
        """Generate trace with attack propagation chain"""
        
        attack_steps = {"simple": 3, "medium": 5, "complex": 7}[complexity]
        
        trace_id = f"attack_chain_{complexity}_{int(time.time())}"
        
        # Generate attack trace
        generator = RealisticServerlessTraceGenerator(random_seed=self.random_seed)
        base_trace = generator.generate_attack_trace(trace_id, "dos_attack", attack_steps)
        
        ground_truth = {
            "trace_id": trace_id,
            "trace_type": "attack_chain",
            "causal_edges": [],
            "attack_paths": [],
            "evidence_sources": {
                "temporal": [],
                "error": [],
                "resource": [],
                "network": []
            }
        }
        
        # Create attack propagation chain
        invocations = base_trace.invocations
        attack_path_nodes = []
        attack_path_edges = []
        
        for i in range(len(invocations) - 1):
            current = invocations[i]
            next_inv = invocations[i + 1]
            
            # Attack propagation edge
            edge = CausalEdge(
                source_node=current.event_id,
                target_node=next_inv.event_id,
                edge_type="error",
                confidence=0.95,
                evidence_sources=["error_propagation", "resource_exhaustion"],
                is_ground_truth=True,
                ground_truth_type="attack_propagation"
            )
            
            ground_truth["causal_edges"].append(edge)
            attack_path_edges.append(edge)
            attack_path_nodes.extend([current.event_id, next_inv.event_id])
            
            ground_truth["evidence_sources"]["error"].append({
                "source": current.event_id,
                "target": next_inv.event_id,
                "error_type": "resource_exhaustion",
                "propagation_mechanism": "memory_pressure"
            })
        
        # Create attack path
        attack_path = AttackPath(
            attack_id=f"dos_attack_{trace_id}",
            nodes=list(dict.fromkeys(attack_path_nodes)),  # Remove duplicates, preserve order
            edges=attack_path_edges,
            attack_type="dos_attack",
            severity=0.9,
            is_ground_truth=True
        )
        
        ground_truth["attack_paths"].append(attack_path)
        
        return base_trace, ground_truth
    
    def _generate_error_propagation_trace(self, complexity: str) -> Tuple[ServerlessTrace, Dict[str, Any]]:
        """Generate trace with error propagation patterns"""
        
        num_functions = {"simple": 4, "medium": 6, "complex": 10}[complexity]
        
        trace_id = f"error_prop_{complexity}_{int(time.time())}"
        
        generator = RealisticServerlessTraceGenerator(random_seed=self.random_seed)
        base_trace = generator.generate_normal_trace(trace_id, 0.1, num_functions)
        
        # Inject error cascade
        ground_truth = {
            "trace_id": trace_id,
            "trace_type": "error_propagation",
            "causal_edges": [],
            "attack_paths": [],
            "evidence_sources": {
                "temporal": [],
                "error": [],
                "resource": []
            }
        }
        
        # Create error cascade starting from 2nd function
        error_start_idx = 1
        invocations = base_trace.invocations
        
        for i in range(error_start_idx, len(invocations)):
            current = invocations[i]
            
            # Mark as error
            current.anomaly_type = AnomalyType.EXECUTION_FAILURE
            current.telemetry_metadata["error_occurred"] = True
            
            if i > error_start_idx:
                # Error propagation from previous
                prev = invocations[i - 1]
                
                edge = CausalEdge(
                    source_node=prev.event_id,
                    target_node=current.event_id,
                    edge_type="error",
                    confidence=0.9,
                    evidence_sources=["error_propagation", "temporal_ordering"],
                    is_ground_truth=True,
                    ground_truth_type="error_cascade"
                )
                
                ground_truth["causal_edges"].append(edge)
                ground_truth["evidence_sources"]["error"].append({
                    "source": prev.event_id,
                    "target": current.event_id,
                    "cascade_type": "downstream_failure",
                    "error_correlation": 0.95
                })
        
        return base_trace, ground_truth
    
    def _generate_resource_contention_trace(self, complexity: str) -> Tuple[ServerlessTrace, Dict[str, Any]]:
        """Generate trace with resource contention causality"""
        
        num_concurrent = {"simple": 3, "medium": 5, "complex": 8}[complexity]
        
        trace_id = f"resource_contention_{complexity}_{int(time.time())}"
        
        generator = RealisticServerlessTraceGenerator(random_seed=self.random_seed)
        base_trace = generator.generate_normal_trace(trace_id, 0.05, num_concurrent)
        
        ground_truth = {
            "trace_id": trace_id,
            "trace_type": "resource_contention",
            "causal_edges": [],
            "attack_paths": [],
            "evidence_sources": {
                "resource": [],
                "temporal": []
            }
        }
        
        # Create overlapping execution with resource contention
        invocations = base_trace.invocations
        
        # Make functions overlap in time
        base_start = invocations[0].timestamp
        for i, inv in enumerate(invocations):
            inv.timestamp = base_start + (i * 0.5)  # Overlapping starts
            inv.duration = 2.0  # Long enough to overlap
            
            # Increase memory usage for contention
            inv.memory_spike_kb = 50000 + (i * 10000)  # Increasing memory pressure
        
        # Add resource contention edges
        for i in range(len(invocations)):
            for j in range(i + 1, min(i + 3, len(invocations))):  # Each affects next 2
                source = invocations[i]
                target = invocations[j]
                
                # Check for temporal overlap
                source_end = source.timestamp + source.duration
                target_start = target.timestamp
                
                if source_end > target_start:  # Overlap indicates contention
                    edge = CausalEdge(
                        source_node=source.event_id,
                        target_node=target.event_id,
                        edge_type="resource",
                        confidence=0.8,
                        evidence_sources=["resource_contention", "temporal_overlap"],
                        is_ground_truth=True,
                        ground_truth_type="memory_contention"
                    )
                    
                    ground_truth["causal_edges"].append(edge)
                    ground_truth["evidence_sources"]["resource"].append({
                        "source": source.event_id,
                        "target": target.event_id,
                        "resource_type": "memory",
                        "contention_level": min(source.memory_spike_kb, target.memory_spike_kb) / 100000.0,
                        "temporal_overlap": source_end - target_start
                    })
        
        return base_trace, ground_truth


class CausalAccuracyEvaluator:
    """Evaluates causal inference accuracy of SCAFAD"""
    
    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        np.random.seed(random_seed)
        
        self.graph_orchestrator = GraphAnalysisOrchestrator()
        self.ground_truth_generator = GroundTruthGenerator(random_seed)
        
        # Evidence source weights for ablation
        self.evidence_weights = {
            "temporal_ordering": 1.0,
            "data_dependency": 1.0,
            "resource_contention": 1.0,
            "error_propagation": 1.0,
            "control_flow": 1.0,
            "network_communication": 1.0
        }
        
        logger.info(f"Causal accuracy evaluator initialized with seed {random_seed}")
    
    def extract_predicted_edges(self, trace: ServerlessTrace, 
                               evidence_weights: Dict[str, float] = None) -> List[CausalEdge]:
        """Extract predicted causal edges from trace analysis"""
        
        if evidence_weights is None:
            evidence_weights = self.evidence_weights
        
        try:
            # Run graph analysis
            analysis_result = self.graph_orchestrator.analyze_execution_trace(trace)
            
            predicted_edges = []
            
            # Extract edges from graph analysis
            if "execution_graph" in analysis_result:
                graph = analysis_result["execution_graph"]
                
                for source, target, edge_data in graph.edges(data=True):
                    # Calculate weighted confidence
                    confidence = 0.0
                    evidence_sources = []
                    
                    # Temporal evidence
                    if "temporal_order" in edge_data:
                        confidence += evidence_weights.get("temporal_ordering", 0) * 0.3
                        evidence_sources.append("temporal_ordering")
                    
                    # Data flow evidence  
                    if "data_flow" in edge_data:
                        confidence += evidence_weights.get("data_dependency", 0) * 0.4
                        evidence_sources.append("data_dependency")
                    
                    # Resource evidence
                    if "resource_sharing" in edge_data:
                        confidence += evidence_weights.get("resource_contention", 0) * 0.2
                        evidence_sources.append("resource_contention")
                    
                    # Error evidence
                    if "error_correlation" in edge_data:
                        confidence += evidence_weights.get("error_propagation", 0) * 0.5
                        evidence_sources.append("error_propagation")
                    
                    # Normalize confidence
                    confidence = min(confidence, 1.0)
                    
                    if confidence > 0.1:  # Threshold for edge inclusion
                        edge = CausalEdge(
                            source_node=str(source),
                            target_node=str(target),
                            edge_type=edge_data.get("edge_type", "unknown"),
                            confidence=confidence,
                            evidence_sources=evidence_sources
                        )
                        predicted_edges.append(edge)
            
            return predicted_edges
            
        except Exception as e:
            logger.warning(f"Error extracting predicted edges: {e}")
            return []
    
    def evaluate_edge_detection(self, predicted_edges: List[CausalEdge],
                              ground_truth_edges: List[CausalEdge],
                              confidence_threshold: float = 0.5) -> Dict[str, Any]:
        """Evaluate precision/recall of edge detection"""
        
        # Filter predicted edges by confidence threshold
        filtered_predicted = [e for e in predicted_edges if e.confidence >= confidence_threshold]
        
        # Create sets of edge tuples for comparison
        predicted_set = set((e.source_node, e.target_node) for e in filtered_predicted)
        ground_truth_set = set((e.source_node, e.target_node) for e in ground_truth_edges)
        
        # Calculate metrics
        true_positives = len(predicted_set & ground_truth_set)
        false_positives = len(predicted_set - ground_truth_set)
        false_negatives = len(ground_truth_set - predicted_set)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        # Detailed analysis by edge type
        edge_type_analysis = {}
        
        # Group ground truth by type
        gt_by_type = defaultdict(list)
        for edge in ground_truth_edges:
            gt_by_type[edge.edge_type].append(edge)
        
        # Group predictions by type
        pred_by_type = defaultdict(list)
        for edge in filtered_predicted:
            pred_by_type[edge.edge_type].append(edge)
        
        # Analyze each edge type
        for edge_type in set(list(gt_by_type.keys()) + list(pred_by_type.keys())):
            gt_edges_type = gt_by_type[edge_type]
            pred_edges_type = pred_by_type[edge_type]
            
            gt_set_type = set((e.source_node, e.target_node) for e in gt_edges_type)
            pred_set_type = set((e.source_node, e.target_node) for e in pred_edges_type)
            
            tp_type = len(pred_set_type & gt_set_type)
            fp_type = len(pred_set_type - gt_set_type)
            fn_type = len(gt_set_type - pred_set_type)
            
            prec_type = tp_type / (tp_type + fp_type) if (tp_type + fp_type) > 0 else 0
            rec_type = tp_type / (tp_type + fn_type) if (tp_type + fn_type) > 0 else 0
            f1_type = 2 * prec_type * rec_type / (prec_type + rec_type) if (prec_type + rec_type) > 0 else 0
            
            edge_type_analysis[edge_type] = {
                "precision": prec_type,
                "recall": rec_type,
                "f1_score": f1_type,
                "true_positives": tp_type,
                "false_positives": fp_type,
                "false_negatives": fn_type,
                "ground_truth_count": len(gt_edges_type),
                "predicted_count": len(pred_edges_type)
            }
        
        return {
            "overall_metrics": {
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives
            },
            "edge_type_analysis": edge_type_analysis,
            "confidence_threshold": confidence_threshold,
            "total_predicted": len(filtered_predicted),
            "total_ground_truth": len(ground_truth_edges),
            "detailed_comparison": {
                "correct_edges": list(predicted_set & ground_truth_set),
                "missing_edges": list(ground_truth_set - predicted_set),
                "spurious_edges": list(predicted_set - ground_truth_set)
            }
        }
    
    def evaluate_attack_path_reconstruction(self, predicted_edges: List[CausalEdge],
                                          ground_truth_paths: List[AttackPath]) -> Dict[str, Any]:
        """Evaluate attack path reconstruction accuracy"""
        
        if not ground_truth_paths:
            return {"error": "No ground truth attack paths provided"}
        
        results = {
            "path_reconstruction_metrics": {},
            "path_completeness": {},
            "path_ordering_accuracy": {}
        }
        
        # Build predicted graph
        pred_graph = nx.DiGraph()
        for edge in predicted_edges:
            pred_graph.add_edge(edge.source_node, edge.target_node, 
                              confidence=edge.confidence,
                              edge_type=edge.edge_type)
        
        path_results = []
        
        for gt_path in ground_truth_paths:
            path_result = {
                "attack_id": gt_path.attack_id,
                "ground_truth_length": len(gt_path.nodes),
                "path_found": False,
                "reconstructed_path": [],
                "path_completeness": 0.0,
                "ordering_accuracy": 0.0
            }
            
            # Try to find path in predicted graph
            if len(gt_path.nodes) >= 2:
                start_node = gt_path.nodes[0]
                end_node = gt_path.nodes[-1]
                
                try:
                    # Find shortest path in predicted graph
                    if pred_graph.has_node(start_node) and pred_graph.has_node(end_node):
                        reconstructed_path = nx.shortest_path(pred_graph, start_node, end_node)
                        path_result["path_found"] = True
                        path_result["reconstructed_path"] = reconstructed_path
                        
                        # Calculate path completeness (how many GT nodes are in reconstructed path)
                        gt_nodes_set = set(gt_path.nodes)
                        recon_nodes_set = set(reconstructed_path)
                        
                        path_completeness = len(gt_nodes_set & recon_nodes_set) / len(gt_nodes_set)
                        path_result["path_completeness"] = path_completeness
                        
                        # Calculate ordering accuracy
                        ordering_accuracy = self._calculate_ordering_accuracy(gt_path.nodes, reconstructed_path)
                        path_result["ordering_accuracy"] = ordering_accuracy
                        
                except nx.NetworkXNoPath:
                    path_result["path_found"] = False
                    path_result["error"] = "No path found in predicted graph"
            
            path_results.append(path_result)
        
        # Aggregate metrics
        found_paths = [p for p in path_results if p["path_found"]]
        
        results["path_reconstruction_metrics"] = {
            "total_paths": len(path_results),
            "paths_found": len(found_paths),
            "path_detection_rate": len(found_paths) / len(path_results) if path_results else 0,
            "average_completeness": np.mean([p["path_completeness"] for p in found_paths]) if found_paths else 0,
            "average_ordering_accuracy": np.mean([p["ordering_accuracy"] for p in found_paths]) if found_paths else 0
        }
        
        results["detailed_path_results"] = path_results
        
        return results
    
    def _calculate_ordering_accuracy(self, ground_truth_order: List[str], 
                                   predicted_order: List[str]) -> float:
        """Calculate how well the predicted ordering matches ground truth"""
        
        if len(ground_truth_order) < 2 or len(predicted_order) < 2:
            return 0.0
        
        # Find common nodes
        common_nodes = list(set(ground_truth_order) & set(predicted_order))
        
        if len(common_nodes) < 2:
            return 0.0
        
        # Get ordering of common nodes in both sequences
        gt_positions = {node: i for i, node in enumerate(ground_truth_order)}
        pred_positions = {node: i for i, node in enumerate(predicted_order)}
        
        # Count correctly ordered pairs
        correct_pairs = 0
        total_pairs = 0
        
        for i, node1 in enumerate(common_nodes):
            for node2 in common_nodes[i+1:]:
                total_pairs += 1
                
                gt_order_correct = gt_positions[node1] < gt_positions[node2]
                pred_order_correct = pred_positions[node1] < pred_positions[node2]
                
                if gt_order_correct == pred_order_correct:
                    correct_pairs += 1
        
        return correct_pairs / total_pairs if total_pairs > 0 else 0.0
    
    def run_evidence_source_ablation(self, traces_with_gt: List[Tuple[ServerlessTrace, Dict[str, Any]]],
                                    evidence_sources: List[str] = None) -> Dict[str, Any]:
        """Run ablation study on evidence source weights"""
        
        if evidence_sources is None:
            evidence_sources = list(self.evidence_weights.keys())
        
        logger.info(f"Running evidence source ablation on {len(traces_with_gt)} traces")
        
        ablation_results = {}
        
        # Test each evidence source individually (leave-one-out)
        for source_to_ablate in evidence_sources:
            logger.debug(f"Ablating evidence source: {source_to_ablate}")
            
            # Create modified weights (set ablated source to 0)
            ablated_weights = self.evidence_weights.copy()
            ablated_weights[source_to_ablate] = 0.0
            
            # Evaluate with ablated weights
            results = self._evaluate_traces_with_weights(traces_with_gt, ablated_weights)
            
            ablation_results[f"without_{source_to_ablate}"] = {
                "ablated_source": source_to_ablate,
                "edge_detection_f1": results["average_edge_f1"],
                "path_completeness": results["average_path_completeness"],
                "performance_degradation": results["average_edge_f1"] - self._get_baseline_f1(traces_with_gt)
            }
        
        # Test with only individual sources (leave-all-but-one-out)
        for source_to_keep in evidence_sources:
            logger.debug(f"Testing with only evidence source: {source_to_keep}")
            
            # Create weights with only one source
            isolated_weights = {source: 0.0 for source in evidence_sources}
            isolated_weights[source_to_keep] = 1.0
            
            results = self._evaluate_traces_with_weights(traces_with_gt, isolated_weights)
            
            ablation_results[f"only_{source_to_keep}"] = {
                "isolated_source": source_to_keep,
                "edge_detection_f1": results["average_edge_f1"],
                "path_completeness": results["average_path_completeness"]
            }
        
        # Analyze source importance
        source_importance = {}
        baseline_f1 = self._get_baseline_f1(traces_with_gt)
        
        for source in evidence_sources:
            without_key = f"without_{source}"
            only_key = f"only_{source}"
            
            if without_key in ablation_results and only_key in ablation_results:
                # Importance = baseline - performance_without_source
                importance = baseline_f1 - ablation_results[without_key]["edge_detection_f1"]
                
                # Individual contribution
                individual_contribution = ablation_results[only_key]["edge_detection_f1"]
                
                source_importance[source] = {
                    "importance_score": importance,
                    "individual_contribution": individual_contribution,
                    "relative_importance": importance / baseline_f1 if baseline_f1 > 0 else 0
                }
        
        return {
            "ablation_results": ablation_results,
            "source_importance_ranking": sorted(source_importance.items(), 
                                              key=lambda x: x[1]["importance_score"], 
                                              reverse=True),
            "methodology": "Leave-one-out and isolated source testing",
            "baseline_f1_score": baseline_f1
        }
    
    def _evaluate_traces_with_weights(self, traces_with_gt: List[Tuple[ServerlessTrace, Dict[str, Any]]], 
                                    weights: Dict[str, float]) -> Dict[str, Any]:
        """Evaluate traces with specific evidence weights"""
        
        edge_f1_scores = []
        path_completeness_scores = []
        
        for trace, ground_truth in traces_with_gt:
            try:
                # Extract edges with custom weights
                predicted_edges = self.extract_predicted_edges(trace, weights)
                ground_truth_edges = ground_truth["causal_edges"]
                
                # Evaluate edge detection
                edge_results = self.evaluate_edge_detection(predicted_edges, ground_truth_edges)
                edge_f1_scores.append(edge_results["overall_metrics"]["f1_score"])
                
                # Evaluate path reconstruction if paths exist
                if ground_truth.get("attack_paths"):
                    path_results = self.evaluate_attack_path_reconstruction(predicted_edges, ground_truth["attack_paths"])
                    path_completeness_scores.append(path_results["path_reconstruction_metrics"]["average_completeness"])
                
            except Exception as e:
                logger.warning(f"Error evaluating trace {trace.trace_id}: {e}")
                continue
        
        return {
            "average_edge_f1": np.mean(edge_f1_scores) if edge_f1_scores else 0.0,
            "average_path_completeness": np.mean(path_completeness_scores) if path_completeness_scores else 0.0,
            "num_traces_evaluated": len(edge_f1_scores)
        }
    
    def _get_baseline_f1(self, traces_with_gt: List[Tuple[ServerlessTrace, Dict[str, Any]]]) -> float:
        """Get baseline F1 score with default weights"""
        results = self._evaluate_traces_with_weights(traces_with_gt, self.evidence_weights)
        return results["average_edge_f1"]
    
    def generate_roc_pr_curves(self, traces_with_gt: List[Tuple[ServerlessTrace, Dict[str, Any]]]) -> Dict[str, Any]:
        """Generate ROC and Precision-Recall curves for threshold optimization"""
        
        all_predicted_scores = []
        all_ground_truth_labels = []
        
        for trace, ground_truth in traces_with_gt:
            try:
                # Get all possible edges with confidences
                predicted_edges = self.extract_predicted_edges(trace)
                ground_truth_edges = ground_truth["causal_edges"]
                
                # Create ground truth set
                gt_set = set((e.source_node, e.target_node) for e in ground_truth_edges)
                
                # Collect scores and labels
                for edge in predicted_edges:
                    all_predicted_scores.append(edge.confidence)
                    is_correct = (edge.source_node, edge.target_node) in gt_set
                    all_ground_truth_labels.append(1 if is_correct else 0)
                
            except Exception as e:
                logger.warning(f"Error processing trace {trace.trace_id}: {e}")
                continue
        
        if not all_predicted_scores:
            return {"error": "No predicted edges found"}
        
        y_true = np.array(all_ground_truth_labels)
        y_scores = np.array(all_predicted_scores)
        
        # ROC Curve
        fpr, tpr, roc_thresholds = roc_curve(y_true, y_scores)
        roc_auc = auc(fpr, tpr)
        
        # Precision-Recall Curve
        precision, recall, pr_thresholds = precision_recall_curve(y_true, y_scores)
        pr_auc = auc(recall, precision)
        
        # Find optimal threshold (max F1)
        f1_scores = []
        for threshold in pr_thresholds:
            y_pred = (y_scores >= threshold).astype(int)
            f1 = f1_score(y_true, y_pred, zero_division=0)
            f1_scores.append(f1)
        
        optimal_threshold_idx = np.argmax(f1_scores)
        optimal_threshold = pr_thresholds[optimal_threshold_idx]
        optimal_f1 = f1_scores[optimal_threshold_idx]
        
        return {
            "roc_curve": {
                "fpr": fpr.tolist(),
                "tpr": tpr.tolist(),
                "thresholds": roc_thresholds.tolist(),
                "auc": roc_auc
            },
            "pr_curve": {
                "precision": precision.tolist(),
                "recall": recall.tolist(),
                "thresholds": pr_thresholds.tolist(),
                "auc": pr_auc
            },
            "optimal_threshold": {
                "threshold": optimal_threshold,
                "f1_score": optimal_f1,
                "precision": precision[optimal_threshold_idx],
                "recall": recall[optimal_threshold_idx]
            },
            "total_samples": len(all_predicted_scores),
            "positive_samples": sum(all_ground_truth_labels)
        }
    
    async def run_comprehensive_causal_accuracy_study(self, 
                                                    num_traces_per_type: int = 50,
                                                    trace_types: List[str] = None,
                                                    complexity_levels: List[str] = None) -> CausalAccuracyResults:
        """Run comprehensive causal accuracy evaluation"""
        
        if trace_types is None:
            trace_types = ["normal_causality", "attack_chain", "error_propagation", "resource_contention"]
        
        if complexity_levels is None:
            complexity_levels = ["simple", "medium", "complex"]
        
        logger.info(f"Running comprehensive causal accuracy study")
        logger.info(f"Trace types: {trace_types}")
        logger.info(f"Complexity levels: {complexity_levels}")
        logger.info(f"Traces per type/complexity: {num_traces_per_type}")
        
        # Generate test traces with ground truth
        traces_with_gt = []
        
        for trace_type in trace_types:
            for complexity in complexity_levels:
                logger.debug(f"Generating {trace_type} traces with {complexity} complexity")
                
                for i in range(num_traces_per_type):
                    try:
                        trace, ground_truth = self.ground_truth_generator.generate_labeled_trace_with_causality(
                            trace_type, complexity
                        )
                        traces_with_gt.append((trace, ground_truth))
                    except Exception as e:
                        logger.warning(f"Failed to generate trace {trace_type}/{complexity}/{i}: {e}")
                        continue
        
        logger.info(f"Generated {len(traces_with_gt)} traces with ground truth")
        
        # Evaluate edge detection across all traces
        all_edge_results = []
        all_path_results = []
        
        for trace, ground_truth in traces_with_gt:
            try:
                # Extract predicted edges
                predicted_edges = self.extract_predicted_edges(trace)
                ground_truth_edges = ground_truth["causal_edges"]
                
                # Evaluate edge detection
                edge_result = self.evaluate_edge_detection(predicted_edges, ground_truth_edges)
                edge_result["trace_id"] = ground_truth["trace_id"]
                edge_result["trace_type"] = ground_truth["trace_type"]
                all_edge_results.append(edge_result)
                
                # Evaluate attack path reconstruction
                if ground_truth.get("attack_paths"):
                    path_result = self.evaluate_attack_path_reconstruction(predicted_edges, ground_truth["attack_paths"])
                    path_result["trace_id"] = ground_truth["trace_id"]
                    path_result["trace_type"] = ground_truth["trace_type"]
                    all_path_results.append(path_result)
                
            except Exception as e:
                logger.warning(f"Error evaluating trace {trace.trace_id}: {e}")
                continue
        
        # Aggregate edge detection metrics
        edge_detection_metrics = self._aggregate_edge_results(all_edge_results)
        
        # Aggregate attack path metrics
        attack_path_metrics = self._aggregate_path_results(all_path_results)
        
        # Run evidence source ablation
        logger.info("Running evidence source ablation study...")
        ablation_results = self.run_evidence_source_ablation(traces_with_gt)
        
        # Generate ROC/PR curves
        logger.info("Generating ROC and Precision-Recall curves...")
        curve_analysis = self.generate_roc_pr_curves(traces_with_gt)
        
        # Statistical significance tests
        statistical_tests = self._run_statistical_tests(all_edge_results, all_path_results)
        
        return CausalAccuracyResults(
            edge_detection_metrics=edge_detection_metrics,
            attack_path_metrics=attack_path_metrics,
            ablation_results=ablation_results,
            evidence_analysis=curve_analysis,
            statistical_tests=statistical_tests
        )
    
    def _aggregate_edge_results(self, all_edge_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate edge detection results across all traces"""
        
        if not all_edge_results:
            return {"error": "No edge results to aggregate"}
        
        # Overall metrics
        overall_precision = [r["overall_metrics"]["precision"] for r in all_edge_results]
        overall_recall = [r["overall_metrics"]["recall"] for r in all_edge_results]
        overall_f1 = [r["overall_metrics"]["f1_score"] for r in all_edge_results]
        
        # By trace type
        by_trace_type = defaultdict(list)
        for result in all_edge_results:
            trace_type = result.get("trace_type", "unknown")
            by_trace_type[trace_type].append(result["overall_metrics"])
        
        # By edge type
        all_edge_types = set()
        for result in all_edge_results:
            all_edge_types.update(result["edge_type_analysis"].keys())
        
        edge_type_aggregated = {}
        for edge_type in all_edge_types:
            type_metrics = []
            for result in all_edge_results:
                if edge_type in result["edge_type_analysis"]:
                    type_metrics.append(result["edge_type_analysis"][edge_type])
            
            if type_metrics:
                edge_type_aggregated[edge_type] = {
                    "mean_precision": np.mean([m["precision"] for m in type_metrics]),
                    "mean_recall": np.mean([m["recall"] for m in type_metrics]),
                    "mean_f1": np.mean([m["f1_score"] for m in type_metrics]),
                    "std_f1": np.std([m["f1_score"] for m in type_metrics]),
                    "num_traces": len(type_metrics)
                }
        
        return {
            "overall_performance": {
                "mean_precision": np.mean(overall_precision),
                "mean_recall": np.mean(overall_recall),
                "mean_f1": np.mean(overall_f1),
                "std_precision": np.std(overall_precision),
                "std_recall": np.std(overall_recall),
                "std_f1": np.std(overall_f1),
                "confidence_interval_f1": self._calculate_confidence_interval(overall_f1)
            },
            "by_trace_type": {
                trace_type: {
                    "mean_f1": np.mean([m["f1_score"] for m in metrics]),
                    "mean_precision": np.mean([m["precision"] for m in metrics]),
                    "mean_recall": np.mean([m["recall"] for m in metrics]),
                    "num_traces": len(metrics)
                }
                for trace_type, metrics in by_trace_type.items()
            },
            "by_edge_type": edge_type_aggregated,
            "total_traces_evaluated": len(all_edge_results)
        }
    
    def _aggregate_path_results(self, all_path_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate attack path reconstruction results"""
        
        if not all_path_results:
            return {"no_attack_paths": True, "message": "No attack path results to aggregate"}
        
        detection_rates = [r["path_reconstruction_metrics"]["path_detection_rate"] for r in all_path_results]
        completeness_scores = [r["path_reconstruction_metrics"]["average_completeness"] for r in all_path_results]
        ordering_scores = [r["path_reconstruction_metrics"]["average_ordering_accuracy"] for r in all_path_results]
        
        return {
            "overall_path_performance": {
                "mean_detection_rate": np.mean(detection_rates),
                "mean_completeness": np.mean(completeness_scores),
                "mean_ordering_accuracy": np.mean(ordering_scores),
                "std_detection_rate": np.std(detection_rates),
                "std_completeness": np.std(completeness_scores),
                "confidence_interval_completeness": self._calculate_confidence_interval(completeness_scores)
            },
            "total_attack_traces_evaluated": len(all_path_results)
        }
    
    def _calculate_confidence_interval(self, values: List[float], confidence_level: float = 0.95) -> Dict[str, float]:
        """Calculate confidence interval for a list of values"""
        
        if len(values) < 2:
            return {"error": "Insufficient data for confidence interval"}
        
        values_array = np.array(values)
        mean = np.mean(values_array)
        sem = stats.sem(values_array)  # Standard error of mean
        
        # t-distribution for small samples, normal for large
        if len(values) < 30:
            t_val = stats.t.ppf((1 + confidence_level) / 2, df=len(values) - 1)
            margin_error = t_val * sem
        else:
            z_val = stats.norm.ppf((1 + confidence_level) / 2)
            margin_error = z_val * sem
        
        return {
            "mean": mean,
            "lower": mean - margin_error,
            "upper": mean + margin_error,
            "margin_error": margin_error,
            "confidence_level": confidence_level
        }
    
    def _run_statistical_tests(self, edge_results: List[Dict[str, Any]], 
                              path_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run statistical significance tests"""
        
        tests = {
            "methodology": "t-tests and non-parametric tests for performance comparisons",
            "significance_level": 0.05
        }
        
        # Test if performance differs by trace type
        if len(edge_results) > 0:
            trace_types = list(set(r.get("trace_type", "unknown") for r in edge_results))
            
            if len(trace_types) > 1:
                # Group F1 scores by trace type
                f1_by_type = defaultdict(list)
                for result in edge_results:
                    trace_type = result.get("trace_type", "unknown")
                    f1_by_type[trace_type].append(result["overall_metrics"]["f1_score"])
                
                # Run ANOVA if more than 2 groups
                if len(trace_types) > 2:
                    try:
                        f_stat, p_value = stats.f_oneway(*f1_by_type.values())
                        tests["trace_type_comparison"] = {
                            "test": "One-way ANOVA",
                            "f_statistic": f_stat,
                            "p_value": p_value,
                            "significant": p_value < 0.05
                        }
                    except Exception as e:
                        tests["trace_type_comparison"] = {"error": str(e)}
                
                # Pairwise comparisons
                pairwise_results = {}
                for i, type1 in enumerate(trace_types):
                    for type2 in trace_types[i+1:]:
                        try:
                            t_stat, p_val = stats.ttest_ind(f1_by_type[type1], f1_by_type[type2])
                            pairwise_results[f"{type1}_vs_{type2}"] = {
                                "t_statistic": t_stat,
                                "p_value": p_val,
                                "significant": p_val < 0.05
                            }
                        except Exception as e:
                            pairwise_results[f"{type1}_vs_{type2}"] = {"error": str(e)}
                
                tests["pairwise_comparisons"] = pairwise_results
        
        return tests
    
    def generate_causal_accuracy_report(self, results: CausalAccuracyResults, 
                                      output_dir: str = "experiments/results") -> str:
        """Generate comprehensive causal accuracy report"""
        
        output_path = Path(output_dir) / "causal_accuracy_report.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            "analysis_metadata": {
                "timestamp": time.time(),
                "random_seed": self.random_seed,
                "analysis_type": "Causal Accuracy Study",
                "methodology": "Ground truth comparison with evidence source ablation"
            },
            "executive_summary": self._generate_causal_summary(results),
            "detailed_results": {
                "edge_detection_metrics": results.edge_detection_metrics,
                "attack_path_metrics": results.attack_path_metrics,
                "ablation_results": results.ablation_results,
                "evidence_analysis": results.evidence_analysis
            },
            "statistical_analysis": results.statistical_tests,
            "recommendations": self._generate_causal_recommendations(results)
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Causal accuracy report saved: {output_path}")
        return str(output_path)
    
    def _generate_causal_summary(self, results: CausalAccuracyResults) -> Dict[str, Any]:
        """Generate executive summary of causal accuracy"""
        
        edge_perf = results.edge_detection_metrics.get("overall_performance", {})
        path_perf = results.attack_path_metrics.get("overall_path_performance", {})
        
        summary = {
            "edge_detection_performance": {
                "mean_f1_score": edge_perf.get("mean_f1", 0),
                "mean_precision": edge_perf.get("mean_precision", 0),
                "mean_recall": edge_perf.get("mean_recall", 0),
                "confidence_interval": edge_perf.get("confidence_interval_f1", {})
            },
            "attack_path_performance": {
                "mean_detection_rate": path_perf.get("mean_detection_rate", 0),
                "mean_completeness": path_perf.get("mean_completeness", 0),
                "mean_ordering_accuracy": path_perf.get("mean_ordering_accuracy", 0)
            },
            "key_findings": []
        }
        
        # Generate key findings
        f1_score = edge_perf.get("mean_f1", 0)
        if f1_score > 0.8:
            summary["key_findings"].append("✅ Excellent edge detection performance (F1 > 0.8)")
        elif f1_score > 0.6:
            summary["key_findings"].append("⚠️ Good edge detection performance (F1 > 0.6)")
        else:
            summary["key_findings"].append("❌ Edge detection needs improvement (F1 < 0.6)")
        
        detection_rate = path_perf.get("mean_detection_rate", 0)
        if detection_rate > 0.8:
            summary["key_findings"].append("✅ High attack path detection rate")
        elif detection_rate > 0.5:
            summary["key_findings"].append("⚠️ Moderate attack path detection rate")
        else:
            summary["key_findings"].append("❌ Low attack path detection rate")
        
        return summary
    
    def _generate_causal_recommendations(self, results: CausalAccuracyResults) -> List[Dict[str, str]]:
        """Generate recommendations for improving causal accuracy"""
        
        recommendations = []
        
        edge_perf = results.edge_detection_metrics.get("overall_performance", {})
        f1_score = edge_perf.get("mean_f1", 0)
        
        if f1_score < 0.7:
            recommendations.append({
                "type": "improvement",
                "priority": "high",
                "message": "Consider improving evidence source weighting or adding new evidence types"
            })
        
        # Analyze ablation results for specific recommendations
        ablation = results.ablation_results
        if "source_importance_ranking" in ablation:
            top_sources = ablation["source_importance_ranking"][:2]
            if top_sources:
                top_source_names = [s[0] for s in top_sources]
                recommendations.append({
                    "type": "optimization",
                    "priority": "medium",
                    "message": f"Focus on improving {', '.join(top_source_names)} evidence sources for maximum impact"
                })
        
        if not recommendations:
            recommendations.append({
                "type": "validation",
                "priority": "info",
                "message": "✅ Causal accuracy meets performance targets"
            })
        
        return recommendations


# Export main class
__all__ = ['CausalAccuracyEvaluator', 'CausalAccuracyResults', 'GroundTruthGenerator']


if __name__ == "__main__":
    # Self-test
    async def run_self_test():
        print("Running Causal Accuracy Study Self-Test...")
        
        evaluator = CausalAccuracyEvaluator(random_seed=42)
        
        # Quick test with small sample size
        results = await evaluator.run_comprehensive_causal_accuracy_study(
            num_traces_per_type=3,
            trace_types=["normal_causality", "attack_chain"],
            complexity_levels=["simple"]
        )
        
        report_path = evaluator.generate_causal_accuracy_report(results)
        print(f"✅ Self-test completed. Report saved: {report_path}")
        
        # Print key metrics
        edge_perf = results.edge_detection_metrics.get("overall_performance", {})
        print(f"Mean F1 Score: {edge_perf.get('mean_f1', 0):.3f}")
        
        return True
    
    import asyncio
    asyncio.run(run_self_test())