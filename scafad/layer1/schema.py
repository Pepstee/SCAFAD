#!/usr/bin/env python3
"""
SCAFAD Layer 1: Schema Evolution Engine
========================================

The Schema Evolution Engine manages schema versioning, migration, and backward compatibility
for telemetry records flowing through Layer 1. It ensures seamless evolution of data structures
while maintaining compatibility with existing detection models and preserving anomaly semantics.

Key Responsibilities:
- Schema version management and registry
- Automatic schema migration between versions
- Backward and forward compatibility handling
- Field mapping and transformation
- Schema inference and validation
- Migration path optimization
- Compatibility testing and verification
- Schema drift detection and alerting

Performance Targets:
- Migration latency: <0.2ms per record
- Compatibility rate: 99.9%+
- Schema detection accuracy: 100%
- Migration success rate: 99.95%+
- Zero data loss during migrations

Author: SCAFAD Research Team
Institution: Birmingham Newman University
License: MIT
Version: 1.0.0
"""

import json
import hashlib
import logging
import asyncio
import copy
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union, Tuple, Callable, Set
from enum import Enum, auto
from datetime import datetime, timezone
from collections import defaultdict, OrderedDict
import pickle
import re
from functools import lru_cache
import traceback

# Version management and semantic versioning
from packaging import version
try:
    import semver
except ImportError:
    semver = None

# Schema validation and JSON operations
from jsonschema import validate, Draft7Validator, ValidationError as JsonSchemaValidationError
try:
    import jsonpatch
except ImportError:
    jsonpatch = None
try:
    import jsonpointer
except ImportError:
    jsonpointer = None

# Performance monitoring
import time
try:
    import numpy as np
except ImportError:
    np = None


# =============================================================================
# Schema Data Models and Enums
# =============================================================================

class SchemaCompatibilityLevel(Enum):
    """Schema compatibility levels"""
    NONE = "none"                      # No compatibility required
    BACKWARD = "backward"              # New schema can read old data
    FORWARD = "forward"                # Old schema can read new data  
    FULL = "full"                      # Both backward and forward compatible
    BACKWARD_TRANSITIVE = "backward_transitive"  # Compatible with all previous versions
    FORWARD_TRANSITIVE = "forward_transitive"    # Compatible with all future versions
    FULL_TRANSITIVE = "full_transitive"          # Fully transitive compatibility

class MigrationStrategy(Enum):
    """Migration strategies for schema evolution"""
    DIRECT = "direct"                  # Direct field mapping
    TRANSFORM = "transform"            # Field transformation required
    SYNTHETIC = "synthetic"            # Synthetic field generation
    DEFAULT = "default"                # Use default values
    COMPUTE = "compute"                # Compute from other fields
    PRESERVE = "preserve"              # Preserve without modification
    DROP = "drop"                      # Drop field (forward compatibility)

class SchemaChangeType(Enum):
    """Types of schema changes"""
    ADD_FIELD = "add_field"
    REMOVE_FIELD = "remove_field"
    RENAME_FIELD = "rename_field"
    CHANGE_TYPE = "change_type"
    CHANGE_CONSTRAINT = "change_constraint"
    ADD_CONSTRAINT = "add_constraint"
    REMOVE_CONSTRAINT = "remove_constraint"
    RESTRUCTURE = "restructure"

class MigrationStatus(Enum):
    """Migration operation status"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_REQUIRED = "not_required"


@dataclass
class SchemaMetadata:
    """
    Metadata for schema versions
    """
    version: str = ""
    created_at: str = ""
    updated_at: str = ""
    compatibility_level: str = "none"
    migration_applied: bool = False
    schema_hash: str = ""
    field_count: int = 0
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    deprecated_fields: List[str] = field(default_factory=list)
    added_fields: List[str] = field(default_factory=list)
    removed_fields: List[str] = field(default_factory=list)
    parent_version: Optional[str] = None
    migration_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return asdict(self)


@dataclass
class MigrationResult:
    """
    Result of a schema migration operation
    """
    success: bool
    status: MigrationStatus
    migrated_record: Optional[Any] = None
    original_version: Optional[str] = None
    target_version: Optional[str] = None
    fields_migrated: List[str] = field(default_factory=list)
    fields_added: List[str] = field(default_factory=list)
    fields_removed: List[str] = field(default_factory=list)
    fields_transformed: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    migration_time_ms: float = 0.0
    compatibility_warnings: List[str] = field(default_factory=list)


@dataclass
class SchemaVersion:
    """
    Complete schema version definition
    """
    version: str
    schema_definition: Dict[str, Any]
    field_mappings: Dict[str, str]
    type_definitions: Dict[str, str]
    constraints: Dict[str, Any]
    transformations: Dict[str, Callable]
    metadata: SchemaMetadata
    json_schema: Optional[Dict[str, Any]] = None
    migration_paths: Dict[str, List[str]] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.json_schema:
            self.json_schema = self._generate_json_schema()
    
    def _generate_json_schema(self) -> Dict[str, Any]:
        """Generate JSON Schema from schema definition"""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": self.schema_definition,
            "required": self.metadata.required_fields,
            "additionalProperties": False
        }


@dataclass 
class MigrationPath:
    """
    Migration path between schema versions
    """
    source_version: str
    target_version: str
    intermediate_versions: List[str]
    total_steps: int
    migration_functions: List[Callable]
    estimated_time_ms: float
    compatibility_level: SchemaCompatibilityLevel
    risk_level: str  # low, medium, high
    
    def is_direct(self) -> bool:
        """Check if migration is direct (no intermediate steps)"""
        return self.total_steps == 1


@dataclass
class FieldMapping:
    """
    Field mapping definition for migrations
    """
    source_field: str
    target_field: str
    mapping_type: MigrationStrategy
    transformation: Optional[Callable] = None
    default_value: Any = None
    is_required: bool = False
    preserve_on_error: bool = True
    validation_rule: Optional[Callable] = None


# =============================================================================
# Schema Registry
# =============================================================================

class SchemaRegistry:
    """
    Central registry for schema versions and migration paths
    """
    
    def __init__(self):
        """Initialize schema registry"""
        self.logger = logging.getLogger("SCAFAD.Layer1.SchemaRegistry")
        
        # Schema storage
        self.schemas: Dict[str, SchemaVersion] = {}
        self.migration_paths: Dict[Tuple[str, str], MigrationPath] = {}
        self.field_mappings: Dict[Tuple[str, str], List[FieldMapping]] = {}
        
        # Version ordering
        self.version_chain: List[str] = []
        self.latest_version: Optional[str] = None
        
        # Performance metrics
        self.migration_stats = {
            'total_migrations': 0,
            'successful_migrations': 0,
            'failed_migrations': 0,
            'average_migration_time_ms': 0.0
        }
        
        # Initialize default schemas
        self._initialize_default_schemas()
    
    def _initialize_default_schemas(self):
        """Initialize default schema versions"""
        
        # Schema v1.0 (Legacy)
        self.register_schema(self._create_schema_v1_0())
        
        # Schema v2.0 (Intermediate)
        self.register_schema(self._create_schema_v2_0())
        
        # Schema v2.1 (Current)
        self.register_schema(self._create_schema_v2_1())
        
        # Schema v2.2 (Future/Experimental)
        self.register_schema(self._create_schema_v2_2())
        
        # Define migration paths
        self._define_migration_paths()
    
    def _create_schema_v1_0(self) -> SchemaVersion:
        """Create schema version 1.0 definition"""
        
        schema_def = {
            "id": {"type": "string"},
            "timestamp": {"type": "integer"},
            "function": {"type": "string"},
            "phase": {"type": "string"},
            "data": {"type": "object"},
            "version": {"type": "string"}
        }
        
        metadata = SchemaMetadata(
            version="v1.0",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            compatibility_level=SchemaCompatibilityLevel.BACKWARD.value,
            migration_applied=False,
            schema_hash=self._calculate_schema_hash(schema_def),
            field_count=6,
            required_fields=["id", "timestamp", "function", "phase", "data"],
            optional_fields=["version"]
        )
        
        return SchemaVersion(
            version="v1.0",
            schema_definition=schema_def,
            field_mappings={
                "id": "id",
                "timestamp": "timestamp",
                "function": "function",
                "phase": "phase",
                "data": "data",
                "version": "version"
            },
            type_definitions={
                "id": "string",
                "timestamp": "integer",
                "function": "string",
                "phase": "string",
                "data": "object",
                "version": "string"
            },
            constraints={
                "timestamp": {"minimum": 0},
                "function": {"minLength": 1, "maxLength": 256},
                "phase": {"enum": ["init", "exec", "complete", "error"]}
            },
            transformations={},
            metadata=metadata
        )
    
    def _create_schema_v2_0(self) -> SchemaVersion:
        """Create schema version 2.0 definition"""
        
        schema_def = {
            "record_id": {"type": "string"},
            "timestamp": {"type": "number"},
            "function_name": {"type": "string"},
            "execution_phase": {"type": "string"},
            "anomaly_type": {"type": "string"},
            "telemetry_data": {"type": "object"},
            "schema_version": {"type": "string"}
        }
        
        metadata = SchemaMetadata(
            version="v2.0",
            created_at="2024-06-01T00:00:00Z",
            updated_at="2024-06-01T00:00:00Z",
            compatibility_level=SchemaCompatibilityLevel.BACKWARD.value,
            migration_applied=False,
            schema_hash=self._calculate_schema_hash(schema_def),
            field_count=7,
            required_fields=["record_id", "timestamp", "function_name", "execution_phase", "anomaly_type", "telemetry_data"],
            optional_fields=["schema_version"],
            parent_version="v1.0",
            added_fields=["anomaly_type"],
            removed_fields=[]
        )
        
        return SchemaVersion(
            version="v2.0",
            schema_definition=schema_def,
            field_mappings={
                "record_id": "record_id",
                "timestamp": "timestamp",
                "function_name": "function_name",
                "execution_phase": "execution_phase",
                "anomaly_type": "anomaly_type",
                "telemetry_data": "telemetry_data",
                "schema_version": "schema_version"
            },
            type_definitions={
                "record_id": "string",
                "timestamp": "number",
                "function_name": "string",
                "execution_phase": "string",
                "anomaly_type": "string",
                "telemetry_data": "object",
                "schema_version": "string"
            },
            constraints={
                "timestamp": {"minimum": 0},
                "function_name": {"minLength": 1, "maxLength": 256},
                "execution_phase": {"enum": ["initialization", "execution", "completion", "error", "timeout"]},
                "anomaly_type": {"enum": ["benign", "suspicious", "malicious", "unknown"]}
            },
            transformations={},
            metadata=metadata
        )
    
    def _create_schema_v2_1(self) -> SchemaVersion:
        """Create schema version 2.1 definition (current)"""
        
        schema_def = {
            "record_id": {"type": "string", "format": "uuid"},
            "timestamp": {"type": "number"},
            "function_name": {"type": "string"},
            "execution_phase": {"type": "string"},
            "anomaly_type": {"type": "string"},
            "telemetry_data": {"type": "object"},
            "provenance_chain": {"type": ["object", "null"]},
            "context_metadata": {"type": ["object", "null"]},
            "schema_version": {"type": "string"}
        }
        
        metadata = SchemaMetadata(
            version="v2.1",
            created_at="2024-10-01T00:00:00Z",
            updated_at="2024-10-01T00:00:00Z",
            compatibility_level=SchemaCompatibilityLevel.FULL.value,
            migration_applied=False,
            schema_hash=self._calculate_schema_hash(schema_def),
            field_count=9,
            required_fields=["record_id", "timestamp", "function_name", "execution_phase", "anomaly_type", "telemetry_data", "schema_version"],
            optional_fields=["provenance_chain", "context_metadata"],
            parent_version="v2.0",
            added_fields=["provenance_chain", "context_metadata"],
            removed_fields=[]
        )
        
        return SchemaVersion(
            version="v2.1",
            schema_definition=schema_def,
            field_mappings={
                "record_id": "record_id",
                "timestamp": "timestamp",
                "function_name": "function_name",
                "execution_phase": "execution_phase",
                "anomaly_type": "anomaly_type",
                "telemetry_data": "telemetry_data",
                "provenance_chain": "provenance_chain",
                "context_metadata": "context_metadata",
                "schema_version": "schema_version"
            },
            type_definitions={
                "record_id": "string:uuid",
                "timestamp": "number",
                "function_name": "string",
                "execution_phase": "string",
                "anomaly_type": "string",
                "telemetry_data": "object",
                "provenance_chain": "object:optional",
                "context_metadata": "object:optional",
                "schema_version": "string"
            },
            constraints={
                "record_id": {"pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
                "timestamp": {"minimum": 0},
                "function_name": {"minLength": 1, "maxLength": 256, "pattern": "^[a-zA-Z0-9_\\-\\.]+$"},
                "execution_phase": {"enum": ["initialization", "execution", "completion", "error", "timeout"]},
                "anomaly_type": {"enum": ["benign", "suspicious", "malicious", "unknown"]},
                "schema_version": {"pattern": "^v\\d+\\.\\d+$"}
            },
            transformations={},
            metadata=metadata
        )
    
    def _create_schema_v2_2(self) -> SchemaVersion:
        """Create schema version 2.2 definition (future/experimental)"""
        
        schema_def = {
            "record_id": {"type": "string", "format": "uuid"},
            "timestamp": {"type": "number"},
            "function_name": {"type": "string"},
            "execution_phase": {"type": "string"},
            "anomaly_type": {"type": "string"},
            "anomaly_confidence": {"type": "number"},  # New field
            "telemetry_data": {"type": "object"},
            "provenance_chain": {"type": ["object", "null"]},
            "context_metadata": {"type": ["object", "null"]},
            "behavioral_signature": {"type": ["string", "null"]},  # New field
            "risk_score": {"type": ["number", "null"]},  # New field
            "schema_version": {"type": "string"}
        }
        
        metadata = SchemaMetadata(
            version="v2.2",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            compatibility_level=SchemaCompatibilityLevel.BACKWARD.value,
            migration_applied=False,
            schema_hash=self._calculate_schema_hash(schema_def),
            field_count=12,
            required_fields=["record_id", "timestamp", "function_name", "execution_phase", "anomaly_type", "telemetry_data", "schema_version"],
            optional_fields=["anomaly_confidence", "provenance_chain", "context_metadata", "behavioral_signature", "risk_score"],
            parent_version="v2.1",
            added_fields=["anomaly_confidence", "behavioral_signature", "risk_score"],
            removed_fields=[]
        )
        
        return SchemaVersion(
            version="v2.2",
            schema_definition=schema_def,
            field_mappings={
                "record_id": "record_id",
                "timestamp": "timestamp",
                "function_name": "function_name",
                "execution_phase": "execution_phase",
                "anomaly_type": "anomaly_type",
                "anomaly_confidence": "anomaly_confidence",
                "telemetry_data": "telemetry_data",
                "provenance_chain": "provenance_chain",
                "context_metadata": "context_metadata",
                "behavioral_signature": "behavioral_signature",
                "risk_score": "risk_score",
                "schema_version": "schema_version"
            },
            type_definitions={
                "record_id": "string:uuid",
                "timestamp": "number",
                "function_name": "string",
                "execution_phase": "string",
                "anomaly_type": "string",
                "anomaly_confidence": "number",
                "telemetry_data": "object",
                "provenance_chain": "object:optional",
                "context_metadata": "object:optional",
                "behavioral_signature": "string:optional",
                "risk_score": "number:optional",
                "schema_version": "string"
            },
            constraints={
                "anomaly_confidence": {"minimum": 0.0, "maximum": 1.0},
                "risk_score": {"minimum": 0.0, "maximum": 100.0}
            },
            transformations={},
            metadata=metadata
        )
    
    def _define_migration_paths(self):
        """Define migration paths between schema versions"""
        
        # v1.0 -> v2.0
        self.add_migration_path(
            MigrationPath(
                source_version="v1.0",
                target_version="v2.0",
                intermediate_versions=[],
                total_steps=1,
                migration_functions=[self._migrate_v1_0_to_v2_0],
                estimated_time_ms=0.15,
                compatibility_level=SchemaCompatibilityLevel.BACKWARD,
                risk_level="low"
            )
        )
        
        # v2.0 -> v2.1
        self.add_migration_path(
            MigrationPath(
                source_version="v2.0",
                target_version="v2.1",
                intermediate_versions=[],
                total_steps=1,
                migration_functions=[self._migrate_v2_0_to_v2_1],
                estimated_time_ms=0.10,
                compatibility_level=SchemaCompatibilityLevel.FULL,
                risk_level="low"
            )
        )
        
        # v2.1 -> v2.2
        self.add_migration_path(
            MigrationPath(
                source_version="v2.1",
                target_version="v2.2",
                intermediate_versions=[],
                total_steps=1,
                migration_functions=[self._migrate_v2_1_to_v2_2],
                estimated_time_ms=0.12,
                compatibility_level=SchemaCompatibilityLevel.BACKWARD,
                risk_level="low"
            )
        )
        
        # v1.0 -> v2.1 (multi-step)
        self.add_migration_path(
            MigrationPath(
                source_version="v1.0",
                target_version="v2.1",
                intermediate_versions=["v2.0"],
                total_steps=2,
                migration_functions=[self._migrate_v1_0_to_v2_0, self._migrate_v2_0_to_v2_1],
                estimated_time_ms=0.25,
                compatibility_level=SchemaCompatibilityLevel.BACKWARD,
                risk_level="medium"
            )
        )
        
        # v1.0 -> v2.2 (multi-step)
        self.add_migration_path(
            MigrationPath(
                source_version="v1.0",
                target_version="v2.2",
                intermediate_versions=["v2.0", "v2.1"],
                total_steps=3,
                migration_functions=[self._migrate_v1_0_to_v2_0, self._migrate_v2_0_to_v2_1, self._migrate_v2_1_to_v2_2],
                estimated_time_ms=0.37,
                compatibility_level=SchemaCompatibilityLevel.BACKWARD,
                risk_level="medium"
            )
        )
        
        # Backward migrations (for forward compatibility)
        # v2.1 -> v2.0
        self.add_migration_path(
            MigrationPath(
                source_version="v2.1",
                target_version="v2.0",
                intermediate_versions=[],
                total_steps=1,
                migration_functions=[self._migrate_v2_1_to_v2_0],
                estimated_time_ms=0.10,
                compatibility_level=SchemaCompatibilityLevel.FORWARD,
                risk_level="medium"
            )
        )
    
    def _calculate_schema_hash(self, schema_def: Dict[str, Any]) -> str:
        """Calculate hash of schema definition"""
        schema_str = json.dumps(schema_def, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]
    
    def register_schema(self, schema_version: SchemaVersion):
        """Register a new schema version"""
        version = schema_version.version
        self.schemas[version] = schema_version
        
        # Update version chain
        if version not in self.version_chain:
            self.version_chain.append(version)
            self.version_chain.sort(key=lambda v: semver.VersionInfo.parse(
                '.'.join((v.lstrip('v').split('.') + ['0', '0'])[:3])))
        
        # Update latest version
        if not self.latest_version or self._compare_versions(version, self.latest_version) > 0:
            self.latest_version = version
        
        self.logger.info(f"Registered schema version {version}")
    
    def add_migration_path(self, migration_path: MigrationPath):
        """Add a migration path between versions"""
        key = (migration_path.source_version, migration_path.target_version)
        self.migration_paths[key] = migration_path
        self.logger.debug(f"Added migration path: {migration_path.source_version} -> {migration_path.target_version}")
    
    def get_schema(self, version: str) -> Optional[SchemaVersion]:
        """Get schema by version"""
        return self.schemas.get(version)
    
    def get_migration_path(self, source_version: str, target_version: str) -> Optional[MigrationPath]:
        """Get migration path between versions"""
        return self.migration_paths.get((source_version, target_version))
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings"""
        v1_parsed = semver.VersionInfo.parse('.'.join((v1.lstrip('v').split('.') + ['0', '0'])[:3]))
        v2_parsed = semver.VersionInfo.parse('.'.join((v2.lstrip('v').split('.') + ['0', '0'])[:3]))
        return v1_parsed.compare(v2_parsed)
    
    # =========================================================================
    # Migration Functions
    # =========================================================================
    
    def _migrate_v1_0_to_v2_0(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate record from v1.0 to v2.0"""
        migrated = {}
        
        # Field mappings
        migrated['record_id'] = record.get('id', '')
        migrated['timestamp'] = float(record.get('timestamp', 0))
        migrated['function_name'] = record.get('function', '')
        
        # Map phase values
        phase_mapping = {
            'init': 'initialization',
            'exec': 'execution',
            'complete': 'completion',
            'error': 'error'
        }
        migrated['execution_phase'] = phase_mapping.get(record.get('phase', ''), 'execution')
        
        # Add new field with default
        migrated['anomaly_type'] = 'unknown'  # Default for v1.0 records
        
        # Rename data to telemetry_data
        migrated['telemetry_data'] = record.get('data', {})
        
        # Update schema version
        migrated['schema_version'] = 'v2.0'
        
        return migrated
    
    def _migrate_v2_0_to_v2_1(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate record from v2.0 to v2.1"""
        migrated = record.copy()
        
        # Ensure record_id is UUID format
        if 'record_id' in migrated and not self._is_valid_uuid(migrated['record_id']):
            # Convert to UUID format if needed
            import uuid
            migrated['record_id'] = str(uuid.uuid5(uuid.NAMESPACE_DNS, migrated['record_id']))
        
        # Add new optional fields with null defaults
        if 'provenance_chain' not in migrated:
            migrated['provenance_chain'] = None
        
        if 'context_metadata' not in migrated:
            migrated['context_metadata'] = None
        
        # Update schema version
        migrated['schema_version'] = 'v2.1'
        
        return migrated
    
    def _migrate_v2_1_to_v2_2(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate record from v2.1 to v2.2"""
        migrated = record.copy()
        
        # Add anomaly_confidence based on anomaly_type
        if 'anomaly_confidence' not in migrated:
            confidence_mapping = {
                'benign': 0.9,
                'suspicious': 0.6,
                'malicious': 0.8,
                'unknown': 0.3
            }
            migrated['anomaly_confidence'] = confidence_mapping.get(migrated.get('anomaly_type', 'unknown'), 0.5)
        
        # Add behavioral_signature (can be computed from telemetry_data)
        if 'behavioral_signature' not in migrated:
            migrated['behavioral_signature'] = self._compute_behavioral_signature(migrated.get('telemetry_data', {}))
        
        # Add risk_score (computed from anomaly_type and confidence)
        if 'risk_score' not in migrated:
            risk_mapping = {
                'benign': 10.0,
                'suspicious': 50.0,
                'malicious': 90.0,
                'unknown': 30.0
            }
            base_risk = risk_mapping.get(migrated.get('anomaly_type', 'unknown'), 30.0)
            confidence = migrated.get('anomaly_confidence', 0.5)
            migrated['risk_score'] = base_risk * confidence
        
        # Update schema version
        migrated['schema_version'] = 'v2.2'
        
        return migrated
    
    def _migrate_v2_1_to_v2_0(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Backward migration from v2.1 to v2.0"""
        migrated = record.copy()
        
        # Remove fields not in v2.0
        migrated.pop('provenance_chain', None)
        migrated.pop('context_metadata', None)
        
        # Ensure record_id is string (v2.0 doesn't enforce UUID)
        if 'record_id' in migrated:
            migrated['record_id'] = str(migrated['record_id'])
        
        # Update schema version
        migrated['schema_version'] = 'v2.0'
        
        return migrated
    
    def _is_valid_uuid(self, value: str) -> bool:
        """Check if string is valid UUID"""
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(value))
    
    def _compute_behavioral_signature(self, telemetry_data: Dict[str, Any]) -> str:
        """Compute behavioral signature from telemetry data"""
        # Simple signature based on key patterns
        keys = sorted(telemetry_data.keys())
        signature_components = []
        
        for key in keys[:5]:  # Use top 5 keys
            value = telemetry_data[key]
            if isinstance(value, (int, float)):
                signature_components.append(f"{key}:{value:.2f}")
            else:
                signature_components.append(f"{key}:{type(value).__name__}")
        
        return hashlib.md5('|'.join(signature_components).encode()).hexdigest()[:16]


# =============================================================================
# Schema Evolution Engine
# =============================================================================

class SchemaEvolutionEngine:
    """
    Main Schema Evolution Engine for Layer 1
    
    This class orchestrates schema detection, validation, and migration
    for telemetry records flowing through the behavioral intake zone.
    """
    
    def __init__(self, config: Any):
        """
        Initialize Schema Evolution Engine
        
        Args:
            config: Layer 1 configuration object
        """
        self.config = config
        self.logger = logging.getLogger("SCAFAD.Layer1.SchemaEvolution")
        
        # Initialize schema registry
        self.registry = SchemaRegistry()
        
        # Current target schema version
        self.current_version = config.schema_version
        self.current_schema = self.registry.get_schema(self.current_version)
        
        # Migration settings
        self.enable_migration = config.enable_schema_migration
        self.backward_compatibility = config.backward_compatibility_mode
        self.migration_timeout_ms = 1.0  # Maximum time for single migration
        
        # Initialize caches
        self._initialize_caches()
        
        # Initialize migration statistics
        self._initialize_statistics()
        
        # Schema inference engine
        self.schema_inferencer = SchemaInferencer()
        
        # Compatibility validator
        self.compatibility_validator = CompatibilityValidator()
        
        self.logger.info(f"Schema Evolution Engine initialized with target version: {self.current_version}")
    
    def _initialize_caches(self):
        """Initialize performance caches"""
        self.migration_cache = {}  # Cache for migration paths
        self.validation_cache = {}  # Cache for validation results
        self.transformation_cache = {}  # Cache for transformations
        
        # LRU cache for frequent migrations
        self._get_optimal_migration_path = lru_cache(maxsize=128)(self._get_optimal_migration_path_impl)
    
    def _initialize_statistics(self):
        """Initialize migration statistics"""
        self.stats = {
            'total_migrations': 0,
            'successful_migrations': 0,
            'failed_migrations': 0,
            'skipped_migrations': 0,
            'migrations_by_version': defaultdict(int),
            'average_migration_time_ms': 0.0,
            'migration_times': []
        }
    
    # =========================================================================
    # Main Migration Methods
    # =========================================================================
    
    async def migrate_record_to_current_schema(self, record: Any) -> MigrationResult:
        """
        Migrate a record to the current schema version
        
        Args:
            record: Telemetry record to migrate
            
        Returns:
            MigrationResult with migration status and migrated record
        """
        migration_start = time.time()
        
        try:
            # Convert record to dictionary
            record_dict = self._to_dict(record)
            
            # Detect current schema version
            detected_version = await self.detect_schema_version(record_dict)
            
            if not detected_version:
                return MigrationResult(
                    success=False,
                    status=MigrationStatus.FAILED,
                    error_message="Unable to detect schema version"
                )
            
            # Check if migration is needed
            if detected_version == self.current_version:
                return MigrationResult(
                    success=True,
                    status=MigrationStatus.NOT_REQUIRED,
                    migrated_record=record,
                    original_version=detected_version,
                    target_version=self.current_version,
                    migration_time_ms=(time.time() - migration_start) * 1000
                )
            
            # Get migration path
            migration_path = self._get_optimal_migration_path(detected_version, self.current_version)
            
            if not migration_path:
                return MigrationResult(
                    success=False,
                    status=MigrationStatus.FAILED,
                    error_message=f"No migration path from {detected_version} to {self.current_version}"
                )
            
            # Perform migration
            migrated_record = await self._execute_migration(record_dict, migration_path)
            
            # Validate migrated record
            is_valid = await self._validate_migrated_record(migrated_record, self.current_version)
            
            if not is_valid:
                return MigrationResult(
                    success=False,
                    status=MigrationStatus.PARTIAL_SUCCESS,
                    migrated_record=migrated_record,
                    original_version=detected_version,
                    target_version=self.current_version,
                    error_message="Migrated record failed validation",
                    migration_time_ms=(time.time() - migration_start) * 1000
                )
            
            # Calculate migration details
            fields_added, fields_removed, fields_transformed = self._analyze_migration_changes(
                record_dict, migrated_record, detected_version, self.current_version
            )
            
            # Update statistics
            self._update_statistics(True, (time.time() - migration_start) * 1000, detected_version)
            
            # Convert back to original type if needed
            final_record = self._from_dict(record.__class__, migrated_record) if not isinstance(record, dict) else migrated_record
            
            return MigrationResult(
                success=True,
                status=MigrationStatus.SUCCESS,
                migrated_record=final_record,
                original_version=detected_version,
                target_version=self.current_version,
                fields_migrated=list(migrated_record.keys()),
                fields_added=fields_added,
                fields_removed=fields_removed,
                fields_transformed=fields_transformed,
                migration_time_ms=(time.time() - migration_start) * 1000
            )
            
        except Exception as e:
            self.logger.error(f"Migration failed: {str(e)}")
            self._update_statistics(False, (time.time() - migration_start) * 1000, None)
            
            return MigrationResult(
                success=False,
                status=MigrationStatus.FAILED,
                error_message=f"Migration error: {str(e)}",
                migration_time_ms=(time.time() - migration_start) * 1000
            )
    
    async def detect_schema_version(self, record: Dict[str, Any]) -> Optional[str]:
        """
        Detect the schema version of a record
        
        Args:
            record: Record to analyze
            
        Returns:
            Detected schema version or None
        """
        # Check for explicit schema version field
        if 'schema_version' in record:
            return record['schema_version']
        
        if 'version' in record:
            # v1.0 used 'version' field
            return record['version'] if record['version'].startswith('v') else f"v{record['version']}"
        
        # Infer schema version from structure
        return await self.schema_inferencer.infer_version(record, self.registry.schemas)
    
    async def _execute_migration(self, record: Dict[str, Any], migration_path: MigrationPath) -> Dict[str, Any]:
        """Execute migration along specified path"""
        migrated = record.copy()
        
        # Apply each migration function in sequence
        for migration_func in migration_path.migration_functions:
            try:
                migrated = migration_func(migrated)
            except Exception as e:
                self.logger.error(f"Migration step failed: {str(e)}")
                raise
        
        return migrated
    
    async def _validate_migrated_record(self, record: Dict[str, Any], target_version: str) -> bool:
        """Validate migrated record against target schema"""
        target_schema = self.registry.get_schema(target_version)
        
        if not target_schema:
            return False
        
        try:
            # Validate against JSON schema
            validate(instance=record, schema=target_schema.json_schema)
            
            # Additional semantic validation
            return self._validate_semantic_integrity(record, target_schema)
            
        except JsonSchemaValidationError as e:
            self.logger.warning(f"Schema validation failed: {str(e)}")
            return False
    
    def _validate_semantic_integrity(self, record: Dict[str, Any], schema: SchemaVersion) -> bool:
        """Validate semantic integrity of migrated record"""
        
        # Check required fields
        for field in schema.metadata.required_fields:
            if field not in record or record[field] is None:
                return False
        
        # Check field types
        for field, type_def in schema.type_definitions.items():
            if field in record and record[field] is not None:
                if not self._check_field_type(record[field], type_def):
                    return False
        
        # Check constraints
        for field, constraints in schema.constraints.items():
            if field in record and record[field] is not None:
                if not self._check_constraints(record[field], constraints):
                    return False
        
        return True
    
    def _check_field_type(self, value: Any, type_def: str) -> bool:
        """Check if value matches type definition"""
        if ':' in type_def:
            base_type, modifier = type_def.split(':', 1)
        else:
            base_type = type_def
            modifier = None
        
        type_checks = {
            'string': lambda v: isinstance(v, str),
            'number': lambda v: isinstance(v, (int, float)),
            'integer': lambda v: isinstance(v, int),
            'boolean': lambda v: isinstance(v, bool),
            'object': lambda v: isinstance(v, dict),
            'array': lambda v: isinstance(v, list)
        }
        
        if base_type in type_checks:
            return type_checks[base_type](value)
        
        return True
    
    def _check_constraints(self, value: Any, constraints: Dict[str, Any]) -> bool:
        """Check if value satisfies constraints"""
        
        if 'minimum' in constraints and isinstance(value, (int, float)):
            if value < constraints['minimum']:
                return False
        
        if 'maximum' in constraints and isinstance(value, (int, float)):
            if value > constraints['maximum']:
                return False
        
        if 'minLength' in constraints and isinstance(value, str):
            if len(value) < constraints['minLength']:
                return False
        
        if 'maxLength' in constraints and isinstance(value, str):
            if len(value) > constraints['maxLength']:
                return False
        
        if 'enum' in constraints:
            if value not in constraints['enum']:
                return False
        
        if 'pattern' in constraints and isinstance(value, str):
            if not re.match(constraints['pattern'], value):
                return False
        
        return True
    
    def _get_optimal_migration_path_impl(self, source_version: str, target_version: str) -> Optional[MigrationPath]:
        """Get optimal migration path between versions (implementation)"""
        
        # Check for direct path
        direct_path = self.registry.get_migration_path(source_version, target_version)
        if direct_path:
            return direct_path
        
        # Find shortest path using BFS
        return self._find_migration_path_bfs(source_version, target_version)
    
    def _find_migration_path_bfs(self, source_version: str, target_version: str) -> Optional[MigrationPath]:
        """Find migration path using breadth-first search"""
        
        from collections import deque
        
        queue = deque([(source_version, [])])
        visited = set()
        
        while queue:
            current_version, path = queue.popleft()
            
            if current_version == target_version:
                # Construct migration path
                if not path:
                    return None
                
                migration_functions = []
                for i in range(len(path) - 1):
                    step_path = self.registry.get_migration_path(path[i], path[i + 1])
                    if step_path:
                        migration_functions.extend(step_path.migration_functions)
                
                return MigrationPath(
                    source_version=source_version,
                    target_version=target_version,
                    intermediate_versions=path[1:-1],
                    total_steps=len(path) - 1,
                    migration_functions=migration_functions,
                    estimated_time_ms=0.1 * (len(path) - 1),
                    compatibility_level=SchemaCompatibilityLevel.BACKWARD,
                    risk_level="medium" if len(path) > 2 else "low"
                )
            
            if current_version in visited:
                continue
            
            visited.add(current_version)
            
            # Check all possible next versions
            for next_version in self.registry.version_chain:
                if self.registry.get_migration_path(current_version, next_version):
                    queue.append((next_version, path + [current_version, next_version]))
        
        return None
    
    def _analyze_migration_changes(self, 
                                  original: Dict[str, Any], 
                                  migrated: Dict[str, Any],
                                  source_version: str,
                                  target_version: str) -> Tuple[List[str], List[str], List[str]]:
        """Analyze changes made during migration"""
        
        original_keys = set(original.keys())
        migrated_keys = set(migrated.keys())
        
        fields_added = list(migrated_keys - original_keys)
        fields_removed = list(original_keys - migrated_keys)
        
        # Detect transformed fields
        fields_transformed = []
        for key in original_keys & migrated_keys:
            if original[key] != migrated[key]:
                # Check if it's a type transformation
                if type(original[key]) != type(migrated[key]):
                    fields_transformed.append(key)
                # Check if it's a value transformation (for enums, etc.)
                elif key in ['execution_phase', 'anomaly_type']:
                    fields_transformed.append(key)
        
        return fields_added, fields_removed, fields_transformed
    
    # =========================================================================
    # Compatibility Methods
    # =========================================================================
    
    async def validate_schema_compatibility(self, 
                                          source_version: str, 
                                          target_version: str) -> Dict[str, Any]:
        """
        Validate compatibility between two schema versions
        
        Args:
            source_version: Source schema version
            target_version: Target schema version
            
        Returns:
            Compatibility validation result
        """
        result = {
            'is_compatible': False,
            'compatibility_level': None,
            'breaking_changes': [],
            'warnings': [],
            'migration_available': False,
            'risk_assessment': None
        }
        
        source_schema = self.registry.get_schema(source_version)
        target_schema = self.registry.get_schema(target_version)
        
        if not source_schema or not target_schema:
            result['breaking_changes'].append("Schema version not found")
            return result
        
        # Check for migration path
        migration_path = self._get_optimal_migration_path(source_version, target_version)
        result['migration_available'] = migration_path is not None
        
        if migration_path:
            result['risk_assessment'] = migration_path.risk_level
        
        # Analyze compatibility
        compatibility_analysis = await self.compatibility_validator.analyze(
            source_schema, target_schema
        )
        
        result.update(compatibility_analysis)
        
        return result
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _to_dict(self, record: Any) -> Dict[str, Any]:
        """Convert record to dictionary"""
        if isinstance(record, dict):
            return record
        elif hasattr(record, '__dict__'):
            return record.__dict__
        elif hasattr(record, '_asdict'):
            return record._asdict()
        elif hasattr(record, '__dataclass_fields__'):
            return asdict(record)
        else:
            return dict(record)
    
    def _from_dict(self, cls: type, data: Dict[str, Any]) -> Any:
        """Convert dictionary back to original class type"""
        try:
            return cls(**data)
        except:
            return data
    
    def _update_statistics(self, success: bool, migration_time_ms: float, source_version: Optional[str]):
        """Update migration statistics"""
        self.stats['total_migrations'] += 1
        
        if success:
            self.stats['successful_migrations'] += 1
        else:
            self.stats['failed_migrations'] += 1
        
        if source_version:
            self.stats['migrations_by_version'][source_version] += 1
        
        self.stats['migration_times'].append(migration_time_ms)
        
        # Keep only last 1000 samples for average calculation
        if len(self.stats['migration_times']) > 1000:
            self.stats['migration_times'] = self.stats['migration_times'][-1000:]
        
        self.stats['average_migration_time_ms'] = np.mean(self.stats['migration_times'])
    
    # =========================================================================
    # Public Interface Methods
    # =========================================================================
    
    def get_current_metadata(self) -> SchemaMetadata:
        """Get metadata for current schema version"""
        if self.current_schema:
            return self.current_schema.metadata
        
        # Return default metadata if schema not found
        return SchemaMetadata(
            version=self.current_version,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            compatibility_level=SchemaCompatibilityLevel.BACKWARD.value,
            migration_applied=False,
            schema_hash="unknown",
            field_count=0,
            required_fields=[],
            optional_fields=[]
        )
    
    def get_migration_statistics(self) -> Dict[str, Any]:
        """Get current migration statistics"""
        return {
            **self.stats,
            'success_rate': (self.stats['successful_migrations'] / self.stats['total_migrations'] * 100) 
                          if self.stats['total_migrations'] > 0 else 0,
            'cache_size': len(self.migration_cache),
            'registered_schemas': len(self.registry.schemas),
            'available_migration_paths': len(self.registry.migration_paths)
        }
    
    def reset_statistics(self):
        """Reset migration statistics"""
        self._initialize_statistics()
        self.logger.info("Migration statistics reset")
    
    async def health_check(self) -> Dict[str, str]:
        """Perform health check"""
        try:
            # Test migration with sample record
            test_record = {
                'id': 'health-check',
                'timestamp': 1234567890,
                'function': 'test',
                'phase': 'exec',
                'data': {},
                'version': 'v1.0'
            }
            
            result = await self.migrate_record_to_current_schema(test_record)
            
            if result.success or result.status == MigrationStatus.NOT_REQUIRED:
                return {'status': 'healthy', 'message': 'Schema evolution engine operational'}
            else:
                return {'status': 'warning', 'message': f'Migration test failed: {result.error_message}'}
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


# =============================================================================
# Supporting Classes
# =============================================================================

class SchemaInferencer:
    """
    Infers schema version from record structure
    """
    
    def __init__(self):
        """Initialize schema inferencer"""
        self.logger = logging.getLogger("SCAFAD.Layer1.SchemaInferencer")
    
    async def infer_version(self, record: Dict[str, Any], known_schemas: Dict[str, SchemaVersion]) -> Optional[str]:
        """
        Infer schema version from record structure
        
        Args:
            record: Record to analyze
            known_schemas: Dictionary of known schema versions
            
        Returns:
            Inferred schema version or None
        """
        best_match = None
        best_score = 0
        
        for version, schema in known_schemas.items():
            score = self._calculate_match_score(record, schema)
            
            if score > best_score:
                best_score = score
                best_match = version
        
        # Require at least 70% field match
        if best_score >= 0.7:
            self.logger.debug(f"Inferred schema version {best_match} with confidence {best_score:.2f}")
            return best_match
        
        return None
    
    def _calculate_match_score(self, record: Dict[str, Any], schema: SchemaVersion) -> float:
        """Calculate how well a record matches a schema"""
        
        record_fields = set(record.keys())
        schema_fields = set(schema.field_mappings.keys())
        required_fields = set(schema.metadata.required_fields)
        
        # Check if all required fields are present
        if not required_fields.issubset(record_fields):
            return 0.0
        
        # Calculate field overlap
        common_fields = record_fields & schema_fields
        field_score = len(common_fields) / len(schema_fields) if schema_fields else 0
        
        # Check field types
        type_matches = 0
        for field in common_fields:
            if field in schema.type_definitions:
                expected_type = schema.type_definitions[field].split(':')[0]
                if self._check_type_match(record[field], expected_type):
                    type_matches += 1
        
        type_score = type_matches / len(common_fields) if common_fields else 0
        
        # Combined score (weighted average)
        return 0.6 * field_score + 0.4 * type_score
    
    def _check_type_match(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type"""
        type_map = {
            'string': str,
            'number': (int, float),
            'integer': int,
            'boolean': bool,
            'object': dict,
            'array': list
        }
        
        if expected_type in type_map:
            return isinstance(value, type_map[expected_type])
        
        return True


class CompatibilityValidator:
    """
    Validates compatibility between schema versions
    """
    
    def __init__(self):
        """Initialize compatibility validator"""
        self.logger = logging.getLogger("SCAFAD.Layer1.CompatibilityValidator")
    
    async def analyze(self, source_schema: SchemaVersion, target_schema: SchemaVersion) -> Dict[str, Any]:
        """
        Analyze compatibility between two schemas
        
        Args:
            source_schema: Source schema version
            target_schema: Target schema version
            
        Returns:
            Compatibility analysis result
        """
        result = {
            'is_compatible': True,
            'compatibility_level': None,
            'breaking_changes': [],
            'warnings': []
        }
        
        # Check field additions (backward compatibility)
        source_fields = set(source_schema.field_mappings.keys())
        target_fields = set(target_schema.field_mappings.keys())
        
        added_fields = target_fields - source_fields
        removed_fields = source_fields - target_fields
        
        # Check required field additions (breaking change for backward compatibility)
        for field in added_fields:
            if field in target_schema.metadata.required_fields:
                result['breaking_changes'].append(f"Required field '{field}' added")
                result['is_compatible'] = False
        
        # Check field removals (breaking change for forward compatibility)
        for field in removed_fields:
            if field in source_schema.metadata.required_fields:
                result['warnings'].append(f"Required field '{field}' removed")
        
        # Check type changes
        common_fields = source_fields & target_fields
        for field in common_fields:
            source_type = source_schema.type_definitions.get(field)
            target_type = target_schema.type_definitions.get(field)
            
            if source_type != target_type:
                if not self._are_types_compatible(source_type, target_type):
                    result['breaking_changes'].append(
                        f"Type change for field '{field}': {source_type} -> {target_type}"
                    )
                    result['is_compatible'] = False
        
        # Determine compatibility level
        if not removed_fields and not result['breaking_changes']:
            result['compatibility_level'] = SchemaCompatibilityLevel.BACKWARD.value
        elif not added_fields and not result['breaking_changes']:
            result['compatibility_level'] = SchemaCompatibilityLevel.FORWARD.value
        elif not result['breaking_changes']:
            result['compatibility_level'] = SchemaCompatibilityLevel.FULL.value
        else:
            result['compatibility_level'] = SchemaCompatibilityLevel.NONE.value
        
        return result
    
    def _are_types_compatible(self, source_type: str, target_type: str) -> bool:
        """Check if two types are compatible"""
        
        # Handle optional modifier
        source_base = source_type.split(':')[0] if source_type else ''
        target_base = target_type.split(':')[0] if target_type else ''
        
        # Same base type is always compatible
        if source_base == target_base:
            return True
        
        # Number types are compatible
        if source_base in ['integer', 'number'] and target_base in ['integer', 'number']:
            return True
        
        # String can be converted to most types
        if source_base == 'string':
            return True
        
        return False


# =============================================================================
# Export public interface
# =============================================================================

__all__ = [
    'SchemaEvolutionEngine',
    'SchemaMetadata',
    'MigrationResult',
    'SchemaVersion',
    'MigrationPath',
    'FieldMapping',
    'SchemaCompatibilityLevel',
    'MigrationStrategy',
    'SchemaChangeType',
    'MigrationStatus',
    'SchemaRegistry',
    'SchemaInferencer',
    'CompatibilityValidator'
]

# =============================================================================
# Public API -- Phase 3 implementation
# Imported by tests/unit/test_layer1_schema.py
# =============================================================================
from dataclasses import dataclass as _dc, field as _field
from typing import Any as _Any, List as _List, Dict as _Dict, Optional as _Opt, Callable as _Callable
from enum import Enum as _Enum
import time as _time
import copy as _copy


class CompatibilityLevel(_Enum):
    BACKWARD = "backward"
    FORWARD  = "forward"
    FULL     = "full"
    NONE     = "none"


@_dc
class SchemaVersion:
    major:       int  = 0
    minor:       int  = 0
    patch:       int  = 0
    timestamp:   _Any = None
    description: str  = ""

    def _tuple(self):
        return (self.major, self.minor, self.patch)

    def __lt__(self, other):  return self._tuple() <  other._tuple()
    def __le__(self, other):  return self._tuple() <= other._tuple()
    def __gt__(self, other):  return self._tuple() >  other._tuple()
    def __ge__(self, other):  return self._tuple() >= other._tuple()
    def __eq__(self, other):
        if not isinstance(other, SchemaVersion): return NotImplemented
        return self._tuple() == other._tuple()
    def __hash__(self): return hash(self._tuple())

    def __str__(self) -> str:
        if self.patch:
            return f"{self.major}.{self.minor}.{self.patch}"
        return f"{self.major}.{self.minor}"

    def to_dict(self) -> dict:
        ts = self.timestamp
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts) if ts else None
        return {
            "major":       self.major,
            "minor":       self.minor,
            "patch":       self.patch,
            "timestamp":   ts_str,
            "description": self.description,
        }


@_dc
class SchemaChange:
    change_type:   str               = ""
    field_name:    str               = ""
    old_value:     _Any              = None
    new_value:     _Any              = None
    compatibility: CompatibilityLevel = CompatibilityLevel.NONE
    description:   str               = ""

    def to_dict(self) -> dict:
        return {
            "change_type":   self.change_type,
            "field_name":    self.field_name,
            "old_value":     self.old_value,
            "new_value":     self.new_value,
            "compatibility": self.compatibility.value,
            "description":   self.description,
        }

    def is_backward_compatible(self) -> bool:
        return self.compatibility in (CompatibilityLevel.BACKWARD, CompatibilityLevel.FULL)

    def is_forward_compatible(self) -> bool:
        return self.compatibility in (CompatibilityLevel.FORWARD, CompatibilityLevel.FULL)


@_dc
class SchemaMetadata:
    schema_id:       str                    = ""
    version:         _Opt[SchemaVersion]    = None
    fields:          _Dict[str, dict]       = _field(default_factory=dict)
    required_fields: _List[str]             = _field(default_factory=list)
    optional_fields: _List[str]             = _field(default_factory=list)
    constraints:     _Dict[str, dict]       = _field(default_factory=dict)

    def is_valid(self) -> bool:
        return all(f in self.fields for f in self.required_fields)

    def to_dict(self) -> dict:
        return {
            "schema_id":       self.schema_id,
            "version":         self.version.to_dict() if self.version else {},
            "fields":          self.fields,
            "required_fields": self.required_fields,
            "optional_fields": self.optional_fields,
            "constraints":     self.constraints,
        }

    def has_field(self, field_name: str) -> bool:
        return field_name in self.fields

    def is_required(self, field_name: str) -> bool:
        return field_name in self.required_fields

    def get_field_type(self, field_name: str) -> _Opt[str]:
        return self.fields.get(field_name, {}).get("type")

    def get_field_constraints(self, field_name: str) -> dict:
        return self.constraints.get(field_name, {})


@_dc
class MigrationStrategy:
    name:               str                    = ""
    source_version:     _Opt[SchemaVersion]    = None
    target_version:     _Opt[SchemaVersion]    = None
    changes:            _List[SchemaChange]    = _field(default_factory=list)
    migration_function: _Opt[_Callable]        = None

    def is_valid(self) -> bool:
        if self.source_version is None or self.target_version is None:
            return False
        return self.source_version < self.target_version

    def execute(self, data: _Any) -> _Any:
        if self.migration_function is None:
            return data
        return self.migration_function(_copy.deepcopy(data))

    def to_dict(self) -> dict:
        return {
            "name":           self.name,
            "source_version": self.source_version.to_dict() if self.source_version else {},
            "target_version": self.target_version.to_dict() if self.target_version else {},
            "changes":        [c.to_dict() for c in self.changes],
        }


@_dc
class MigrationResult:
    success:         bool                  = True
    source_version:  _Opt[SchemaVersion]  = None
    target_version:  _Opt[SchemaVersion]  = None
    migrated_data:   _Opt[_Any]           = None
    changes_applied: _List[SchemaChange]  = _field(default_factory=list)
    warnings:        _List[str]           = _field(default_factory=list)
    errors:          _List[str]           = _field(default_factory=list)
    processing_time: float                = 0.0

    def to_dict(self) -> dict:
        return {
            "success":         self.success,
            "source_version":  self.source_version.to_dict() if self.source_version else {},
            "target_version":  self.target_version.to_dict() if self.target_version else {},
            "migrated_data":   self.migrated_data,
            "changes_applied": [c.to_dict() for c in self.changes_applied],
            "warnings":        self.warnings,
            "errors":          self.errors,
            "processing_time": self.processing_time,
        }

    def generate_summary(self) -> str:
        status = "successful" if self.success else "failed"
        sv = str(self.source_version) if self.source_version else "?"
        tv = str(self.target_version) if self.target_version else "?"
        return (
            f"Migration {status}: "
            f"{sv} -> {tv}, "
            f"{self.processing_time}s"
        )


@_dc
class _SchemaValidResult:
    is_valid: bool
    errors:   _List[str] = _field(default_factory=list)


@_dc
class _CompatibilityResult:
    level:         CompatibilityLevel = CompatibilityLevel.NONE
    is_compatible: bool               = False
    notes:         _List[str]         = _field(default_factory=list)


class SchemaEvolutionEngine:
    def __init__(self, config=None):
        self.schemas              = {}
        self.migration_strategies = []
        self.current_version      = None

    def register_schema(self, schema):
        self.schemas[schema.schema_id] = schema

    def register_migration_strategy(self, strategy):
        self.migration_strategies.append(strategy)

    def validate_data(self, data, schema_id):
        schema = self.schemas.get(schema_id)
        if schema is None:
            return _SchemaValidResult(is_valid=False, errors=[f"Unknown schema: {schema_id}"])
        errors = []
        if isinstance(data, dict):
            for f in schema.required_fields:
                if f not in data:
                    errors.append(f"Missing required field: {f}")
        else:
            errors.append("Data must be a dict")
        return _SchemaValidResult(is_valid=len(errors) == 0, errors=errors)

    def _find_path(self, source_ver, target_ver):
        if source_ver == target_ver:
            return []
        from collections import deque
        queue = deque([(source_ver, [])])
        visited = {source_ver._tuple()}
        while queue:
            current, path = queue.popleft()
            for strat in self.migration_strategies:
                if strat.source_version is None:
                    continue
                if strat.source_version._tuple() == current._tuple():
                    next_ver = strat.target_version
                    if next_ver is None:
                        continue
                    new_path = path + [strat]
                    if next_ver._tuple() == target_ver._tuple():
                        return new_path
                    if next_ver._tuple() not in visited:
                        visited.add(next_ver._tuple())
                        queue.append((next_ver, new_path))
        return None

    def migrate_data(self, data, source_schema_id, target_schema_id):
        if source_schema_id not in self.schemas:
            raise ValueError(f"Unknown source schema: {source_schema_id}")
        if target_schema_id not in self.schemas:
            raise ValueError(f"Unknown target schema: {target_schema_id}")
        source_schema = self.schemas[source_schema_id]
        target_schema = self.schemas[target_schema_id]
        t0 = _time.perf_counter()
        path = self._find_path(source_schema.version, target_schema.version)
        if path is None:
            raise ValueError(f"No migration path from {source_schema_id} to {target_schema_id}")
        current_data = _copy.deepcopy(data)
        changes_applied = []
        for strat in path:
            current_data = strat.execute(current_data)
            changes_applied.extend(strat.changes)
        elapsed = round(_time.perf_counter() - t0, 6)
        return MigrationResult(
            success=True,
            source_version=source_schema.version,
            target_version=target_schema.version,
            migrated_data=current_data,
            changes_applied=changes_applied,
            processing_time=elapsed,
        )

    def check_compatibility(self, source_schema_id, target_schema_id):
        source = self.schemas.get(source_schema_id)
        target = self.schemas.get(target_schema_id)
        if source is None or target is None:
            return _CompatibilityResult(level=CompatibilityLevel.NONE, is_compatible=False)
        src_req = set(source.required_fields)
        tgt_req = set(target.required_fields)
        src_opt = set(source.optional_fields)
        tgt_opt = set(target.optional_fields)
        new_required     = tgt_req - src_req
        removed_required = src_req - tgt_req
        if new_required or removed_required:
            level = CompatibilityLevel.NONE
        elif tgt_opt > src_opt:
            level = CompatibilityLevel.BACKWARD
        elif src_opt > tgt_opt:
            level = CompatibilityLevel.FORWARD
        else:
            level = CompatibilityLevel.FULL
        return _CompatibilityResult(
            level=level,
            is_compatible=(level is not CompatibilityLevel.NONE),
        )


# Backward-compatible public alias used by older integration tests.
SchemaManager = SchemaEvolutionEngine
