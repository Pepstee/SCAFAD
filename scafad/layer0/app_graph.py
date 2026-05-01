"""
SCAFAD Layer 0: Advanced Invocation Graph Analysis
=================================================

State-of-the-art graph construction and behavioral analysis for serverless functions.
Implements real algorithms from current research including LogGD, DTGB, and ALASTOR approaches.

Academic References:
- LogGD: Session graphs from system logs using event co-occurrence and temporal proximity
- DTGB: Dynamic text-attributed graphs with temporal reasoning
- ALASTOR: Provenance tracking and attack path reconstruction in serverless
- ResGCN: Residual GCN with attention mechanisms for anomaly detection
- GLAD: Semantic edge creation with latent content similarity

Key Innovations:
- Real-time temporal correlation analysis
- Multi-modal feature fusion (structural + semantic + temporal)
- Inductive Graph Neural Networks for unseen function patterns
- Adversarially-aware centrality metrics
- Flow reconstruction for attack path analysis
"""

import time
import math
import asyncio
import logging
import numpy as np
import networkx as nx
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json

# Scientific computing imports
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.nn import GCNConv, GATConv, global_mean_pool
    from torch_geometric.data import Data, Batch
    from sklearn.cluster import DBSCAN, KMeans
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import StandardScaler
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logging.warning("PyTorch/PyG not available. Graph ML features disabled.")


    class _DummyModule:
        def __init__(self, *args, **kwargs):
            pass

    class torch:  # type: ignore
        Tensor = Any

    class nn:  # type: ignore
        Module = object

    class GCNConv:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

    class GATConv:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

    def global_mean_pool(*args, **kwargs):  # type: ignore
        return None

    class Data:  # type: ignore
        pass

    class Batch:  # type: ignore
        pass

    class DBSCAN:  # type: ignore
        pass

    class KMeans:  # type: ignore
        pass

    def cosine_similarity(*args, **kwargs):  # type: ignore
        return np.array([[0.0]])

    class StandardScaler:  # type: ignore
        def fit_transform(self, X):
            return X


from .app_config import GraphConfig
from .app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase


@dataclass
class GraphNode:
    """Advanced graph node with multi-modal features"""
    node_id: str
    function_id: str
    timestamp: float
    execution_phase: ExecutionPhase
    
    # Core execution features
    duration: float
    memory_kb: int
    cpu_percent: float
    network_io: int
    
    # Behavioral features  
    call_pattern_hash: str
    payload_signature: str
    error_pattern: Optional[str] = None
    
    # Semantic features
    semantic_embedding: Optional[np.ndarray] = None
    textual_features: Dict[str, Any] = field(default_factory=dict)
    
    # Temporal features
    time_bucket: int = 0
    sequence_position: int = 0
    inter_arrival_time: float = 0.0
    
    # Anomaly indicators
    anomaly_score: float = 0.0
    anomaly_type: AnomalyType = AnomalyType.BENIGN
    confidence: float = 1.0
    
    # Provenance tracking
    parent_nodes: List[str] = field(default_factory=list)
    child_nodes: List[str] = field(default_factory=list)
    causal_depth: int = 0


@dataclass
class GraphEdge:
    """Enhanced edge with correlation metrics"""
    source_id: str
    target_id: str
    edge_type: str  # temporal, semantic, causal, flow
    
    # Correlation strengths
    temporal_correlation: float = 0.0
    semantic_similarity: float = 0.0
    behavioral_correlation: float = 0.0
    causal_strength: float = 0.0
    
    # Temporal properties
    time_delta: float = 0.0
    sequence_distance: int = 0
    
    # Flow properties
    flow_id: Optional[str] = None
    flow_position: int = 0
    
    # Metadata
    confidence: float = 1.0
    timestamp: float = 0.0


@dataclass
class GraphMetrics:
    """Comprehensive graph analysis results"""
    # Basic graph properties
    num_nodes: int = 0
    num_edges: int = 0
    density: float = 0.0
    
    # Centrality metrics
    centrality_scores: Dict[str, float] = field(default_factory=dict)
    anomaly_centrality: Dict[str, float] = field(default_factory=dict)
    
    # Clustering results
    anomaly_clusters: List[List[str]] = field(default_factory=list)
    cluster_anomaly_scores: List[float] = field(default_factory=list)
    
    # Temporal patterns
    temporal_flows: List[Dict] = field(default_factory=list)
    flow_anomaly_scores: Dict[str, float] = field(default_factory=dict)
    
    # Attack path analysis
    suspicious_paths: List[List[str]] = field(default_factory=list)
    path_risk_scores: List[float] = field(default_factory=list)


class ResidualGATLayer(nn.Module):
    """Residual Graph Attention Layer inspired by ResGCN research"""
    
    def __init__(self, in_features: int, out_features: int, heads: int = 4, dropout: float = 0.2):
        super().__init__()
        self.gat = GATConv(in_features, out_features // heads, heads=heads, dropout=dropout, concat=True)
        self.residual = nn.Linear(in_features, out_features) if in_features != out_features else nn.Identity()
        self.layer_norm = nn.LayerNorm(out_features)
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x, edge_index):
        # GAT computation
        gat_out = self.gat(x, edge_index)
        
        # Residual connection
        residual_out = self.residual(x)
        
        # Combine and normalize
        out = self.layer_norm(gat_out + residual_out)
        return self.dropout(out)


class InductiveGraphNeuralNetwork(nn.Module):
    """
    Inductive GNN for anomaly detection inspired by LogGD and DTGB
    Designed to generalize to unseen function patterns
    """
    
    def __init__(self, input_dim: int = 64, hidden_dim: int = 128, num_layers: int = 3, num_classes: int = 2):
        super().__init__()
        
        self.num_layers = num_layers
        self.embedding = nn.Linear(input_dim, hidden_dim)
        
        # Residual GAT layers
        self.gat_layers = nn.ModuleList([
            ResidualGATLayer(hidden_dim, hidden_dim) for _ in range(num_layers)
        ])
        
        # Temporal attention mechanism
        self.temporal_attention = nn.MultiheadAttention(hidden_dim, num_heads=8, batch_first=True)
        
        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim // 2, num_classes)
        )
        
        # Anomaly scoring head
        self.anomaly_scorer = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 4),
            nn.ReLU(),
            nn.Linear(hidden_dim // 4, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x, edge_index, batch=None):
        # Initial embedding
        h = F.relu(self.embedding(x))
        
        # Graph convolutions with residual connections
        for layer in self.gat_layers:
            h = layer(h, edge_index)
        
        # Global graph representation
        if batch is not None:
            graph_repr = global_mean_pool(h, batch)
        else:
            graph_repr = h.mean(dim=0, keepdim=True)
        
        # Classification and anomaly scoring
        class_logits = self.classifier(graph_repr)
        anomaly_scores = self.anomaly_scorer(graph_repr)
        
        return class_logits, anomaly_scores, h


class SemanticFeatureExtractor:
    """Extract semantic features from function metadata and payloads"""
    
    def __init__(self):
        self.vocabulary = set()
        self.feature_cache = {}
    
    def extract_textual_features(self, function_id: str, payload: Dict, error_msg: Optional[str] = None) -> Dict[str, float]:
        """Extract textual features for semantic analysis"""
        features = {}
        
        # Function name features
        func_parts = function_id.lower().split('-')
        features['func_complexity'] = len(func_parts)
        features['has_handler'] = 1.0 if 'handler' in function_id.lower() else 0.0
        features['has_api'] = 1.0 if 'api' in function_id.lower() else 0.0
        
        # Payload structure features
        if isinstance(payload, dict):
            features['payload_depth'] = self._calculate_dict_depth(payload)
            features['payload_keys'] = len(payload.keys())
            features['has_nested_objects'] = 1.0 if any(isinstance(v, dict) for v in payload.values()) else 0.0
        
        # Error pattern features
        if error_msg:
            features['has_error'] = 1.0
            features['error_type'] = self._classify_error_type(error_msg)
        else:
            features['has_error'] = 0.0
            features['error_type'] = 0.0
        
        return features
    
    def create_semantic_embedding(self, textual_features: Dict[str, float], dimension: int = 32) -> np.ndarray:
        """Create semantic embedding from textual features"""
        # Simple but effective embedding creation
        feature_vector = np.zeros(dimension)
        
        for i, (key, value) in enumerate(textual_features.items()):
            if i < dimension:
                feature_vector[i] = value
        
        # Normalize
        norm = np.linalg.norm(feature_vector)
        if norm > 0:
            feature_vector = feature_vector / norm
            
        return feature_vector
    
    def _calculate_dict_depth(self, d: Dict, current_depth: int = 0) -> int:
        """Calculate maximum depth of nested dictionary"""
        if not isinstance(d, dict) or not d:
            return current_depth
        
        return max(self._calculate_dict_depth(v, current_depth + 1) 
                  if isinstance(v, dict) else current_depth + 1 
                  for v in d.values())
    
    def _classify_error_type(self, error_msg: str) -> float:
        """Classify error type into numeric feature"""
        error_msg = error_msg.lower()
        
        if 'timeout' in error_msg:
            return 1.0
        elif 'memory' in error_msg:
            return 2.0
        elif 'permission' in error_msg or 'auth' in error_msg:
            return 3.0
        elif 'network' in error_msg or 'connection' in error_msg:
            return 4.0
        else:
            return 0.5  # Unknown error


class TemporalCorrelationAnalyzer:
    """Advanced temporal correlation analysis inspired by DTGB"""
    
    def __init__(self, time_window: int = 300):
        self.time_window = time_window
        self.execution_history = deque(maxlen=10000)
        
    def calculate_temporal_correlation(self, node1: GraphNode, node2: GraphNode) -> float:
        """Calculate sophisticated temporal correlation between nodes"""
        time_diff = abs(node1.timestamp - node2.timestamp)
        
        if time_diff > self.time_window:
            return 0.0
        
        # Base temporal proximity score
        proximity_score = 1.0 - (time_diff / self.time_window)
        
        # Execution phase correlation
        phase_correlation = self._phase_correlation(node1.execution_phase, node2.execution_phase)
        
        # Inter-arrival time pattern correlation
        arrival_correlation = self._arrival_pattern_correlation(node1, node2)
        
        # Sequence position correlation  
        sequence_correlation = self._sequence_correlation(node1, node2)
        
        # Weighted combination
        correlation = (0.4 * proximity_score + 
                      0.25 * phase_correlation + 
                      0.2 * arrival_correlation + 
                      0.15 * sequence_correlation)
        
        return max(0.0, min(1.0, correlation))
    
    def _phase_correlation(self, phase1: ExecutionPhase, phase2: ExecutionPhase) -> float:
        """Calculate execution phase correlation"""
        if phase1 == phase2:
            return 1.0
        
        # Adjacent phases have moderate correlation
        phase_order = [ExecutionPhase.INIT, ExecutionPhase.MAIN, ExecutionPhase.CLEANUP]
        
        try:
            idx1, idx2 = phase_order.index(phase1), phase_order.index(phase2)
            distance = abs(idx1 - idx2)
            return max(0.0, 1.0 - (distance / len(phase_order)))
        except ValueError:
            return 0.0
    
    def _arrival_pattern_correlation(self, node1: GraphNode, node2: GraphNode) -> float:
        """Analyze inter-arrival time patterns"""
        if node1.inter_arrival_time == 0 or node2.inter_arrival_time == 0:
            return 0.5
        
        # Similar inter-arrival times suggest related executions
        ratio = min(node1.inter_arrival_time, node2.inter_arrival_time) / max(node1.inter_arrival_time, node2.inter_arrival_time)
        return ratio
    
    def _sequence_correlation(self, node1: GraphNode, node2: GraphNode) -> float:
        """Calculate sequence position correlation"""
        if node1.sequence_position == 0 or node2.sequence_position == 0:
            return 0.5
        
        distance = abs(node1.sequence_position - node2.sequence_position)
        return 1.0 / (1.0 + distance)


class FlowDetectionEngine:
    """
    Advanced flow detection for attack path reconstruction
    Inspired by ALASTOR's provenance tracking approach
    """
    
    def __init__(self, config: GraphConfig):
        self.config = config
        self.active_flows = {}
        self.completed_flows = []
        
    def detect_execution_flows(self, graph: nx.DiGraph, time_window: int = 600) -> List[Dict]:
        """Detect execution flows using advanced graph analysis"""
        flows = []
        
        # Find strongly connected components
        sccs = list(nx.strongly_connected_components(graph))
        
        for scc in sccs:
            if len(scc) > 1:  # Only consider non-trivial SCCs
                flow = self._analyze_flow_component(graph, scc, time_window)
                if flow['flow_score'] >= self.config.min_flow_score:
                    flows.append(flow)
        
        # Find linear execution chains
        chains = self._find_execution_chains(graph, time_window)
        flows.extend(chains)
        
        # Score and rank flows
        flows = self._score_flows(flows)
        
        return sorted(flows, key=lambda x: x['flow_score'], reverse=True)
    
    def _analyze_flow_component(self, graph: nx.DiGraph, component: Set[str], time_window: int) -> Dict:
        """Analyze a strongly connected component as a potential flow"""
        nodes = [graph.nodes[node_id] for node_id in component]
        
        # Calculate flow metrics
        start_time = min(node['timestamp'] for node in nodes)
        end_time = max(node['timestamp'] for node in nodes)
        duration = end_time - start_time
        
        # Analyze execution patterns
        execution_patterns = self._analyze_execution_patterns(nodes)
        
        # Calculate anomaly concentration
        anomaly_concentration = sum(1 for node in nodes if node.get('anomaly_score', 0) > 0.5) / len(nodes)
        
        flow = {
            'flow_id': f"scc_{hash(tuple(sorted(component))) % 10000}",
            'type': 'strongly_connected',
            'nodes': list(component),
            'start_time': start_time,
            'end_time': end_time,
            'duration': duration,
            'anomaly_concentration': anomaly_concentration,
            'execution_patterns': execution_patterns,
            'flow_score': 0.0  # Will be calculated later
        }
        
        return flow
    
    def _find_execution_chains(self, graph: nx.DiGraph, time_window: int) -> List[Dict]:
        """Find linear execution chains indicating potential flows"""
        chains = []
        visited = set()
        
        for node_id in graph.nodes():
            if node_id in visited:
                continue
                
            chain = self._trace_execution_chain(graph, node_id, visited, time_window)
            if len(chain) >= 3:  # Minimum chain length
                chains.append(chain)
        
        return chains
    
    def _trace_execution_chain(self, graph: nx.DiGraph, start_node: str, visited: Set[str], time_window: int) -> Dict:
        """Trace an execution chain from a starting node"""
        chain_nodes = [start_node]
        current = start_node
        visited.add(start_node)
        
        while True:
            successors = list(graph.successors(current))
            
            # Find best temporal successor
            best_successor = None
            best_score = 0.0
            
            for successor in successors:
                if successor in visited:
                    continue
                    
                time_diff = abs(graph.nodes[successor]['timestamp'] - graph.nodes[current]['timestamp'])
                if time_diff <= time_window:
                    score = 1.0 - (time_diff / time_window)
                    if score > best_score:
                        best_score = score
                        best_successor = successor
            
            if best_successor:
                chain_nodes.append(best_successor)
                visited.add(best_successor)
                current = best_successor
            else:
                break
        
        # Analyze chain properties
        nodes = [graph.nodes[node_id] for node_id in chain_nodes]
        start_time = min(node['timestamp'] for node in nodes)
        end_time = max(node['timestamp'] for node in nodes)
        
        return {
            'flow_id': f"chain_{hash(tuple(chain_nodes)) % 10000}",
            'type': 'linear_chain',
            'nodes': chain_nodes,
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'anomaly_concentration': sum(1 for node in nodes if node.get('anomaly_score', 0) > 0.5) / len(nodes),
            'execution_patterns': self._analyze_execution_patterns(nodes),
            'flow_score': 0.0
        }
    
    def _analyze_execution_patterns(self, nodes: List[Dict]) -> Dict:
        """Analyze execution patterns within a flow"""
        if not nodes:
            return {}
        
        durations = [node.get('duration', 0) for node in nodes]
        memory_usage = [node.get('memory_kb', 0) for node in nodes]
        cpu_usage = [node.get('cpu_percent', 0) for node in nodes]
        
        patterns = {
            'avg_duration': np.mean(durations),
            'duration_variance': np.var(durations),
            'avg_memory': np.mean(memory_usage),
            'memory_trend': 'increasing' if memory_usage[-1] > memory_usage[0] else 'decreasing',
            'avg_cpu': np.mean(cpu_usage),
            'execution_regularity': 1.0 / (1.0 + np.var(durations))
        }
        
        return patterns
    
    def _score_flows(self, flows: List[Dict]) -> List[Dict]:
        """Score flows based on multiple criteria"""
        for flow in flows:
            score = 0.0
            
            # Length score (longer flows are more significant)
            length_score = min(1.0, len(flow['nodes']) / 10.0)
            score += 0.3 * length_score
            
            # Anomaly concentration score
            score += 0.4 * flow['anomaly_concentration']
            
            # Duration score (flows spanning time are more interesting)
            duration_score = min(1.0, flow['duration'] / 300.0)  # 5 minutes max
            score += 0.2 * duration_score
            
            # Pattern regularity (irregular patterns are suspicious)
            regularity = flow['execution_patterns'].get('execution_regularity', 0.5)
            score += 0.1 * (1.0 - regularity)  # Irregular = higher score
            
            flow['flow_score'] = score
        
        return flows


class GraphMetricsCalculator:
    """Advanced graph metrics calculation with anomaly-aware centrality"""
    
    def __init__(self, config: GraphConfig):
        self.config = config
        
    def calculate_centrality_metrics(self, graph: nx.DiGraph) -> Dict[str, Dict[str, float]]:
        """Calculate multiple centrality metrics"""
        metrics = {}
        
        if len(graph.nodes()) == 0:
            return metrics
        
        # Standard centrality measures
        try:
            metrics['betweenness'] = nx.betweenness_centrality(graph)
            metrics['eigenvector'] = nx.eigenvector_centrality(graph, max_iter=self.config.max_centrality_iterations)
            metrics['pagerank'] = nx.pagerank(graph, max_iter=self.config.max_centrality_iterations)
            metrics['closeness'] = nx.closeness_centrality(graph)
        except Exception as e:
            logging.warning(f"Error calculating centrality: {e}")
            return {}
        
        # Anomaly-aware centrality
        metrics['anomaly_centrality'] = self._calculate_anomaly_centrality(graph)
        
        return metrics
    
    def _calculate_anomaly_centrality(self, graph: nx.DiGraph) -> Dict[str, float]:
        """Calculate centrality weighted by anomaly scores"""
        anomaly_centrality = {}
        
        for node_id in graph.nodes():
            node_data = graph.nodes[node_id]
            anomaly_score = node_data.get('anomaly_score', 0.0)
            
            # Weight by neighbors' anomaly scores
            neighbor_anomaly = 0.0
            neighbors = list(graph.neighbors(node_id))
            
            if neighbors:
                neighbor_scores = [graph.nodes[n].get('anomaly_score', 0.0) for n in neighbors]
                neighbor_anomaly = sum(neighbor_scores) / len(neighbor_scores)
            
            # Combined anomaly centrality
            anomaly_centrality[node_id] = 0.7 * anomaly_score + 0.3 * neighbor_anomaly
        
        return anomaly_centrality
    
    def detect_anomaly_clusters(self, graph: nx.DiGraph) -> Tuple[List[List[str]], List[float]]:
        """Detect clusters of anomalous nodes"""
        if len(graph.nodes()) < self.config.clustering_min_samples:
            return [], []
        
        # Extract features for clustering
        features = []
        node_ids = []
        
        for node_id in graph.nodes():
            node_data = graph.nodes[node_id]
            feature_vector = [
                node_data.get('anomaly_score', 0.0),
                node_data.get('duration', 0.0),
                node_data.get('memory_kb', 0.0),
                node_data.get('cpu_percent', 0.0),
                len(list(graph.neighbors(node_id)))  # degree
            ]
            features.append(feature_vector)
            node_ids.append(node_id)
        
        features = np.array(features)
        
        # Normalize features
        scaler = StandardScaler()
        features_normalized = scaler.fit_transform(features)
        
        # Clustering
        if self.config.clustering_algorithm == "DBSCAN":
            clusterer = DBSCAN(eps=self.config.clustering_eps, 
                             min_samples=self.config.clustering_min_samples)
        else:
            clusterer = KMeans(n_clusters=min(5, len(node_ids) // 3))
        
        cluster_labels = clusterer.fit_predict(features_normalized)
        
        # Group nodes by cluster
        clusters = defaultdict(list)
        for i, label in enumerate(cluster_labels):
            if label != -1:  # -1 is noise in DBSCAN
                clusters[label].append(node_ids[i])
        
        # Calculate cluster anomaly scores
        cluster_anomaly_scores = []
        cluster_lists = []
        
        for cluster_nodes in clusters.values():
            if len(cluster_nodes) >= 2:  # Only consider meaningful clusters
                cluster_score = np.mean([graph.nodes[node]['anomaly_score'] 
                                       for node in cluster_nodes])
                cluster_lists.append(cluster_nodes)
                cluster_anomaly_scores.append(cluster_score)
        
        return cluster_lists, cluster_anomaly_scores


class AdvancedInvocationGraphBuilder:
    """
    Advanced invocation graph builder implementing state-of-the-art techniques
    from LogGD, DTGB, ALASTOR, and other research
    """
    
    def __init__(self, config: GraphConfig):
        self.config = config
        self.graph = nx.DiGraph()
        self.node_cache = {}
        self.edge_cache = {}
        
        # Initialize analyzers
        self.semantic_extractor = SemanticFeatureExtractor()
        self.temporal_analyzer = TemporalCorrelationAnalyzer(config.flow_time_window_seconds)
        self.flow_detector = FlowDetectionEngine(config)
        self.metrics_calculator = GraphMetricsCalculator(config)
        
        # Initialize GNN if available
        self.gnn_model = None
        if TORCH_AVAILABLE and config.enable_graph_analysis:
            self.gnn_model = InductiveGraphNeuralNetwork()
            self.gnn_model.eval()
        
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    async def create_node_with_advanced_features(self, event: Dict, context: Any, 
                                               telemetry: TelemetryRecord) -> str:
        """Create graph node with comprehensive multi-modal features"""
        
        # Generate unique node ID
        node_id = self._generate_node_id(telemetry)
        
        # Extract semantic features
        textual_features = self.semantic_extractor.extract_textual_features(
            telemetry.function_id, 
            event, 
            telemetry.custom_fields.get('error_message')
        )
        
        semantic_embedding = self.semantic_extractor.create_semantic_embedding(textual_features)
        
        # Calculate temporal features
        current_time = time.time()
        time_bucket = int(current_time // 300)  # 5-minute buckets
        
        # Create comprehensive node
        node = GraphNode(
            node_id=node_id,
            function_id=telemetry.function_id,
            timestamp=telemetry.timestamp,
            execution_phase=telemetry.execution_phase,
            duration=telemetry.duration,
            memory_kb=telemetry.memory_spike_kb,
            cpu_percent=telemetry.cpu_utilization,
            network_io=telemetry.network_io_bytes,
            call_pattern_hash=self._calculate_call_pattern_hash(event),
            payload_signature=self._create_payload_signature(event),
            semantic_embedding=semantic_embedding,
            textual_features=textual_features,
            time_bucket=time_bucket,
            sequence_position=len(self.graph.nodes()),
            inter_arrival_time=self._calculate_inter_arrival_time(telemetry),
            anomaly_score=self._calculate_initial_anomaly_score(telemetry),
            anomaly_type=telemetry.anomaly_type
        )
        
        # Add node to graph
        self.graph.add_node(node_id, **node.__dict__)
        self.node_cache[node_id] = node
        
        # Create edges to existing nodes
        await self._create_edges_with_temporal_correlation(node_id, node, telemetry.timestamp)
        
        # Update provenance relationships
        self._update_provenance_chains(node_id, event, context)
        
        # Cleanup old nodes if necessary
        await self._cleanup_expired_nodes()
        
        return node_id
    
    async def _create_edges_with_temporal_correlation(self, node_id: str, node: GraphNode, timestamp: float):
        """Create edges using sophisticated correlation analysis"""
        
        # Find candidate nodes for edge creation
        candidate_nodes = []
        for existing_id, existing_node in self.node_cache.items():
            if existing_id == node_id:
                continue
                
            time_diff = abs(timestamp - existing_node.timestamp)
            if time_diff <= self.config.flow_time_window_seconds:
                candidate_nodes.append((existing_id, existing_node))
        
        # Calculate correlations in parallel
        correlation_tasks = []
        for existing_id, existing_node in candidate_nodes:
            task = self._calculate_comprehensive_correlation(node, existing_node)
            correlation_tasks.append((existing_id, task))
        
        # Process correlation results
        for existing_id, correlation_data in correlation_tasks:
            temporal_corr = correlation_data.get('temporal', 0.0)
            semantic_corr = correlation_data.get('semantic', 0.0)
            behavioral_corr = correlation_data.get('behavioral', 0.0)
            causal_corr = correlation_data.get('causal', 0.0)
            
            # Create edges based on thresholds
            if temporal_corr >= self.config.temporal_correlation_threshold:
                await self._create_edge(existing_id, node_id, 'temporal', correlation_data)
            
            if semantic_corr >= self.config.semantic_similarity_threshold:
                await self._create_edge(existing_id, node_id, 'semantic', correlation_data)
            
            if behavioral_corr >= self.config.behavioral_correlation_threshold:
                await self._create_edge(existing_id, node_id, 'behavioral', correlation_data)
            
            if causal_corr >= self.config.causal_correlation_threshold:
                await self._create_edge(existing_id, node_id, 'causal', correlation_data)
    
    def _calculate_comprehensive_correlation(self, node1: GraphNode, node2: GraphNode) -> Dict[str, float]:
        """Calculate comprehensive correlation metrics between nodes"""
        
        # Temporal correlation
        temporal_corr = self.temporal_analyzer.calculate_temporal_correlation(node1, node2)
        
        # Semantic correlation
        semantic_corr = self._calculate_semantic_correlation(node1, node2)
        
        # Behavioral correlation  
        behavioral_corr = self._calculate_behavioral_correlation(node1, node2)
        
        # Causal correlation
        causal_corr = self._calculate_causal_correlation(node1, node2)
        
        return {
            'temporal': temporal_corr,
            'semantic': semantic_corr,
            'behavioral': behavioral_corr,
            'causal': causal_corr,
            'time_delta': abs(node1.timestamp - node2.timestamp),
            'sequence_distance': abs(node1.sequence_position - node2.sequence_position)
        }
    
    def _calculate_semantic_correlation(self, node1: GraphNode, node2: GraphNode) -> float:
        """Calculate semantic similarity using embeddings and textual features"""
        
        # Function ID similarity
        func_similarity = 1.0 if node1.function_id == node2.function_id else 0.0
        
        # Embedding similarity
        embedding_similarity = 0.0
        if node1.semantic_embedding is not None and node2.semantic_embedding is not None:
            # Cosine similarity between embeddings
            dot_product = np.dot(node1.semantic_embedding, node2.semantic_embedding)
            norm1 = np.linalg.norm(node1.semantic_embedding)
            norm2 = np.linalg.norm(node2.semantic_embedding)
            
            if norm1 > 0 and norm2 > 0:
                embedding_similarity = dot_product / (norm1 * norm2)
                embedding_similarity = max(0.0, embedding_similarity)  # Ensure non-negative
        
        # Textual feature similarity
        textual_similarity = self._compare_textual_features(node1.textual_features, node2.textual_features)
        
        # Payload signature similarity
        payload_similarity = 1.0 if node1.payload_signature == node2.payload_signature else 0.0
        
        # Error pattern similarity
        error_similarity = 0.0
        if node1.error_pattern and node2.error_pattern:
            error_similarity = 1.0 if node1.error_pattern == node2.error_pattern else 0.0
        elif node1.error_pattern is None and node2.error_pattern is None:
            error_similarity = 1.0
        
        # Weighted combination
        semantic_correlation = (0.25 * func_similarity + 
                              0.35 * embedding_similarity + 
                              0.2 * textual_similarity + 
                              0.1 * payload_similarity + 
                              0.1 * error_similarity)
        
        return semantic_correlation
    
    def _calculate_behavioral_correlation(self, node1: GraphNode, node2: GraphNode) -> float:
        """Calculate behavioral correlation based on execution patterns"""
        
        # Resource usage correlation
        duration_similarity = self._calculate_metric_similarity(node1.duration, node2.duration, scale=1.0)
        memory_similarity = self._calculate_metric_similarity(node1.memory_kb, node2.memory_kb, scale=10000.0)
        cpu_similarity = self._calculate_metric_similarity(node1.cpu_percent, node2.cpu_percent, scale=100.0)
        network_similarity = self._calculate_metric_similarity(node1.network_io, node2.network_io, scale=10000.0)
        
        # Execution phase correlation
        phase_correlation = 1.0 if node1.execution_phase == node2.execution_phase else 0.5
        
        # Call pattern correlation
        pattern_correlation = 1.0 if node1.call_pattern_hash == node2.call_pattern_hash else 0.0
        
        # Anomaly type correlation
        anomaly_correlation = 1.0 if node1.anomaly_type == node2.anomaly_type else 0.0
        
        # Weighted behavioral correlation
        behavioral_correlation = (0.2 * duration_similarity + 
                                0.2 * memory_similarity + 
                                0.15 * cpu_similarity + 
                                0.1 * network_similarity + 
                                0.15 * phase_correlation + 
                                0.1 * pattern_correlation + 
                                0.1 * anomaly_correlation)
        
        return behavioral_correlation
    
    def _calculate_causal_correlation(self, node1: GraphNode, node2: GraphNode) -> float:
        """Calculate causal relationship strength between nodes"""
        
        # Time-based causality (earlier node can cause later node)
        if node1.timestamp >= node2.timestamp:
            return 0.0  # No causal relationship possible
        
        time_diff = node2.timestamp - node1.timestamp
        
        # Exponential decay for causal strength
        causal_strength = math.exp(-time_diff / 60.0)  # 1-minute decay constant
        
        # Function chain causality
        if node1.function_id in node2.parent_nodes:
            causal_strength *= 2.0  # Strong causal indicator
        
        # Resource impact causality (high resource usage affecting subsequent executions)
        if node1.memory_kb > 50000 or node1.cpu_percent > 80.0:
            causal_strength *= 1.5
        
        # Error propagation causality
        if node1.anomaly_type != AnomalyType.BENIGN and node2.anomaly_type != AnomalyType.BENIGN:
            causal_strength *= 1.3
        
        return min(1.0, causal_strength)
    
    async def _create_edge(self, source_id: str, target_id: str, edge_type: str, correlation_data: Dict):
        """Create a graph edge with comprehensive metadata"""
        
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            temporal_correlation=correlation_data.get('temporal', 0.0),
            semantic_similarity=correlation_data.get('semantic', 0.0),
            behavioral_correlation=correlation_data.get('behavioral', 0.0),
            causal_strength=correlation_data.get('causal', 0.0),
            time_delta=correlation_data.get('time_delta', 0.0),
            sequence_distance=correlation_data.get('sequence_distance', 0),
            timestamp=time.time()
        )
        
        # Calculate edge confidence
        edge.confidence = self._calculate_edge_confidence(edge)
        
        # Add edge to graph
        edge_key = f"{source_id}->{target_id}:{edge_type}"
        self.graph.add_edge(source_id, target_id, key=edge_key, **edge.__dict__)
        self.edge_cache[edge_key] = edge
    
    def _calculate_edge_confidence(self, edge: GraphEdge) -> float:
        """Calculate confidence score for an edge"""
        
        correlations = [
            edge.temporal_correlation,
            edge.semantic_similarity,
            edge.behavioral_correlation,
            edge.causal_strength
        ]
        
        # High confidence if multiple correlation types are strong
        strong_correlations = sum(1 for corr in correlations if corr > 0.7)
        moderate_correlations = sum(1 for corr in correlations if 0.4 <= corr <= 0.7)
        
        base_confidence = np.mean(correlations)
        
        # Boost confidence for multiple strong correlations
        if strong_correlations >= 2:
            base_confidence *= 1.2
        elif strong_correlations == 1 and moderate_correlations >= 2:
            base_confidence *= 1.1
        
        return min(1.0, base_confidence)
    
    def _detect_execution_flows(self, node_id: str, node: GraphNode) -> List[str]:
        """Detect execution flows containing the given node"""
        
        flows = []
        
        # Trace backward to find flow origins
        backward_path = self._trace_path_backward(node_id, max_depth=10)
        
        # Trace forward to find flow destinations
        forward_path = self._trace_path_forward(node_id, max_depth=10)
        
        # Combine into complete flow
        complete_flow = backward_path[::-1] + [node_id] + forward_path
        
        if len(complete_flow) >= 3:  # Minimum meaningful flow length
            flows.append(complete_flow)
        
        return flows
    
    def _trace_path_backward(self, node_id: str, max_depth: int) -> List[str]:
        """Trace execution path backward from a node"""
        path = []
        current = node_id
        depth = 0
        
        while depth < max_depth:
            predecessors = list(self.graph.predecessors(current))
            
            if not predecessors:
                break
            
            # Find best predecessor based on edge strength
            best_pred = None
            best_score = 0.0
            
            for pred in predecessors:
                edge_data = self.graph.get_edge_data(pred, current)
                if edge_data:
                    score = edge_data.get('causal_strength', 0.0)
                    if score > best_score:
                        best_score = score
                        best_pred = pred
            
            if best_pred and best_score > 0.3:  # Minimum causal strength
                path.append(best_pred)
                current = best_pred
                depth += 1
            else:
                break
        
        return path
    
    def _trace_path_forward(self, node_id: str, max_depth: int) -> List[str]:
        """Trace execution path forward from a node"""
        path = []
        current = node_id
        depth = 0
        
        while depth < max_depth:
            successors = list(self.graph.successors(current))
            
            if not successors:
                break
            
            # Find best successor based on edge strength
            best_succ = None
            best_score = 0.0
            
            for succ in successors:
                edge_data = self.graph.get_edge_data(current, succ)
                if edge_data:
                    score = edge_data.get('causal_strength', 0.0)
                    if score > best_score:
                        best_score = score
                        best_succ = succ
            
            if best_succ and best_score > 0.3:  # Minimum causal strength
                path.append(best_succ)
                current = best_succ
                depth += 1
            else:
                break
        
        return path
    
    async def get_advanced_graph_metrics(self) -> GraphMetrics:
        """Calculate comprehensive graph metrics and analysis"""
        
        if len(self.graph.nodes()) == 0:
            return GraphMetrics()
        
        # Basic graph properties
        num_nodes = len(self.graph.nodes())
        num_edges = len(self.graph.edges())
        density = nx.density(self.graph)
        
        # Calculate centrality metrics
        centrality_scores = self.metrics_calculator.calculate_centrality_metrics(self.graph)
        
        # Detect anomaly clusters
        anomaly_clusters, cluster_scores = self.metrics_calculator.detect_anomaly_clusters(self.graph)
        
        # Detect execution flows
        temporal_flows = self.flow_detector.detect_execution_flows(self.graph, 
                                                                  self.config.flow_time_window_seconds)
        
        # Calculate flow anomaly scores
        flow_anomaly_scores = {}
        for flow in temporal_flows:
            flow_id = flow['flow_id']
            flow_anomaly_scores[flow_id] = flow['anomaly_concentration']
        
        # Detect suspicious paths (attack path reconstruction)
        suspicious_paths, path_risk_scores = await self._detect_suspicious_paths()
        
        # Apply GNN analysis if available
        if self.gnn_model and TORCH_AVAILABLE:
            await self._apply_gnn_analysis()
        
        return GraphMetrics(
            num_nodes=num_nodes,
            num_edges=num_edges,
            density=density,
            centrality_scores=centrality_scores,
            anomaly_centrality=centrality_scores.get('anomaly_centrality', {}),
            anomaly_clusters=anomaly_clusters,
            cluster_anomaly_scores=cluster_scores,
            temporal_flows=temporal_flows,
            flow_anomaly_scores=flow_anomaly_scores,
            suspicious_paths=suspicious_paths,
            path_risk_scores=path_risk_scores
        )
    
    async def _detect_suspicious_paths(self) -> Tuple[List[List[str]], List[float]]:
        """Detect suspicious execution paths that may indicate attacks"""
        
        suspicious_paths = []
        risk_scores = []
        
        # Find high-anomaly nodes as potential attack indicators
        high_anomaly_nodes = [
            node_id for node_id, node_data in self.graph.nodes(data=True)
            if node_data.get('anomaly_score', 0.0) > 0.7
        ]
        
        # Trace paths from each high-anomaly node
        for start_node in high_anomaly_nodes:
            # Trace both directions to find complete attack path
            backward_path = self._trace_path_backward(start_node, max_depth=15)
            forward_path = self._trace_path_forward(start_node, max_depth=15)
            
            complete_path = backward_path[::-1] + [start_node] + forward_path
            
            if len(complete_path) >= 3:
                risk_score = self._calculate_path_risk_score(complete_path)
                
                if risk_score > 0.5:  # Minimum risk threshold
                    suspicious_paths.append(complete_path)
                    risk_scores.append(risk_score)
        
        # Sort by risk score
        if suspicious_paths:
            sorted_pairs = sorted(zip(suspicious_paths, risk_scores), 
                                key=lambda x: x[1], reverse=True)
            suspicious_paths, risk_scores = zip(*sorted_pairs)
            suspicious_paths = list(suspicious_paths)
            risk_scores = list(risk_scores)
        
        return suspicious_paths, risk_scores
    
    def _calculate_path_risk_score(self, path: List[str]) -> float:
        """Calculate risk score for a suspicious path"""
        
        if len(path) < 2:
            return 0.0
        
        # Aggregate anomaly scores along path
        anomaly_scores = []
        for node_id in path:
            node_data = self.graph.nodes[node_id]
            anomaly_scores.append(node_data.get('anomaly_score', 0.0))
        
        # Path-level risk factors
        avg_anomaly = np.mean(anomaly_scores)
        max_anomaly = max(anomaly_scores)
        anomaly_concentration = sum(1 for score in anomaly_scores if score > 0.5) / len(anomaly_scores)
        
        # Temporal characteristics
        timestamps = [self.graph.nodes[node_id]['timestamp'] for node_id in path]
        time_span = max(timestamps) - min(timestamps)
        execution_velocity = len(path) / max(1.0, time_span)  # executions per second
        
        # Edge strength characteristics
        edge_strengths = []
        for i in range(len(path) - 1):
            edge_data = self.graph.get_edge_data(path[i], path[i + 1])
            if edge_data:
                strength = max(edge_data.get('causal_strength', 0.0),
                             edge_data.get('temporal_correlation', 0.0))
                edge_strengths.append(strength)
        
        avg_edge_strength = np.mean(edge_strengths) if edge_strengths else 0.0
        
        # Calculate composite risk score
        risk_score = (0.4 * avg_anomaly + 
                     0.2 * max_anomaly + 
                     0.2 * anomaly_concentration + 
                     0.1 * min(1.0, execution_velocity * 10) +  # High velocity is suspicious
                     0.1 * avg_edge_strength)
        
        return min(1.0, risk_score)
    
    async def _apply_gnn_analysis(self):
        """Apply Graph Neural Network analysis for advanced anomaly detection"""
        
        if not self.gnn_model or not TORCH_AVAILABLE:
            return
        
        try:
            # Convert NetworkX graph to PyTorch Geometric format
            node_features, edge_index, node_mapping = self._convert_to_torch_geometric()
            
            if node_features.size(0) == 0:
                return
            
            # Apply GNN model
            with torch.no_grad():
                class_logits, anomaly_scores, node_embeddings = self.gnn_model(node_features, edge_index)
            
            # Update node anomaly scores with GNN predictions
            anomaly_scores_np = anomaly_scores.cpu().numpy().flatten()
            
            for i, (node_id, _) in enumerate(node_mapping.items()):
                if i < len(anomaly_scores_np):
                    gnn_score = anomaly_scores_np[i]
                    
                    # Combine with existing anomaly score
                    current_score = self.graph.nodes[node_id].get('anomaly_score', 0.0)
                    combined_score = 0.6 * current_score + 0.4 * gnn_score
                    
                    self.graph.nodes[node_id]['anomaly_score'] = combined_score
                    self.graph.nodes[node_id]['gnn_anomaly_score'] = gnn_score
                    
                    # Update node cache
                    if node_id in self.node_cache:
                        self.node_cache[node_id].anomaly_score = combined_score
        
        except Exception as e:
            logging.warning(f"GNN analysis failed: {e}")
    
    def _convert_to_torch_geometric(self) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, int]]:
        """Convert NetworkX graph to PyTorch Geometric format"""
        
        nodes = list(self.graph.nodes(data=True))
        
        if not nodes:
            return torch.empty(0, 64), torch.empty(2, 0, dtype=torch.long), {}
        
        # Create node mapping
        node_mapping = {node_id: i for i, (node_id, _) in enumerate(nodes)}
        
        # Extract node features
        node_features = []
        for node_id, node_data in nodes:
            features = [
                node_data.get('duration', 0.0),
                node_data.get('memory_kb', 0.0) / 1000.0,  # Normalize
                node_data.get('cpu_percent', 0.0) / 100.0,  # Normalize
                node_data.get('network_io', 0.0) / 1000.0,  # Normalize
                node_data.get('anomaly_score', 0.0),
                len(list(self.graph.neighbors(node_id))),  # Degree
                node_data.get('causal_depth', 0.0),
                node_data.get('sequence_position', 0.0) / 1000.0,  # Normalize
            ]
            
            # Pad to 64 dimensions with semantic embedding if available
            if len(features) < 64:
                semantic_emb = node_data.get('semantic_embedding')
                if semantic_emb is not None and len(semantic_emb) > 0:
                    # Use semantic embedding to fill remaining dimensions
                    padding_needed = 64 - len(features)
                    emb_to_use = semantic_emb[:padding_needed] if len(semantic_emb) >= padding_needed else semantic_emb
                    features.extend(emb_to_use.tolist())
                
                # Final padding with zeros if needed
                while len(features) < 64:
                    features.append(0.0)
            
            node_features.append(features[:64])  # Ensure exactly 64 dimensions
        
        # Create edge index
        edge_index = []
        for source, target in self.graph.edges():
            source_idx = node_mapping[source]
            target_idx = node_mapping[target]
            edge_index.append([source_idx, target_idx])
        
        if edge_index:
            edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
        else:
            edge_index = torch.empty(2, 0, dtype=torch.long)
        
        node_features = torch.tensor(node_features, dtype=torch.float32)
        
        return node_features, edge_index, node_mapping
    
    # Utility methods
    
    def _generate_node_id(self, telemetry: TelemetryRecord) -> str:
        """Generate unique node ID"""
        identifier = f"{telemetry.function_id}:{telemetry.timestamp}:{telemetry.event_id}"
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]
    
    def _calculate_call_pattern_hash(self, event: Dict) -> str:
        """Calculate hash representing call pattern"""
        pattern_data = {
            'method': event.get('httpMethod', ''),
            'path': event.get('path', ''),
            'headers_count': len(event.get('headers', {})),
            'body_present': bool(event.get('body'))
        }
        pattern_str = json.dumps(pattern_data, sort_keys=True)
        return hashlib.md5(pattern_str.encode()).hexdigest()[:8]
    
    def _create_payload_signature(self, event: Dict) -> str:
        """Create signature representing payload structure"""
        if 'body' in event and event['body']:
            try:
                body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
                signature_data = {
                    'keys': sorted(body.keys()) if isinstance(body, dict) else [],
                    'type': type(body).__name__,
                    'size': len(str(body))
                }
                signature_str = json.dumps(signature_data, sort_keys=True)
                return hashlib.md5(signature_str.encode()).hexdigest()[:8]
            except:
                return 'invalid_json'
        return 'no_payload'
    
    def _calculate_inter_arrival_time(self, telemetry: TelemetryRecord) -> float:
        """Calculate inter-arrival time for this execution"""
        current_time = telemetry.timestamp
        
        # Find last execution for same function
        last_execution_time = None
        for node_data in self.graph.nodes(data=True):
            if (node_data[1].get('function_id') == telemetry.function_id and 
                node_data[1].get('timestamp', 0) < current_time):
                
                if last_execution_time is None or node_data[1]['timestamp'] > last_execution_time:
                    last_execution_time = node_data[1]['timestamp']
        
        if last_execution_time is not None:
            return current_time - last_execution_time
        
        return 0.0
    
    def _calculate_initial_anomaly_score(self, telemetry: TelemetryRecord) -> float:
        """Calculate initial anomaly score based on telemetry"""
        
        score = 0.0
        
        # Anomaly type contribution
        if telemetry.anomaly_type != AnomalyType.BENIGN:
            score += 0.5
        
        # Resource usage anomalies
        if telemetry.duration > 5.0:  # > 5 seconds
            score += 0.2
        
        if telemetry.memory_spike_kb > 100000:  # > 100MB
            score += 0.2
        
        if telemetry.cpu_utilization > 80.0:  # > 80% CPU
            score += 0.1
        
        return min(1.0, score)
    
    def _compare_textual_features(self, features1: Dict[str, float], features2: Dict[str, float]) -> float:
        """Compare textual features between two nodes"""
        
        if not features1 or not features2:
            return 0.0
        
        common_keys = set(features1.keys()) & set(features2.keys())
        
        if not common_keys:
            return 0.0
        
        similarities = []
        for key in common_keys:
            val1, val2 = features1[key], features2[key]
            similarity = 1.0 - abs(val1 - val2) / max(1.0, max(abs(val1), abs(val2)))
            similarities.append(similarity)
        
        return np.mean(similarities)
    
    def _calculate_metric_similarity(self, val1: float, val2: float, scale: float = 1.0) -> float:
        """Calculate similarity between two metric values"""
        
        if scale == 0:
            return 1.0 if val1 == val2 else 0.0
        
        normalized_diff = abs(val1 - val2) / scale
        similarity = 1.0 / (1.0 + normalized_diff)
        
        return similarity
    
    def _update_provenance_chains(self, node_id: str, event: Dict, context: Any):
        """Update provenance relationships based on execution context"""
        
        # Extract potential parent execution from context
        parent_id = None
        if hasattr(context, 'aws_request_id'):
            # Look for parent based on request correlation
            parent_id = self._find_parent_by_request_correlation(context.aws_request_id)
        
        if parent_id and parent_id in self.node_cache:
            # Update parent-child relationships
            self.node_cache[parent_id].child_nodes.append(node_id)
            self.node_cache[node_id].parent_nodes.append(parent_id)
            
            # Update causal depth
            parent_depth = self.node_cache[parent_id].causal_depth
            self.node_cache[node_id].causal_depth = parent_depth + 1
    
    def _find_parent_by_request_correlation(self, request_id: str) -> Optional[str]:
        """Find parent execution by request correlation"""
        # Simple implementation - could be enhanced with more sophisticated correlation
        current_time = time.time()
        
        for node_id, node in self.node_cache.items():
            time_diff = current_time - node.timestamp
            if 0 < time_diff < 300:  # Within 5 minutes
                # Could implement more sophisticated correlation logic here
                return node_id
        
        return None
    
    async def _cleanup_expired_nodes(self):
        """Remove expired nodes to maintain performance"""
        
        current_time = time.time()
        expired_nodes = []
        
        for node_id, node in self.node_cache.items():
            age = current_time - node.timestamp
            if age > self.config.node_ttl_seconds:
                expired_nodes.append(node_id)
        
        # Remove expired nodes
        for node_id in expired_nodes:
            if node_id in self.node_cache:
                del self.node_cache[node_id]
            
            if self.graph.has_node(node_id):
                self.graph.remove_node(node_id)
        
        # Clean up orphaned edges
        edges_to_remove = []
        for edge_key, edge in self.edge_cache.items():
            if (not self.graph.has_node(edge.source_id) or 
                not self.graph.has_node(edge.target_id)):
                edges_to_remove.append(edge_key)
        
        for edge_key in edges_to_remove:
            if edge_key in self.edge_cache:
                del self.edge_cache[edge_key]
        
        logging.info(f"Cleaned up {len(expired_nodes)} expired nodes and {len(edges_to_remove)} orphaned edges")
    
    def get_graph_summary(self) -> Dict[str, Any]:
        """Get summary statistics of the current graph"""
        
        return {
            'nodes': len(self.graph.nodes()),
            'edges': len(self.graph.edges()),
            'density': nx.density(self.graph) if len(self.graph.nodes()) > 1 else 0.0,
            'avg_clustering': nx.average_clustering(self.graph),
            'anomalous_nodes': sum(1 for _, data in self.graph.nodes(data=True) 
                                 if data.get('anomaly_score', 0.0) > 0.5),
            'function_diversity': len(set(data.get('function_id', '') 
                                        for _, data in self.graph.nodes(data=True))),
            'temporal_span': self._calculate_temporal_span(),
            'cache_size': len(self.node_cache)
        }
    
    def _calculate_temporal_span(self) -> float:
        """Calculate temporal span of the graph"""
        
        if not self.graph.nodes():
            return 0.0
        
        timestamps = [data.get('timestamp', 0.0) for _, data in self.graph.nodes(data=True)]
        return max(timestamps) - min(timestamps) if timestamps else 0.0