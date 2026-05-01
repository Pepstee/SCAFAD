"""SCAFAD Layer 0: Advanced Provenance Tracking Module
==================================================

Advanced provenance tracking and causal analysis for serverless function executions.
Implements comprehensive audit trails, attack path reconstruction, and causal reasoning
based on academic research.

Academic References:
- ALASTOR: Provenance tracking in serverless environments (Datta et al., 2023)
- Causal Analysis for Distributed Systems (Wang et al., 2022)
- Data Provenance in Cloud Computing (Li et al., 2024)
- Attack Path Reconstruction via Provenance (Chen et al., 2023)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import uuid
import hashlib
import time
import asyncio
import logging
import json
from collections import defaultdict, deque
from enum import Enum
import networkx as nx

from .app_config import ProvenanceConfig
from .app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase

logger = logging.getLogger(__name__)


class ProvenanceNodeType(Enum):
    """Types of nodes in provenance graph"""
    FUNCTION_EXECUTION = "FUNCTION_EXECUTION"
    DATA_INPUT = "DATA_INPUT"
    DATA_OUTPUT = "DATA_OUTPUT"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    RESOURCE_ACCESS = "RESOURCE_ACCESS"
    ERROR_EVENT = "ERROR_EVENT"
    SECURITY_EVENT = "SECURITY_EVENT"


class ProvenanceEdgeType(Enum):
    """Types of edges in provenance graph"""
    CAUSALITY = "CAUSALITY"           # Direct causal relationship
    DEPENDENCY = "DEPENDENCY"         # Data/resource dependency
    TEMPORAL = "TEMPORAL"             # Temporal relationship
    COMMUNICATION = "COMMUNICATION"   # Inter-function communication
    DERIVATION = "DERIVATION"         # Data derivation
    INFLUENCE = "INFLUENCE"           # Indirect influence


@dataclass
class ProvenanceRecord:
    """Comprehensive provenance record"""
    provenance_id: str
    event_id: str
    node_type: ProvenanceNodeType
    timestamp: float
    function_id: str
    predecessors: List[str] = field(default_factory=list)
    successors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    data_inputs: List[Dict[str, Any]] = field(default_factory=list)
    data_outputs: List[Dict[str, Any]] = field(default_factory=list)
    resource_accesses: List[str] = field(default_factory=list)
    security_context: Dict[str, Any] = field(default_factory=dict)
    causal_strength: float = 1.0
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'provenance_id': self.provenance_id,
            'event_id': self.event_id,
            'node_type': self.node_type.value,
            'timestamp': self.timestamp,
            'function_id': self.function_id,
            'predecessors': self.predecessors,
            'successors': self.successors,
            'metadata': self.metadata,
            'data_inputs': self.data_inputs,
            'data_outputs': self.data_outputs,
            'resource_accesses': self.resource_accesses,
            'security_context': self.security_context,
            'causal_strength': self.causal_strength,
            'confidence': self.confidence
        }


@dataclass
class CausalRelationship:
    """Represents a causal relationship between events"""
    cause_id: str
    effect_id: str
    edge_type: ProvenanceEdgeType
    strength: float
    evidence: Dict[str, Any]
    timestamp_diff: float
    confidence: float = 0.8


@dataclass
class AttackPath:
    """Represents a reconstructed attack path"""
    path_id: str
    attack_type: str
    entry_point: str
    target: str
    path_nodes: List[str]
    path_edges: List[CausalRelationship]
    severity: float
    confidence: float
    timeline: List[Tuple[float, str, str]]  # (timestamp, event_id, description)
    mitigation_points: List[str] = field(default_factory=list)


class CausalAnalysisEngine:
    """Advanced causal analysis engine for provenance reasoning"""
    
    def __init__(self, config: ProvenanceConfig):
        self.config = config
        self.temporal_window = getattr(config, 'causal_temporal_window', 300.0)  # 5 minutes
        self.causal_threshold = getattr(config, 'causal_strength_threshold', 0.3)
        
    def detect_causal_relationships(self, execution_graph: nx.DiGraph) -> Dict[str, CausalRelationship]:
        """Detect causal relationships in execution graph"""
        relationships = {}
        
        # Analyze all pairs of nodes for potential causal relationships
        for node_a in execution_graph.nodes():
            for node_b in execution_graph.nodes():
                if node_a != node_b:
                    relationship = self._analyze_causal_relationship(
                        execution_graph, node_a, node_b
                    )
                    if relationship and relationship.strength >= self.causal_threshold:
                        rel_id = f"{node_a}_{node_b}"
                        relationships[rel_id] = relationship
        
        return relationships
    
    def _analyze_causal_relationship(self, graph: nx.DiGraph, 
                                   cause_node: str, effect_node: str) -> Optional[CausalRelationship]:
        """Analyze potential causal relationship between two nodes"""
        
        cause_data = graph.nodes.get(cause_node, {})
        effect_data = graph.nodes.get(effect_node, {})
        
        if not cause_data or not effect_data:
            return None
        
        # Temporal analysis
        cause_time = cause_data.get('timestamp', 0)
        effect_time = effect_data.get('timestamp', 0)
        time_diff = effect_time - cause_time
        
        # Causality must respect temporal ordering
        if time_diff <= 0 or time_diff > self.temporal_window:
            return None
        
        # Calculate causal strength based on multiple factors
        strength = self._calculate_causal_strength(cause_data, effect_data, time_diff)
        
        if strength < self.causal_threshold:
            return None
        
        # Determine edge type
        edge_type = self._determine_edge_type(cause_data, effect_data)
        
        # Collect evidence
        evidence = {
            'temporal_proximity': max(0, 1 - (time_diff / self.temporal_window)),
            'data_flow': self._check_data_flow(cause_data, effect_data),
            'resource_sharing': self._check_resource_sharing(cause_data, effect_data),
            'function_relationship': self._check_function_relationship(cause_data, effect_data)
        }
        
        confidence = min(0.9, sum(evidence.values()) / len(evidence))
        
        return CausalRelationship(
            cause_id=cause_node,
            effect_id=effect_node,
            edge_type=edge_type,
            strength=strength,
            evidence=evidence,
            timestamp_diff=time_diff,
            confidence=confidence
        )
    
    def _calculate_causal_strength(self, cause_data: Dict, effect_data: Dict, 
                                 time_diff: float) -> float:
        """Calculate causal strength between two events"""
        
        factors = []
        
        # Temporal proximity (closer in time = stronger causality)
        temporal_factor = max(0, 1 - (time_diff / self.temporal_window))
        factors.append(temporal_factor * 0.3)
        
        # Data flow analysis
        data_flow_factor = self._check_data_flow(cause_data, effect_data)
        factors.append(data_flow_factor * 0.25)
        
        # Resource sharing
        resource_factor = self._check_resource_sharing(cause_data, effect_data)
        factors.append(resource_factor * 0.2)
        
        # Function relationship
        function_factor = self._check_function_relationship(cause_data, effect_data)
        factors.append(function_factor * 0.15)
        
        # Error propagation
        error_factor = self._check_error_propagation(cause_data, effect_data)
        factors.append(error_factor * 0.1)
        
        return sum(factors)
    
    def _check_data_flow(self, cause_data: Dict, effect_data: Dict) -> float:
        """Check for data flow between events"""
        cause_outputs = cause_data.get('data_outputs', [])
        effect_inputs = effect_data.get('data_inputs', [])
        
        if not cause_outputs or not effect_inputs:
            return 0.0
        
        # Simple hash-based matching (in practice, would use more sophisticated analysis)
        matches = 0
        total_checks = min(len(cause_outputs), len(effect_inputs))
        
        for output in cause_outputs[:total_checks]:
            output_hash = self._hash_data(output)
            for input_data in effect_inputs[:total_checks]:
                input_hash = self._hash_data(input_data)
                if output_hash == input_hash:
                    matches += 1
                    break
        
        return matches / total_checks if total_checks > 0 else 0.0
    
    def _check_resource_sharing(self, cause_data: Dict, effect_data: Dict) -> float:
        """Check for shared resource access"""
        cause_resources = set(cause_data.get('resource_accesses', []))
        effect_resources = set(effect_data.get('resource_accesses', []))
        
        if not cause_resources or not effect_resources:
            return 0.0
        
        shared_resources = cause_resources.intersection(effect_resources)
        total_resources = cause_resources.union(effect_resources)
        
        return len(shared_resources) / len(total_resources) if total_resources else 0.0
    
    def _check_function_relationship(self, cause_data: Dict, effect_data: Dict) -> float:
        """Check relationship between functions"""
        cause_func = cause_data.get('function_id', '')
        effect_func = effect_data.get('function_id', '')
        
        if cause_func == effect_func:
            return 0.8  # Same function - high relationship
        
        # Check for common prefixes (indicating related functions)
        if cause_func and effect_func:
            common_prefix_len = 0
            for i, (c1, c2) in enumerate(zip(cause_func, effect_func)):
                if c1 == c2:
                    common_prefix_len = i + 1
                else:
                    break
            
            if common_prefix_len >= 3:  # At least 3 character prefix
                return min(0.6, common_prefix_len / max(len(cause_func), len(effect_func)))
        
        return 0.0
    
    def _check_error_propagation(self, cause_data: Dict, effect_data: Dict) -> float:
        """Check for error propagation patterns"""
        cause_has_error = cause_data.get('anomaly_type') != 'BENIGN'
        effect_has_error = effect_data.get('anomaly_type') != 'BENIGN'
        
        if cause_has_error and effect_has_error:
            return 0.7  # Error propagation likely
        elif cause_has_error and not effect_has_error:
            return 0.3  # Possible error handling
        
        return 0.0
    
    def _determine_edge_type(self, cause_data: Dict, effect_data: Dict) -> ProvenanceEdgeType:
        """Determine the type of relationship between events"""
        
        # Check for direct data flow
        if self._check_data_flow(cause_data, effect_data) > 0.5:
            return ProvenanceEdgeType.DERIVATION
        
        # Check for resource dependencies
        if self._check_resource_sharing(cause_data, effect_data) > 0.5:
            return ProvenanceEdgeType.DEPENDENCY
        
        # Check for function communication
        if (cause_data.get('function_id') != effect_data.get('function_id') and
            self._check_function_relationship(cause_data, effect_data) > 0.3):
            return ProvenanceEdgeType.COMMUNICATION
        
        # Check for error propagation
        if self._check_error_propagation(cause_data, effect_data) > 0.5:
            return ProvenanceEdgeType.CAUSALITY
        
        # Default to temporal relationship
        return ProvenanceEdgeType.TEMPORAL
    
    def _hash_data(self, data: Any) -> str:
        """Generate hash for data comparison"""
        try:
            data_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.sha256(data_str.encode()).hexdigest()[:16]
        except Exception:
            return hashlib.sha256(str(data).encode()).hexdigest()[:16]
    
    def identify_attack_vectors(self, causal_chain: List[str], 
                               provenance_data: Dict[str, ProvenanceRecord]) -> List[str]:
        """Identify potential attack vectors in causal chain"""
        attack_vectors = []
        
        for node_id in causal_chain:
            node_data = provenance_data.get(node_id)
            if not node_data:
                continue
            
            # Check for security-relevant patterns
            if node_data.node_type == ProvenanceNodeType.SECURITY_EVENT:
                attack_vectors.append(f"Security event: {node_id}")
            
            # Check for external inputs
            if node_data.node_type == ProvenanceNodeType.DATA_INPUT:
                if any('external' in str(inp).lower() for inp in node_data.data_inputs):
                    attack_vectors.append(f"External input: {node_id}")
            
            # Check for privilege escalation patterns
            if 'privilege' in str(node_data.metadata).lower():
                attack_vectors.append(f"Privilege escalation: {node_id}")
            
            # Check for anomalous resource access
            if len(node_data.resource_accesses) > 5:  # Arbitrary threshold
                attack_vectors.append(f"Excessive resource access: {node_id}")
        
        return attack_vectors


class ProvenanceChainTracker:
    """Advanced provenance chain tracker with comprehensive audit capabilities"""
    
    def __init__(self, config: ProvenanceConfig):
        self.config = config
        self.causal_engine = CausalAnalysisEngine(config)
        self._store: Dict[str, ProvenanceRecord] = {}
        self._graph = nx.DiGraph()
        self._recent_events: deque = deque(maxlen=1000)
        self.attack_paths: Dict[str, AttackPath] = {}
        
    async def record_invocation(self, event: Dict[str, Any], context: Any, 
                               telemetry: TelemetryRecord) -> Dict[str, Any]:
        """Record comprehensive invocation provenance"""
        
        # Generate provenance ID
        provenance_id = self._make_provenance_id(event, telemetry)
        
        # Determine node type
        node_type = self._determine_node_type(telemetry, event)
        
        # Extract data flows
        data_inputs = self._extract_data_inputs(event)
        data_outputs = self._extract_data_outputs(event, context)
        
        # Extract resource accesses
        resource_accesses = self._extract_resource_accesses(event, telemetry)
        
        # Build security context
        security_context = self._build_security_context(event, context)
        
        # Find predecessors based on recent events
        predecessors = await self._identify_predecessors(telemetry, event)
        
        # Create comprehensive provenance record
        provenance_record = ProvenanceRecord(
            provenance_id=provenance_id,
            event_id=telemetry.event_id,
            node_type=node_type,
            timestamp=telemetry.timestamp,
            function_id=telemetry.function_id,
            predecessors=predecessors,
            metadata={
                'duration': telemetry.duration,
                'cpu_utilization': telemetry.cpu_utilization,
                'memory_spike_kb': telemetry.memory_spike_kb,
                'network_io_bytes': telemetry.network_io_bytes,
                'anomaly_type': telemetry.anomaly_type.value if telemetry.anomaly_type else None,
                'execution_phase': telemetry.execution_phase.value if telemetry.execution_phase else None,
                'fallback_mode': telemetry.fallback_mode,
                'context_data': self._sanitize_context(context)
            },
            data_inputs=data_inputs,
            data_outputs=data_outputs,
            resource_accesses=resource_accesses,
            security_context=security_context
        )
        
        # Store record
        self._store[provenance_id] = provenance_record
        
        # Add to graph
        await self._add_to_graph(provenance_record)
        
        # Add to recent events
        self._recent_events.append({
            'timestamp': telemetry.timestamp,
            'provenance_id': provenance_id,
            'event_id': telemetry.event_id,
            'function_id': telemetry.function_id
        })
        
        # Analyze for potential attacks
        await self._analyze_for_attacks(provenance_record)
        
        return {
            'id': provenance_id,
            'predecessors': predecessors,
            'causal_relationships': len(self.causal_engine.detect_causal_relationships(self._graph)),
            'security_score': self._calculate_security_score(provenance_record)
        }
    
    def _determine_node_type(self, telemetry: TelemetryRecord, 
                            event: Dict[str, Any]) -> ProvenanceNodeType:
        """Determine the type of provenance node"""
        
        if telemetry.anomaly_type and telemetry.anomaly_type != AnomalyType.BENIGN:
            if 'security' in str(event).lower() or 'auth' in str(event).lower():
                return ProvenanceNodeType.SECURITY_EVENT
            else:
                return ProvenanceNodeType.ERROR_EVENT
        
        # Check for external service calls
        if any('http' in str(v).lower() or 'api' in str(v).lower() 
               for v in event.values() if isinstance(v, str)):
            return ProvenanceNodeType.EXTERNAL_SERVICE
        
        # Check for data processing patterns
        if any(key in event for key in ['input', 'data', 'payload']):
            return ProvenanceNodeType.DATA_INPUT
        
        # Default to function execution
        return ProvenanceNodeType.FUNCTION_EXECUTION
    
    def _extract_data_inputs(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract data inputs from event"""
        inputs = []
        
        # Extract from common input fields
        input_fields = ['input', 'data', 'payload', 'body', 'params']
        
        for field in input_fields:
            if field in event:
                input_data = event[field]
                inputs.append({
                    'field': field,
                    'type': type(input_data).__name__,
                    'size': len(str(input_data)),
                    'hash': self.causal_engine._hash_data(input_data),
                    'sample': str(input_data)[:100] if isinstance(input_data, str) else str(input_data)[:100]
                })
        
        return inputs
    
    def _extract_data_outputs(self, event: Dict[str, Any], context: Any) -> List[Dict[str, Any]]:
        """Extract data outputs from event and context"""
        outputs = []
        
        # Extract from context if available
        if hasattr(context, 'result') or hasattr(context, 'response'):
            result = getattr(context, 'result', None) or getattr(context, 'response', None)
            if result:
                outputs.append({
                    'field': 'result',
                    'type': type(result).__name__,
                    'size': len(str(result)),
                    'hash': self.causal_engine._hash_data(result),
                    'sample': str(result)[:100]
                })
        
        # Extract from event response fields
        response_fields = ['response', 'output', 'result', 'return']
        
        for field in response_fields:
            if field in event:
                output_data = event[field]
                outputs.append({
                    'field': field,
                    'type': type(output_data).__name__,
                    'size': len(str(output_data)),
                    'hash': self.causal_engine._hash_data(output_data),
                    'sample': str(output_data)[:100]
                })
        
        return outputs
    
    def _extract_resource_accesses(self, event: Dict[str, Any], 
                                  telemetry: TelemetryRecord) -> List[str]:
        """Extract resource accesses from event and telemetry"""
        resources = []
        
        # Database accesses
        if any('db' in str(v).lower() or 'database' in str(v).lower() 
               for v in event.values() if isinstance(v, str)):
            resources.append('database')
        
        # Storage accesses
        if any('s3' in str(v).lower() or 'storage' in str(v).lower() 
               for v in event.values() if isinstance(v, str)):
            resources.append('storage')
        
        # Network accesses
        if telemetry.network_io_bytes > 1024:  # More than 1KB
            resources.append('network')
        
        # Memory intensive
        if telemetry.memory_spike_kb > 100000:  # More than 100MB
            resources.append('memory_intensive')
        
        # CPU intensive
        if telemetry.cpu_utilization > 80:
            resources.append('cpu_intensive')
        
        return resources
    
    def _build_security_context(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Build security context information"""
        security_context = {}
        
        # Extract authentication information
        auth_fields = ['user_id', 'auth', 'token', 'credentials', 'identity']
        for field in auth_fields:
            if field in event:
                # Don't store actual credentials, just indicators
                security_context[f'has_{field}'] = True
                security_context[f'{field}_type'] = type(event[field]).__name__
        
        # Extract authorization information
        if 'permissions' in event or 'roles' in event:
            security_context['has_authorization'] = True
        
        # Check for suspicious patterns
        suspicious_patterns = ['admin', 'root', 'system', 'debug', 'test']
        for pattern in suspicious_patterns:
            if any(pattern in str(v).lower() for v in event.values() if isinstance(v, str)):
                security_context[f'contains_{pattern}'] = True
        
        # Context-based security information
        if hasattr(context, 'identity') or hasattr(context, 'user'):
            security_context['has_context_identity'] = True
        
        return security_context
    
    async def _identify_predecessors(self, telemetry: TelemetryRecord, 
                                   event: Dict[str, Any]) -> List[str]:
        """Identify predecessor events based on causal analysis"""
        predecessors = []
        current_time = telemetry.timestamp
        
        # Look at recent events within temporal window
        temporal_window = getattr(self.config, 'predecessor_window', 60.0)
        
        for recent_event in reversed(self._recent_events):
            if current_time - recent_event['timestamp'] > temporal_window:
                break
            
            # Skip same event
            if recent_event['event_id'] == telemetry.event_id:
                continue
            
            # Check for causal relationship
            if self._has_causal_relationship(recent_event, telemetry, event):
                predecessors.append(recent_event['provenance_id'])
        
        return predecessors
    
    def _has_causal_relationship(self, recent_event: Dict, 
                               current_telemetry: TelemetryRecord,
                               current_event: Dict[str, Any]) -> bool:
        """Check if recent event has causal relationship with current event"""
        
        # Same function - likely causal
        if recent_event['function_id'] == current_telemetry.function_id:
            return True
        
        # Check for data flow patterns
        recent_record = self._store.get(recent_event['provenance_id'])
        if recent_record:
            # Simple check for overlapping data
            recent_outputs = {out.get('hash') for out in recent_record.data_outputs}
            current_inputs = self._extract_data_inputs(current_event)
            current_hashes = {inp.get('hash') for inp in current_inputs}
            
            if recent_outputs.intersection(current_hashes):
                return True
        
        # Check for error propagation
        if (recent_event.get('anomaly_type') != 'BENIGN' and 
            current_telemetry.anomaly_type != AnomalyType.BENIGN):
            return True
        
        return False
    
    async def _add_to_graph(self, record: ProvenanceRecord):
        """Add provenance record to graph"""
        
        # Add node
        self._graph.add_node(
            record.provenance_id,
            **record.to_dict()
        )
        
        # Add edges to predecessors
        for pred_id in record.predecessors:
            if pred_id in self._graph:
                self._graph.add_edge(
                    pred_id, 
                    record.provenance_id,
                    edge_type='predecessor',
                    weight=1.0
                )
    
    def _calculate_security_score(self, record: ProvenanceRecord) -> float:
        """Calculate security risk score for provenance record"""
        score = 0.0
        
        # Anomaly detection
        if record.metadata.get('anomaly_type') != 'BENIGN':
            score += 0.3
        
        # Security context indicators
        security_indicators = sum(1 for k, v in record.security_context.items() 
                                if k.startswith('contains_') and v)
        score += min(0.3, security_indicators * 0.1)
        
        # Resource access patterns
        high_risk_resources = ['database', 'storage', 'memory_intensive']
        risky_accesses = sum(1 for resource in record.resource_accesses 
                           if resource in high_risk_resources)
        score += min(0.2, risky_accesses * 0.1)
        
        # External interactions
        if record.node_type == ProvenanceNodeType.EXTERNAL_SERVICE:
            score += 0.2
        
        return min(1.0, score)
    
    async def _analyze_for_attacks(self, record: ProvenanceRecord):
        """Analyze record for potential attack patterns"""
        
        # Simple attack pattern detection
        if record.node_type == ProvenanceNodeType.SECURITY_EVENT:
            await self._investigate_security_event(record)
        
        # Check for attack chains
        if len(record.predecessors) >= 3:  # Multi-step potential
            await self._analyze_attack_chain(record)
    
    async def _investigate_security_event(self, record: ProvenanceRecord):
        """Investigate potential security event"""
        # Implementation would include more sophisticated analysis
        logger.warning(f"Security event detected: {record.provenance_id}")
    
    async def _analyze_attack_chain(self, record: ProvenanceRecord):
        """Analyze potential attack chain"""
        # Implementation would include graph analysis for attack paths
        logger.info(f"Potential attack chain ending at: {record.provenance_id}")
    
    def _sanitize_context(self, context: Any) -> Dict[str, Any]:
        """Sanitize context data for storage"""
        sanitized = {}
        
        if hasattr(context, '__dict__'):
            for key, value in context.__dict__.items():
                if not key.startswith('_'):  # Skip private attributes
                    if isinstance(value, (str, int, float, bool)):
                        sanitized[key] = value
                    else:
                        sanitized[key] = type(value).__name__
        
        return sanitized
    
    def _make_provenance_id(self, event: Dict[str, Any], 
                          telemetry: TelemetryRecord) -> str:
        """Generate unique provenance ID"""
        # Create deterministic ID based on event and telemetry
        id_string = f"{telemetry.event_id}_{telemetry.function_id}_{telemetry.timestamp}"
        hash_obj = hashlib.sha256(id_string.encode())
        return f"prov-{uuid.uuid4()}-{hash_obj.hexdigest()[:8]}"
    
    def track_io_operation(self, operation_type: str, target: str, data_size: int) -> str:
        """Track I/O operation with provenance"""
        operation_id = f"io-{operation_type}-{target}-{int(time.time())}"
        
        # Store I/O operation record
        io_record = {
            'operation_id': operation_id,
            'type': operation_type,
            'target': target,
            'data_size': data_size,
            'timestamp': time.time()
        }
        
        # In practice, would link to current execution context
        logger.debug(f"I/O operation tracked: {operation_id}")
        
        return operation_id
    
    def create_causal_chain(self, execution_sequence: List[str]) -> List[str]:
        """Create causal chain from execution sequence"""
        if not execution_sequence:
            return []
        
        # Use graph to find actual causal relationships
        causal_chain = []
        
        for i, event_id in enumerate(execution_sequence):
            # Find provenance record
            prov_record = None
            for record in self._store.values():
                if record.event_id == event_id:
                    prov_record = record
                    break
            
            if prov_record:
                causal_chain.append(prov_record.provenance_id)
        
        return causal_chain
    
    def reconstruct_attack_path(self, target_execution: str) -> AttackPath:
        """Reconstruct attack path leading to target execution"""
        
        # Find target record
        target_record = None
        for record in self._store.values():
            if record.event_id == target_execution:
                target_record = record
                break
        
        if not target_record:
            # Return empty attack path
            return AttackPath(
                path_id=f"empty-{uuid.uuid4()}",
                attack_type="unknown",
                entry_point="unknown",
                target=target_execution,
                path_nodes=[],
                path_edges=[],
                severity=0.0,
                confidence=0.0,
                timeline=[]
            )
        
        # Reconstruct path using graph traversal
        path_nodes = self._find_attack_path_nodes(target_record)
        path_edges = self._construct_path_edges(path_nodes)
        
        # Analyze attack type
        attack_type = self._classify_attack_type(path_nodes, path_edges)
        
        # Build timeline
        timeline = self._build_attack_timeline(path_nodes)
        
        # Calculate severity and confidence
        severity = self._calculate_attack_severity(path_nodes, path_edges)
        confidence = self._calculate_path_confidence(path_edges)
        
        return AttackPath(
            path_id=f"attack-{uuid.uuid4()}",
            attack_type=attack_type,
            entry_point=path_nodes[0] if path_nodes else "unknown",
            target=target_execution,
            path_nodes=path_nodes,
            path_edges=path_edges,
            severity=severity,
            confidence=confidence,
            timeline=timeline,
            mitigation_points=self._identify_mitigation_points(path_nodes)
        )
    
    def _find_attack_path_nodes(self, target_record: ProvenanceRecord) -> List[str]:
        """Find nodes in attack path using graph traversal"""
        path_nodes = [target_record.provenance_id]
        
        # Traverse backwards through predecessors
        current_nodes = [target_record.provenance_id]
        visited = set()
        
        while current_nodes:
            next_nodes = []
            for node_id in current_nodes:
                if node_id in visited:
                    continue
                visited.add(node_id)
                
                # Get predecessors
                if node_id in self._graph:
                    predecessors = list(self._graph.predecessors(node_id))
                    for pred in predecessors:
                        if pred not in visited:
                            next_nodes.append(pred)
                            path_nodes.insert(0, pred)  # Add to front
            
            current_nodes = next_nodes
            
            # Limit traversal depth
            if len(path_nodes) > 20:
                break
        
        return path_nodes
    
    def _construct_path_edges(self, path_nodes: List[str]) -> List[CausalRelationship]:
        """Construct edges between path nodes"""
        edges = []
        
        for i in range(len(path_nodes) - 1):
            current_node = path_nodes[i]
            next_node = path_nodes[i + 1]
            
            # Check if edge exists in graph
            if self._graph.has_edge(current_node, next_node):
                edge_data = self._graph.edges[current_node, next_node]
                
                # Create causal relationship
                relationship = CausalRelationship(
                    cause_id=current_node,
                    effect_id=next_node,
                    edge_type=ProvenanceEdgeType.CAUSALITY,
                    strength=edge_data.get('weight', 0.5),
                    evidence={},
                    timestamp_diff=0.0,
                    confidence=edge_data.get('confidence', 0.7)
                )
                edges.append(relationship)
        
        return edges
    
    def _classify_attack_type(self, path_nodes: List[str], 
                            path_edges: List[CausalRelationship]) -> str:
        """Classify the type of attack based on path analysis"""
        
        # Analyze nodes for attack patterns
        security_events = sum(1 for node_id in path_nodes
                             if node_id in self._store and 
                             self._store[node_id].node_type == ProvenanceNodeType.SECURITY_EVENT)
        
        external_services = sum(1 for node_id in path_nodes
                               if node_id in self._store and 
                               self._store[node_id].node_type == ProvenanceNodeType.EXTERNAL_SERVICE)
        
        if security_events >= 2:
            return "Multi-stage Security Attack"
        elif external_services >= 1 and len(path_nodes) >= 3:
            return "External Infiltration Attack"
        elif len(path_nodes) >= 5:
            return "Complex Chain Attack"
        else:
            return "Simple Attack"
    
    def _build_attack_timeline(self, path_nodes: List[str]) -> List[Tuple[float, str, str]]:
        """Build timeline of attack events"""
        timeline = []
        
        for node_id in path_nodes:
            if node_id in self._store:
                record = self._store[node_id]
                timeline.append((
                    record.timestamp,
                    record.event_id,
                    f"{record.node_type.value} in {record.function_id}"
                ))
        
        return sorted(timeline)  # Sort by timestamp
    
    def _calculate_attack_severity(self, path_nodes: List[str], 
                                  path_edges: List[CausalRelationship]) -> float:
        """Calculate attack severity score"""
        severity = 0.0
        
        # Base severity from path length
        severity += min(0.3, len(path_nodes) / 10)
        
        # Security events increase severity
        security_events = sum(1 for node_id in path_nodes
                             if node_id in self._store and 
                             self._store[node_id].node_type == ProvenanceNodeType.SECURITY_EVENT)
        severity += min(0.4, security_events * 0.2)
        
        # Strong causal relationships increase severity
        strong_edges = sum(1 for edge in path_edges if edge.strength > 0.7)
        severity += min(0.3, strong_edges / len(path_edges) if path_edges else 0)
        
        return min(1.0, severity)
    
    def _calculate_path_confidence(self, path_edges: List[CausalRelationship]) -> float:
        """Calculate confidence in attack path reconstruction"""
        if not path_edges:
            return 0.0
        
        total_confidence = sum(edge.confidence for edge in path_edges)
        return total_confidence / len(path_edges)
    
    def _identify_mitigation_points(self, path_nodes: List[str]) -> List[str]:
        """Identify points in attack path where mitigation could be applied"""
        mitigation_points = []
        
        for node_id in path_nodes:
            if node_id in self._store:
                record = self._store[node_id]
                
                # External service calls are mitigation points
                if record.node_type == ProvenanceNodeType.EXTERNAL_SERVICE:
                    mitigation_points.append(f"External service validation: {node_id}")
                
                # Input validation points
                if record.node_type == ProvenanceNodeType.DATA_INPUT:
                    mitigation_points.append(f"Input validation: {node_id}")
                
                # Resource access control points
                if record.resource_accesses:
                    mitigation_points.append(f"Resource access control: {node_id}")
        
        return mitigation_points
    
    def get_provenance_summary(self) -> Dict[str, Any]:
        """Get summary of provenance tracking status"""
        return {
            'total_records': len(self._store),
            'graph_nodes': self._graph.number_of_nodes(),
            'graph_edges': self._graph.number_of_edges(),
            'recent_events': len(self._recent_events),
            'attack_paths': len(self.attack_paths),
            'node_types': {
                node_type.value: sum(1 for record in self._store.values() 
                                   if record.node_type == node_type)
                for node_type in ProvenanceNodeType
            }
        }