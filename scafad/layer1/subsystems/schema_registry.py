#!/usr/bin/env python3
"""
SCAFAD Layer 1: Schema Registry Subsystem
========================================

The Schema Registry manages schema versioning, registration, and compatibility
checking for Layer 1's behavioral intake zone. It provides:

- Schema version registration and management
- Backward and forward compatibility validation
- Schema migration planning and execution
- Schema evolution tracking and auditing
- Field mapping and transformation rules

Author: SCAFAD Research Team
Institution: Birmingham Newman University
License: MIT
Version: 1.0.0
"""

import json
import hashlib
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from enum import Enum, auto
from datetime import datetime, timezone
import copy
from pathlib import Path

# =============================================================================
# Schema Registry Data Models
# =============================================================================

class SchemaCompatibility(Enum):
    """Schema compatibility levels"""
    FULLY_COMPATIBLE = "fully_compatible"      # No changes needed
    BACKWARD_COMPATIBLE = "backward_compatible"  # Old can read new
    FORWARD_COMPATIBLE = "forward_compatible"    # New can read old
    INCOMPATIBLE = "incompatible"              # Cannot interoperate
    PARTIALLY_COMPATIBLE = "partially_compatible"  # Some compatibility

class FieldType(Enum):
    """Supported field types"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    IP_ADDRESS = "ip_address"
    URL = "url"
    EMAIL = "email"
    JSON_OBJECT = "json_object"
    BASE64 = "base64"
    UUID = "uuid"
    ENUM = "enum"
    ARRAY = "array"
    NESTED_OBJECT = "nested_object"
    BINARY = "binary"

class FieldConstraint(Enum):
    """Field constraint types"""
    REQUIRED = "required"
    OPTIONAL = "optional"
    UNIQUE = "unique"
    INDEXED = "indexed"
    ENCRYPTED = "encrypted"
    HASHED = "hashed"
    REDACTED = "redacted"

@dataclass
class SchemaField:
    """Schema field definition"""
    name: str
    field_type: FieldType
    description: str = ""
    constraints: List[FieldConstraint] = field(default_factory=list)
    default_value: Optional[Any] = None
    validation_rules: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Post-initialization validation"""
        if not self.name:
            raise ValueError("Field name cannot be empty")
        
        if not isinstance(self.field_type, FieldType):
            self.field_type = FieldType(self.field_type)

@dataclass
class SchemaVersion:
    """Schema version definition"""
    version: str
    description: str
    created_at: datetime
    fields: Dict[str, SchemaField]
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_deprecated: bool = False
    deprecation_date: Optional[datetime] = None
    migration_paths: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization validation"""
        if not self.version:
            raise ValueError("Schema version cannot be empty")
        
        if not self.fields:
            raise ValueError("Schema must have at least one field")
        
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)

@dataclass
class SchemaMigration:
    """Schema migration definition"""
    from_version: str
    to_version: str
    migration_type: str
    transformation_rules: Dict[str, Any]
    validation_rules: Dict[str, Any]
    rollback_supported: bool = True
    estimated_duration_ms: float = 0.0
    risk_level: str = "low"

@dataclass
class CompatibilityReport:
    """Schema compatibility analysis report"""
    source_version: str
    target_version: str
    compatibility_level: SchemaCompatibility
    field_changes: Dict[str, str]
    breaking_changes: List[str]
    migration_required: bool
    migration_path: Optional[str] = None
    estimated_migration_effort: str = "low"

# =============================================================================
# Schema Registry Core Class
# =============================================================================

class SchemaRegistry:
    """
    Schema Registry for managing schema versions and compatibility
    
    The Schema Registry provides centralized schema management for Layer 1,
    ensuring consistent data structures across the behavioral intake zone.
    """
    
    def __init__(self, config: Any = None):
        """Initialize the Schema Registry"""
        self.config = config
        self.logger = logging.getLogger("SCAFAD.Layer1.SchemaRegistry")
        
        # Schema storage
        self.schemas: Dict[str, SchemaVersion] = {}
        self.migrations: Dict[str, SchemaMigration] = {}
        self.field_mappings: Dict[str, Dict[str, str]] = {}
        
        # Registry state
        self.current_version: str = "v2.1"
        self.default_schema: Optional[SchemaVersion] = None
        self.registry_initialized: bool = False
        
        # Performance tracking
        self.registry_stats = {
            'total_schemas': 0,
            'total_migrations': 0,
            'compatibility_checks': 0,
            'migration_executions': 0
        }
        
        self.logger.info("Schema Registry initialized")
    
    def register_schema(self, schema: SchemaVersion) -> bool:
        """
        Register a new schema version
        
        Args:
            schema: SchemaVersion to register
            
        Returns:
            bool: True if registration successful
        """
        try:
            # Validate schema
            if not self._validate_schema(schema):
                self.logger.error(f"Schema validation failed for version {schema.version}")
                return False
            
            # Check for version conflicts
            if schema.version in self.schemas:
                self.logger.warning(f"Schema version {schema.version} already exists, updating")
            
            # Register schema
            self.schemas[schema.version] = schema
            self.registry_stats['total_schemas'] += 1
            
            # Set as default if first schema or specified
            if not self.default_schema or schema.version == self.current_version:
                self.default_schema = schema
            
            # Update field mappings
            self._update_field_mappings(schema)
            
            self.logger.info(f"Schema version {schema.version} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register schema {schema.version}: {str(e)}")
            return False
    
    def get_schema(self, version: str) -> Optional[SchemaVersion]:
        """
        Retrieve a schema version
        
        Args:
            version: Schema version to retrieve
            
        Returns:
            SchemaVersion or None if not found
        """
        return self.schemas.get(version)
    
    def get_current_schema(self) -> Optional[SchemaVersion]:
        """Get the current default schema"""
        return self.default_schema or self.schemas.get(self.current_version)
    
    def list_schemas(self) -> List[str]:
        """List all registered schema versions"""
        return list(self.schemas.keys())
    
    def check_compatibility(self, source_version: str, target_version: str) -> CompatibilityReport:
        """
        Check compatibility between two schema versions
        
        Args:
            source_version: Source schema version
            target_version: Target schema version
            
        Returns:
            CompatibilityReport with compatibility analysis
        """
        try:
            self.registry_stats['compatibility_checks'] += 1
            
            source_schema = self.schemas.get(source_version)
            target_schema = self.schemas.get(target_version)
            
            if not source_schema or not target_schema:
                return CompatibilityReport(
                    source_version=source_version,
                    target_version=target_version,
                    compatibility_level=SchemaCompatibility.INCOMPATIBLE,
                    field_changes={},
                    breaking_changes=["Schema version not found"],
                    migration_required=True
                )
            
            # Analyze field changes
            field_changes = self._analyze_field_changes(source_schema, target_schema)
            breaking_changes = self._identify_breaking_changes(source_schema, target_schema)
            
            # Determine compatibility level
            compatibility_level = self._determine_compatibility_level(
                field_changes, breaking_changes
            )
            
            # Check if migration is required
            migration_required = compatibility_level != SchemaCompatibility.FULLY_COMPATIBLE
            
            # Find migration path
            migration_path = self._find_migration_path(source_version, target_version)
            
            return CompatibilityReport(
                source_version=source_version,
                target_version=target_version,
                compatibility_level=compatibility_level,
                field_changes=field_changes,
                breaking_changes=breaking_changes,
                migration_required=migration_required,
                migration_path=migration_path,
                estimated_migration_effort=self._estimate_migration_effort(breaking_changes)
            )
            
        except Exception as e:
            self.logger.error(f"Compatibility check failed: {str(e)}")
            return CompatibilityReport(
                source_version=source_version,
                target_version=target_version,
                compatibility_level=SchemaCompatibility.INCOMPATIBLE,
                field_changes={},
                breaking_changes=[f"Compatibility check error: {str(e)}"],
                migration_required=True
            )
    
    def register_migration(self, migration: SchemaMigration) -> bool:
        """
        Register a schema migration
        
        Args:
            migration: SchemaMigration to register
            
        Returns:
            bool: True if registration successful
        """
        try:
            migration_key = f"{migration.from_version}->{migration.to_version}"
            
            # Validate migration
            if not self._validate_migration(migration):
                self.logger.error(f"Migration validation failed for {migration_key}")
                return False
            
            # Register migration
            self.migrations[migration_key] = migration
            self.registry_stats['total_migrations'] += 1
            
            # Update schema migration paths
            if migration.from_version in self.schemas:
                self.schemas[migration.from_version].migration_paths[migration.to_version] = migration_key
            
            self.logger.info(f"Migration {migration_key} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register migration: {str(e)}")
            return False
    
    def get_migration(self, from_version: str, to_version: str) -> Optional[SchemaMigration]:
        """
        Get migration between two versions
        
        Args:
            from_version: Source version
            to_version: Target version
            
        Returns:
            SchemaMigration or None if not found
        """
        migration_key = f"{from_version}->{to_version}"
        return self.migrations.get(migration_key)
    
    def list_migrations(self) -> List[str]:
        """List all registered migrations"""
        return list(self.migrations.keys())
    
    def migrate_record(self, record: Dict[str, Any], target_version: str) -> Tuple[Dict[str, Any], bool]:
        """
        Migrate a record to a target schema version
        
        Args:
            record: Record to migrate
            target_version: Target schema version
            
        Returns:
            Tuple of (migrated_record, success)
        """
        try:
            # Determine current schema version
            current_version = record.get('schema_version', self.current_version)
            
            if current_version == target_version:
                return record, True
            
            # Check compatibility
            compatibility = self.check_compatibility(current_version, target_version)
            
            if compatibility.compatibility_level == SchemaCompatibility.INCOMPATIBLE:
                self.logger.error(f"Cannot migrate from {current_version} to {target_version}")
                return record, False
            
            # Execute migration
            migrated_record = self._execute_migration(record, current_version, target_version)
            
            if migrated_record:
                self.registry_stats['migration_executions'] += 1
                self.logger.info(f"Record migrated from {current_version} to {target_version}")
                return migrated_record, True
            else:
                return record, False
                
        except Exception as e:
            self.logger.error(f"Migration failed: {str(e)}")
            return record, False
    
    def get_field_mapping(self, source_version: str, target_version: str) -> Dict[str, str]:
        """
        Get field mapping between two schema versions
        
        Args:
            source_version: Source schema version
            target_version: Target schema version
            
        Returns:
            Dictionary mapping source fields to target fields
        """
        mapping_key = f"{source_version}->{target_version}"
        return self.field_mappings.get(mapping_key, {})
    
    def validate_record(self, record: Dict[str, Any], schema_version: str) -> Tuple[bool, List[str]]:
        """
        Validate a record against a schema version
        
        Args:
            record: Record to validate
            schema_version: Schema version to validate against
            
        Returns:
            Tuple of (is_valid, validation_errors)
        """
        try:
            schema = self.schemas.get(schema_version)
            if not schema:
                return False, [f"Schema version {schema_version} not found"]
            
            errors = []
            
            # Check required fields
            for field_name, field_def in schema.fields.items():
                if FieldConstraint.REQUIRED in field_def.constraints:
                    if field_name not in record:
                        errors.append(f"Required field '{field_name}' missing")
                    elif record[field_name] is None:
                        errors.append(f"Required field '{field_name}' cannot be null")
            
            # Check field types
            for field_name, field_value in record.items():
                if field_name in schema.fields:
                    field_def = schema.fields[field_name]
                    if not self._validate_field_type(field_value, field_def):
                        errors.append(f"Field '{field_name}' has invalid type")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return copy.deepcopy(self.registry_stats)
    
    def export_schema(self, version: str, format: str = "json") -> Optional[str]:
        """
        Export schema in specified format
        
        Args:
            version: Schema version to export
            format: Export format (json, yaml)
            
        Returns:
            Exported schema string or None if failed
        """
        try:
            schema = self.schemas.get(version)
            if not schema:
                return None
            
            if format.lower() == "json":
                return json.dumps(asdict(schema), indent=2, default=str)
            else:
                self.logger.warning(f"Export format {format} not supported")
                return None
                
        except Exception as e:
            self.logger.error(f"Export failed: {str(e)}")
            return None
    
    def import_schema(self, schema_data: str, format: str = "json") -> bool:
        """
        Import schema from specified format
        
        Args:
            schema_data: Schema data string
            format: Import format (json, yaml)
            
        Returns:
            bool: True if import successful
        """
        try:
            if format.lower() == "json":
                schema_dict = json.loads(schema_data)
                schema = SchemaVersion(**schema_dict)
                return self.register_schema(schema)
            else:
                self.logger.warning(f"Import format {format} not supported")
                return False
                
        except Exception as e:
            self.logger.error(f"Import failed: {str(e)}")
            return False
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _validate_schema(self, schema: SchemaVersion) -> bool:
        """Validate schema before registration"""
        try:
            # Check version format
            if not schema.version.startswith('v'):
                self.logger.error("Schema version must start with 'v'")
                return False
            
            # Check field definitions
            for field_name, field_def in schema.fields.items():
                if not isinstance(field_def, SchemaField):
                    self.logger.error(f"Invalid field definition for {field_name}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Schema validation error: {str(e)}")
            return False
    
    def _validate_migration(self, migration: SchemaMigration) -> bool:
        """Validate migration before registration"""
        try:
            # Check version existence
            if migration.from_version not in self.schemas:
                self.logger.error(f"Source schema {migration.from_version} not found")
                return False
            
            if migration.to_version not in self.schemas:
                self.logger.error(f"Target schema {migration.to_version} not found")
                return False
            
            # Check for circular migrations
            if self._would_create_circular_migration(migration):
                self.logger.error("Migration would create circular dependency")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Migration validation error: {str(e)}")
            return False
    
    def _would_create_circular_migration(self, migration: SchemaMigration) -> bool:
        """Check if migration would create circular dependency"""
        # Simple check - could be enhanced with graph analysis
        return f"{migration.to_version}->{migration.from_version}" in self.migrations
    
    def _analyze_field_changes(self, source: SchemaVersion, target: SchemaVersion) -> Dict[str, str]:
        """Analyze field changes between schemas"""
        changes = {}
        
        # Check for added fields
        for field_name in target.fields:
            if field_name not in source.fields:
                changes[field_name] = "added"
        
        # Check for removed fields
        for field_name in source.fields:
            if field_name not in target.fields:
                changes[field_name] = "removed"
        
        # Check for modified fields
        for field_name in source.fields:
            if field_name in target.fields:
                source_field = source.fields[field_name]
                target_field = target.fields[field_name]
                
                if (source_field.field_type != target_field.field_type or
                    source_field.constraints != target_field.constraints):
                    changes[field_name] = "modified"
        
        return changes
    
    def _identify_breaking_changes(self, source: SchemaVersion, target: SchemaVersion) -> List[str]:
        """Identify breaking changes between schemas"""
        breaking_changes = []
        
        # Required fields becoming optional is usually safe
        # Optional fields becoming required is breaking
        for field_name in source.fields:
            if field_name in target.fields:
                source_field = source.fields[field_name]
                target_field = target.fields[field_name]
                
                if (FieldConstraint.REQUIRED not in source_field.constraints and
                    FieldConstraint.REQUIRED in target_field.constraints):
                    breaking_changes.append(f"Field '{field_name}' became required")
        
        # Removed fields are breaking
        for field_name in source.fields:
            if field_name not in target.fields:
                breaking_changes.append(f"Field '{field_name}' was removed")
        
        return breaking_changes
    
    def _determine_compatibility_level(self, field_changes: Dict[str, str], 
                                     breaking_changes: List[str]) -> SchemaCompatibility:
        """Determine compatibility level based on changes"""
        if not field_changes and not breaking_changes:
            return SchemaCompatibility.FULLY_COMPATIBLE
        
        if not breaking_changes:
            return SchemaCompatibility.BACKWARD_COMPATIBLE
        
        if len(breaking_changes) < len(field_changes) / 2:
            return SchemaCompatibility.PARTIALLY_COMPATIBLE
        
        return SchemaCompatibility.INCOMPATIBLE
    
    def _find_migration_path(self, from_version: str, to_version: str) -> Optional[str]:
        """Find migration path between versions"""
        direct_migration = f"{from_version}->{to_version}"
        if direct_migration in self.migrations:
            return direct_migration
        
        # Could implement path finding algorithm here
        # For now, return None if no direct path
        return None
    
    def _estimate_migration_effort(self, breaking_changes: List[str]) -> str:
        """Estimate migration effort based on breaking changes"""
        if not breaking_changes:
            return "none"
        elif len(breaking_changes) <= 2:
            return "low"
        elif len(breaking_changes) <= 5:
            return "medium"
        else:
            return "high"
    
    def _execute_migration(self, record: Dict[str, Any], from_version: str, 
                          to_version: str) -> Optional[Dict[str, Any]]:
        """Execute migration on a record"""
        try:
            migration = self.get_migration(from_version, to_version)
            if not migration:
                return None
            
            # Apply transformation rules
            migrated_record = copy.deepcopy(record)
            
            # Update schema version
            migrated_record['schema_version'] = to_version
            
            # Apply field transformations
            for field_name, transformation in migration.transformation_rules.items():
                if field_name in migrated_record:
                    migrated_record[field_name] = self._apply_transformation(
                        migrated_record[field_name], transformation
                    )
            
            return migrated_record
            
        except Exception as e:
            self.logger.error(f"Migration execution failed: {str(e)}")
            return None
    
    def _apply_transformation(self, value: Any, transformation: Dict[str, Any]) -> Any:
        """Apply field transformation"""
        transform_type = transformation.get('type')
        
        if transform_type == 'rename':
            # Field renaming handled by field mapping
            return value
        elif transform_type == 'type_cast':
            target_type = transformation.get('target_type')
            return self._cast_value(value, target_type)
        elif transform_type == 'default':
            return transformation.get('default_value', value)
        else:
            return value
    
    def _cast_value(self, value: Any, target_type: str) -> Any:
        """Cast value to target type"""
        try:
            if target_type == 'string':
                return str(value)
            elif target_type == 'integer':
                return int(float(value))
            elif target_type == 'float':
                return float(value)
            elif target_type == 'boolean':
                return bool(value)
            else:
                return value
        except (ValueError, TypeError):
            return value
    
    def _validate_field_type(self, value: Any, field_def: SchemaField) -> bool:
        """Validate field value against field definition"""
        try:
            if value is None and FieldConstraint.REQUIRED not in field_def.constraints:
                return True
            
            if field_def.field_type == FieldType.STRING:
                return isinstance(value, str)
            elif field_def.field_type == FieldType.INTEGER:
                return isinstance(value, int)
            elif field_def.field_type == FieldType.FLOAT:
                return isinstance(value, (int, float))
            elif field_def.field_type == FieldType.BOOLEAN:
                return isinstance(value, bool)
            elif field_def.field_type == FieldType.TIMESTAMP:
                return isinstance(value, (int, float, str))
            else:
                return True  # Accept other types for now
                
        except Exception:
            return False
    
    def _update_field_mappings(self, schema: SchemaVersion):
        """Update field mappings for new schema"""
        # This would be enhanced with actual field mapping logic
        pass

# =============================================================================
# Schema Registry Factory Functions
# =============================================================================

def create_default_schema_registry() -> SchemaRegistry:
    """Create default schema registry with basic schemas"""
    registry = SchemaRegistry()
    
    # Create v2.0 schema
    v2_0_fields = {
        'record_id': SchemaField('record_id', FieldType.STRING, constraints=[FieldConstraint.REQUIRED]),
        'timestamp': SchemaField('timestamp', FieldType.TIMESTAMP, constraints=[FieldConstraint.REQUIRED]),
        'function_name': SchemaField('function_name', FieldType.STRING, constraints=[FieldConstraint.REQUIRED]),
        'execution_phase': SchemaField('execution_phase', FieldType.STRING, constraints=[FieldConstraint.REQUIRED]),
        'anomaly_type': SchemaField('anomaly_type', FieldType.STRING, constraints=[FieldConstraint.REQUIRED]),
        'telemetry_data': SchemaField('telemetry_data', FieldType.JSON_OBJECT, constraints=[FieldConstraint.REQUIRED])
    }
    
    v2_0_schema = SchemaVersion(
        version="v2.0",
        description="Initial Layer 1 schema version",
        created_at=datetime.now(timezone.utc),
        fields=v2_0_fields
    )
    
    # Create v2.1 schema
    v2_1_fields = copy.deepcopy(v2_0_fields)
    v2_1_fields.update({
        'provenance_chain': SchemaField('provenance_chain', FieldType.JSON_OBJECT),
        'context_metadata': SchemaField('context_metadata', FieldType.JSON_OBJECT),
        'schema_version': SchemaField('schema_version', FieldType.STRING, default_value="v2.1")
    })
    
    v2_1_schema = SchemaVersion(
        version="v2.1",
        description="Enhanced Layer 1 schema with provenance tracking",
        created_at=datetime.now(timezone.utc),
        fields=v2_1_fields
    )
    
    # Register schemas
    registry.register_schema(v2_0_schema)
    registry.register_schema(v2_1_schema)
    
    # Create migration
    v2_0_to_v2_1_migration = SchemaMigration(
        from_version="v2.0",
        to_version="v2.1",
        migration_type="forward_compatible",
        transformation_rules={
            'provenance_chain': {'type': 'default', 'default_value': None},
            'context_metadata': {'type': 'default', 'default_value': None},
            'schema_version': {'type': 'default', 'default_value': 'v2.1'}
        },
        validation_rules={},
        rollback_supported=True,
        estimated_duration_ms=0.1
    )
    
    registry.register_migration(v2_0_to_v2_1_migration)
    
    return registry

if __name__ == "__main__":
    # Example usage
    registry = create_default_schema_registry()
    
    print("Registered schemas:", registry.list_schemas())
    print("Registered migrations:", registry.list_migrations())
    
    # Test compatibility
    compatibility = registry.check_compatibility("v2.0", "v2.1")
    print(f"v2.0 -> v2.1 compatibility: {compatibility.compatibility_level.value}")
    
    # Test record validation
    test_record = {
        'record_id': 'test123',
        'timestamp': 1640995200.0,
        'function_name': 'test_function',
        'execution_phase': 'invocation',
        'anomaly_type': 'performance',
        'telemetry_data': {'cpu_usage': 85.5}
    }
    
    is_valid, errors = registry.validate_record(test_record, "v2.0")
    print(f"Record validation: {is_valid}, Errors: {errors}")
