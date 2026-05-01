"""SCAFAD Layer 0: Schema Evolution Management Module
================================================

Advanced schema evolution and validation system for serverless function data.
Implements schema versioning, migration, compatibility analysis,
and automatic evolution based on academic research.

Academic References:
- Schema Evolution in Distributed Systems (Wang et al., 2023)
- Automated Schema Migration for Cloud Applications (Li et al., 2022)
- Data Contract Evolution in Microservices (Chen et al., 2024)
- Schema Compatibility Analysis for API Evolution (Zhang et al., 2023)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, TYPE_CHECKING
import json
import hashlib
import time
import re
import logging
from collections import defaultdict, deque
from enum import Enum
import copy

from .app_config import SchemaConfig

if TYPE_CHECKING:
    from .app_config import Layer0Config
from .app_telemetry import TelemetryRecord

logger = logging.getLogger(__name__)


class SchemaChangeType(Enum):
    """Types of schema changes"""
    ADD_FIELD = "ADD_FIELD"
    REMOVE_FIELD = "REMOVE_FIELD"
    MODIFY_TYPE = "MODIFY_TYPE"
    RENAME_FIELD = "RENAME_FIELD"
    ADD_VALIDATION = "ADD_VALIDATION"
    REMOVE_VALIDATION = "REMOVE_VALIDATION"
    RESTRUCTURE = "RESTRUCTURE"


class CompatibilityLevel(Enum):
    """Levels of schema compatibility"""
    FULLY_COMPATIBLE = "FULLY_COMPATIBLE"        # No breaking changes
    BACKWARD_COMPATIBLE = "BACKWARD_COMPATIBLE"  # Old readers work with new data
    FORWARD_COMPATIBLE = "FORWARD_COMPATIBLE"    # New readers work with old data
    BREAKING_CHANGE = "BREAKING_CHANGE"          # Incompatible changes


@dataclass
class SchemaVersion:
    """Enhanced schema version with comprehensive metadata"""
    version: str
    definition: Dict[str, Any]
    timestamp: float
    description: str = ""
    author: str = "system"
    compatibility_level: CompatibilityLevel = CompatibilityLevel.FULLY_COMPATIBLE
    migration_script: Optional[str] = None
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    deprecation_warnings: List[str] = field(default_factory=list)
    usage_stats: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'version': self.version,
            'definition': self.definition,
            'timestamp': self.timestamp,
            'description': self.description,
            'author': self.author,
            'compatibility_level': self.compatibility_level.value,
            'migration_script': self.migration_script,
            'validation_rules': self.validation_rules,
            'deprecation_warnings': self.deprecation_warnings,
            'usage_stats': self.usage_stats
        }


@dataclass
class SchemaChange:
    """Represents a schema change operation"""
    change_type: SchemaChangeType
    field_path: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    description: str = ""
    breaking: bool = False
    migration_hint: Optional[str] = None


@dataclass 
class ValidationResult:
    """Result of schema validation"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    score: float = 1.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationPlan:
    """Schema migration execution plan"""
    from_version: str
    to_version: str
    changes: List[SchemaChange]
    migration_steps: List[str]
    estimated_impact: float
    rollback_plan: List[str]
    validation_tests: List[str]


class SchemaValidator:
    """Advanced schema validation engine"""
    
    def __init__(self, config: SchemaConfig):
        self.config = config
        self.validation_cache: Dict[str, ValidationResult] = {}
        self.custom_validators: Dict[str, Callable] = {}
        self._initialize_builtin_validators()
    
    def _initialize_builtin_validators(self):
        """Initialize built-in validation rules"""
        self.custom_validators = {
            'required': self._validate_required,
            'type': self._validate_type,
            'range': self._validate_range,
            'pattern': self._validate_pattern,
            'enum': self._validate_enum,
            'length': self._validate_length,
            'custom': self._validate_custom
        }
    
    def validate_data(self, data: Dict[str, Any], schema_def: Dict[str, Any]) -> ValidationResult:
        """Validate data against schema definition"""
        
        # Create cache key
        data_hash = self._hash_object(data)
        schema_hash = self._hash_object(schema_def)
        cache_key = f"{data_hash}_{schema_hash}"
        
        # Check cache
        if cache_key in self.validation_cache:
            return self.validation_cache[cache_key]
        
        errors = []
        warnings = []
        details = {}
        
        try:
            # Validate structure
            structure_result = self._validate_structure(data, schema_def)
            errors.extend(structure_result.get('errors', []))
            warnings.extend(structure_result.get('warnings', []))
            
            # Validate types
            type_result = self._validate_types(data, schema_def)
            errors.extend(type_result.get('errors', []))
            warnings.extend(type_result.get('warnings', []))
            
            # Validate constraints
            constraint_result = self._validate_constraints(data, schema_def)
            errors.extend(constraint_result.get('errors', []))
            warnings.extend(constraint_result.get('warnings', []))
            
            # Calculate validation score
            total_checks = len(structure_result.get('checks', [])) + len(type_result.get('checks', [])) + len(constraint_result.get('checks', []))
            failed_checks = len(errors)
            score = max(0.0, (total_checks - failed_checks) / max(total_checks, 1))
            
            details = {
                'structure_validation': structure_result,
                'type_validation': type_result,
                'constraint_validation': constraint_result,
                'total_checks': total_checks,
                'failed_checks': failed_checks
            }
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            score = 0.0
        
        result = ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            score=score,
            details=details
        )
        
        # Cache result
        self.validation_cache[cache_key] = result
        
        return result
    
    def _validate_structure(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data structure against schema"""
        errors = []
        warnings = []
        checks = []
        
        required_fields = schema.get('required', [])
        properties = schema.get('properties', {})
        additional_properties = schema.get('additionalProperties', True)
        
        # Check required fields
        for field in required_fields:
            checks.append(f"required_field_{field}")
            if field not in data:
                errors.append(f"Required field '{field}' is missing")
        
        # Check for unexpected fields
        if not additional_properties:
            for field in data:
                checks.append(f"allowed_field_{field}")
                if field not in properties:
                    errors.append(f"Unexpected field '{field}' is not allowed")
        
        # Check deprecated fields
        for field, field_schema in properties.items():
            if field in data and field_schema.get('deprecated'):
                warnings.append(f"Field '{field}' is deprecated: {field_schema.get('deprecation_message', 'No message')}")
        
        return {
            'errors': errors,
            'warnings': warnings,
            'checks': checks
        }
    
    def _validate_types(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data types against schema"""
        errors = []
        warnings = []
        checks = []
        
        properties = schema.get('properties', {})
        
        for field, field_schema in properties.items():
            if field not in data:
                continue
                
            checks.append(f"type_check_{field}")
            value = data[field]
            expected_type = field_schema.get('type')
            
            if expected_type and not self._check_type(value, expected_type):
                errors.append(f"Field '{field}' has type {type(value).__name__}, expected {expected_type}")
        
        return {
            'errors': errors,
            'warnings': warnings,
            'checks': checks
        }
    
    def _validate_constraints(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data constraints against schema"""
        errors = []
        warnings = []
        checks = []
        
        properties = schema.get('properties', {})
        
        for field, field_schema in properties.items():
            if field not in data:
                continue
            
            value = data[field]
            
            # Validate using custom validators
            for validator_name, validator_config in field_schema.items():
                if validator_name in self.custom_validators:
                    checks.append(f"constraint_{field}_{validator_name}")
                    
                    try:
                        result = self.custom_validators[validator_name](value, validator_config, field)
                        if not result:
                            errors.append(f"Field '{field}' failed {validator_name} validation")
                    except Exception as e:
                        errors.append(f"Validation error for field '{field}': {str(e)}")
        
        return {
            'errors': errors,
            'warnings': warnings,
            'checks': checks
        }
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type"""
        type_mapping = {
            'string': str,
            'number': (int, float),
            'integer': int,
            'boolean': bool,
            'array': list,
            'object': dict,
            'null': type(None)
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            return True  # Unknown type, assume valid
        
        return isinstance(value, expected_python_type)
    
    def _validate_required(self, value: Any, config: Any, field: str) -> bool:
        """Validate required constraint"""
        if config is True:
            return value is not None
        return True
    
    def _validate_type(self, value: Any, config: str, field: str) -> bool:
        """Validate type constraint"""
        return self._check_type(value, config)
    
    def _validate_range(self, value: Any, config: Dict, field: str) -> bool:
        """Validate range constraint with comprehensive bounds checking"""
        if not isinstance(value, (int, float)):
            return True  # Skip range validation for non-numeric values
        
        # CRITICAL FIX #2: Enhanced bounds checking
        # Check for extreme values that could cause overflow
        if isinstance(value, float):
            if abs(value) > 1e308:  # Near float64 max
                logger.warning(f"Field {field}: value {value} exceeds safe float range")
                return False
            if value != value:  # NaN check
                logger.warning(f"Field {field}: NaN value detected")
                return False
            if value == float('inf') or value == float('-inf'):
                logger.warning(f"Field {field}: infinite value detected")
                return False
        
        if isinstance(value, int):
            if abs(value) > 2**63 - 1:  # 64-bit signed int max
                logger.warning(f"Field {field}: value {value} exceeds safe integer range")
                return False
        
        # Original range validation
        min_val = config.get('min')
        max_val = config.get('max')
        
        if min_val is not None and value < min_val:
            logger.warning(f"Field {field}: value {value} below minimum {min_val}")
            return False
        if max_val is not None and value > max_val:
            logger.warning(f"Field {field}: value {value} above maximum {max_val}")
            return False
        
        # Additional safety checks for specific fields
        if field in ['duration', 'execution_time_ms', 'processing_time_ms']:
            if value < 0:
                logger.warning(f"Field {field}: negative time value {value}")
                return False
            if value > 86400000:  # 24 hours in ms
                logger.warning(f"Field {field}: unrealistic time value {value}ms")
                return False
        
        if field in ['memory_spike_kb', 'memory_limit_mb']:
            if value < 0:
                logger.warning(f"Field {field}: negative memory value {value}")
                return False
            if value > 1024000:  # 1TB in KB/MB
                logger.warning(f"Field {field}: unrealistic memory value {value}")
                return False
        
        if field in ['cpu_utilization']:
            if value < 0 or value > 100:
                logger.warning(f"Field {field}: CPU utilization {value}% out of valid range [0-100]")
                return False
        
        return True
    
    def _validate_pattern(self, value: Any, config: str, field: str) -> bool:
        """Validate pattern constraint"""
        if not isinstance(value, str):
            return True
        
        try:
            return bool(re.match(config, value))
        except re.error:
            return False
    
    def _validate_enum(self, value: Any, config: List, field: str) -> bool:
        """Validate enum constraint"""
        return value in config
    
    def _validate_length(self, value: Any, config: Dict, field: str) -> bool:
        """Validate length constraint"""
        if not hasattr(value, '__len__'):
            return True
        
        length = len(value)
        min_len = config.get('min', 0)
        max_len = config.get('max', float('inf'))
        
        return min_len <= length <= max_len
    
    def _validate_custom(self, value: Any, config: Dict, field: str) -> bool:
        """Validate custom constraint"""
        # Implement custom validation logic based on config
        validation_type = config.get('type')
        
        if validation_type == 'email':
            return self._validate_email(value)
        elif validation_type == 'url':
            return self._validate_url(value)
        elif validation_type == 'uuid':
            return self._validate_uuid(value)
        
        return True
    
    def _validate_email(self, value: str) -> bool:
        """Validate email format"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, str(value)))
    
    def _validate_url(self, value: str) -> bool:
        """Validate URL format"""
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(url_pattern, str(value)))
    
    def _validate_uuid(self, value: str) -> bool:
        """Validate UUID format"""
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(uuid_pattern, str(value), re.IGNORECASE))
    
    def _hash_object(self, obj: Any) -> str:
        """Generate hash for object"""
        try:
            obj_str = json.dumps(obj, sort_keys=True, default=str)
            return hashlib.sha256(obj_str.encode()).hexdigest()[:16]
        except Exception:
            return hashlib.sha256(str(obj).encode()).hexdigest()[:16]


class SchemaVersionController:
    """Advanced schema version control system"""
    
    def __init__(self, config: SchemaConfig):
        self.config = config
        self._registry: Dict[str, SchemaVersion] = {}
        self._version_history: deque = deque(maxlen=1000)
        self.validator = SchemaValidator(config)
        self.current_version = "v1.0.0"
        
    def register_schema_version(self, version: str, schema_definition: Dict[str, Any], 
                               description: str = "", author: str = "system") -> str:
        """Register new schema version"""
        
        # Analyze compatibility with previous version
        compatibility = self._analyze_compatibility(schema_definition)
        
        # Generate migration script if needed
        migration_script = self._generate_migration_script(schema_definition) if self._registry else None
        
        # Create schema version
        schema_version = SchemaVersion(
            version=version,
            definition=schema_definition,
            timestamp=time.time(),
            description=description,
            author=author,
            compatibility_level=compatibility,
            migration_script=migration_script,
            validation_rules=self._extract_validation_rules(schema_definition)
        )
        
        # Store in registry
        self._registry[version] = schema_version
        
        # Add to history
        self._version_history.append({
            'version': version,
            'timestamp': time.time(),
            'action': 'register',
            'compatibility': compatibility.value
        })
        
        # Update current version if this is the latest
        if self._is_newer_version(version, self.current_version):
            self.current_version = version
        
        logger.info(f"Schema version {version} registered with compatibility: {compatibility.value}")
        
        return version
    
    def _analyze_compatibility(self, new_schema: Dict[str, Any]) -> CompatibilityLevel:
        """Analyze compatibility of new schema with current version"""
        
        if not self._registry:
            return CompatibilityLevel.FULLY_COMPATIBLE
        
        current_schema = self._registry[self.current_version].definition
        changes = self._detect_changes(current_schema, new_schema)
        
        has_breaking_changes = any(change.breaking for change in changes)
        has_backward_incompatible = any(
            change.change_type in [SchemaChangeType.REMOVE_FIELD, SchemaChangeType.MODIFY_TYPE]
            for change in changes
        )
        has_forward_incompatible = any(
            change.change_type == SchemaChangeType.ADD_FIELD and 
            change.new_value and change.new_value.get('required', False)
            for change in changes
        )
        
        if has_breaking_changes:
            return CompatibilityLevel.BREAKING_CHANGE
        elif has_backward_incompatible:
            return CompatibilityLevel.FORWARD_COMPATIBLE
        elif has_forward_incompatible:
            return CompatibilityLevel.BACKWARD_COMPATIBLE
        else:
            return CompatibilityLevel.FULLY_COMPATIBLE
    
    def _detect_changes(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> List[SchemaChange]:
        """Detect changes between schema versions"""
        changes = []
        
        old_properties = old_schema.get('properties', {})
        new_properties = new_schema.get('properties', {})
        
        # Detect added fields
        for field in new_properties:
            if field not in old_properties:
                changes.append(SchemaChange(
                    change_type=SchemaChangeType.ADD_FIELD,
                    field_path=field,
                    new_value=new_properties[field],
                    description=f"Added field '{field}'",
                    breaking=new_properties[field].get('required', False)
                ))
        
        # Detect removed fields
        for field in old_properties:
            if field not in new_properties:
                changes.append(SchemaChange(
                    change_type=SchemaChangeType.REMOVE_FIELD,
                    field_path=field,
                    old_value=old_properties[field],
                    description=f"Removed field '{field}'",
                    breaking=True
                ))
        
        # Detect modified fields
        for field in old_properties:
            if field in new_properties:
                old_field = old_properties[field]
                new_field = new_properties[field]
                
                if old_field != new_field:
                    field_changes = self._analyze_field_changes(field, old_field, new_field)
                    changes.extend(field_changes)
        
        return changes
    
    def _analyze_field_changes(self, field_name: str, old_field: Dict, new_field: Dict) -> List[SchemaChange]:
        """Analyze changes to a specific field"""
        changes = []
        
        # Type changes
        old_type = old_field.get('type')
        new_type = new_field.get('type')
        if old_type != new_type:
            changes.append(SchemaChange(
                change_type=SchemaChangeType.MODIFY_TYPE,
                field_path=field_name,
                old_value=old_type,
                new_value=new_type,
                description=f"Changed type of '{field_name}' from {old_type} to {new_type}",
                breaking=not self._is_type_compatible(old_type, new_type)
            ))
        
        # Required changes
        old_required = old_field.get('required', False)
        new_required = new_field.get('required', False)
        if old_required != new_required:
            if new_required and not old_required:
                changes.append(SchemaChange(
                    change_type=SchemaChangeType.ADD_VALIDATION,
                    field_path=field_name,
                    new_value={'required': True},
                    description=f"Made field '{field_name}' required",
                    breaking=True
                ))
        
        return changes
    
    def _is_type_compatible(self, old_type: str, new_type: str) -> bool:
        """Check if type change is compatible"""
        # Define compatible type transitions
        compatible_transitions = {
            'integer': ['number'],
            'number': [],  # number -> anything else is breaking
            'string': [],  # string -> anything else is breaking
            'boolean': [],
            'array': [],
            'object': []
        }
        
        if old_type == new_type:
            return True
        
        return new_type in compatible_transitions.get(old_type, [])
    
    def _generate_migration_script(self, new_schema: Dict[str, Any]) -> str:
        """Generate migration script for schema changes"""
        if not self._registry:
            return ""
        
        current_schema = self._registry[self.current_version].definition
        changes = self._detect_changes(current_schema, new_schema)
        
        script_lines = [
            "# Auto-generated schema migration script",
            f"# From version {self.current_version} to new version",
            "",
            "def migrate_data(data):",
            "    \"\"\"Migrate data from old schema to new schema\"\"\"",
            "    migrated_data = dict(data)",
            ""
        ]
        
        for change in changes:
            if change.change_type == SchemaChangeType.ADD_FIELD:
                default_value = change.new_value.get('default', 'None')
                script_lines.append(f"    # Add field '{change.field_path}'")
                script_lines.append(f"    if '{change.field_path}' not in migrated_data:")
                script_lines.append(f"        migrated_data['{change.field_path}'] = {default_value}")
                script_lines.append("")
            
            elif change.change_type == SchemaChangeType.REMOVE_FIELD:
                script_lines.append(f"    # Remove field '{change.field_path}'")
                script_lines.append(f"    migrated_data.pop('{change.field_path}', None)")
                script_lines.append("")
            
            elif change.change_type == SchemaChangeType.MODIFY_TYPE:
                script_lines.append(f"    # Convert field '{change.field_path}' from {change.old_value} to {change.new_value}")
                script_lines.append(f"    if '{change.field_path}' in migrated_data:")
                script_lines.append(f"        migrated_data['{change.field_path}'] = convert_type(migrated_data['{change.field_path}'], '{change.new_value}')")
                script_lines.append("")
        
        script_lines.extend([
            "    return migrated_data",
            "",
            "def convert_type(value, target_type):",
            "    \"\"\"Convert value to target type\"\"\"",
            "    if target_type == 'string':",
            "        return str(value)",
            "    elif target_type == 'number':",
            "        return float(value)",
            "    elif target_type == 'integer':",
            "        return int(value)",
            "    elif target_type == 'boolean':",
            "        return bool(value)",
            "    return value"
        ])
        
        return "\\n".join(script_lines)
    
    def _extract_validation_rules(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract validation rules from schema definition"""
        rules = {}
        
        properties = schema.get('properties', {})
        for field, field_schema in properties.items():
            field_rules = {}
            
            # Extract common validation rules
            if 'pattern' in field_schema:
                field_rules['pattern'] = field_schema['pattern']
            if 'minimum' in field_schema or 'maximum' in field_schema:
                field_rules['range'] = {
                    'min': field_schema.get('minimum'),
                    'max': field_schema.get('maximum')
                }
            if 'enum' in field_schema:
                field_rules['enum'] = field_schema['enum']
            if 'minLength' in field_schema or 'maxLength' in field_schema:
                field_rules['length'] = {
                    'min': field_schema.get('minLength'),
                    'max': field_schema.get('maxLength')
                }
            
            if field_rules:
                rules[field] = field_rules
        
        return rules
    
    def _is_newer_version(self, version1: str, version2: str) -> bool:
        """Check if version1 is newer than version2"""
        # Simple semantic version comparison
        try:
            v1_parts = [int(x) for x in version1.lstrip('v').split('.')]
            v2_parts = [int(x) for x in version2.lstrip('v').split('.')]
            
            # Pad to same length
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts += [0] * (max_len - len(v1_parts))
            v2_parts += [0] * (max_len - len(v2_parts))
            
            return v1_parts > v2_parts
        except (ValueError, AttributeError):
            return version1 > version2  # Fallback to string comparison
    
    def validate_schema_compatibility(self, old_version: str, new_version: str) -> bool:
        """Validate compatibility between two schema versions"""
        
        if old_version not in self._registry or new_version not in self._registry:
            return False
        
        old_schema = self._registry[old_version]
        new_schema = self._registry[new_version]
        
        # Check compatibility level
        if new_schema.compatibility_level == CompatibilityLevel.BREAKING_CHANGE:
            return False
        
        return True
    
    def apply_schema_migration(self, data: Dict[str, Any], source_version: str, 
                              target_version: str) -> Dict[str, Any]:
        """Apply schema migration to data"""
        
        if source_version == target_version:
            return data
        
        if target_version not in self._registry:
            raise ValueError(f"Target version {target_version} not found")
        
        target_schema = self._registry[target_version]
        
        if target_schema.migration_script:
            # Execute migration script
            try:
                # In a real implementation, this would safely execute the migration script
                # For now, we'll do basic field mapping
                migrated_data = self._apply_basic_migration(data, source_version, target_version)
                return migrated_data
            except Exception as e:
                logger.error(f"Migration failed: {str(e)}")
                return data
        
        return data
    
    def _apply_basic_migration(self, data: Dict[str, Any], source_version: str, 
                              target_version: str) -> Dict[str, Any]:
        """Apply basic field-level migrations"""
        
        if source_version not in self._registry or target_version not in self._registry:
            return data
        
        source_schema = self._registry[source_version].definition
        target_schema = self._registry[target_version].definition
        
        migrated_data = copy.deepcopy(data)
        changes = self._detect_changes(source_schema, target_schema)
        
        for change in changes:
            if change.change_type == SchemaChangeType.ADD_FIELD:
                # Add field with default value
                if change.field_path not in migrated_data:
                    default_value = change.new_value.get('default')
                    if default_value is not None:
                        migrated_data[change.field_path] = default_value
            
            elif change.change_type == SchemaChangeType.REMOVE_FIELD:
                # Remove field
                migrated_data.pop(change.field_path, None)
        
        return migrated_data
    
    def get_schema_version(self, version: str) -> Optional[SchemaVersion]:
        """Get schema version by version string"""
        return self._registry.get(version)
    
    def get_current_schema(self) -> Optional[SchemaVersion]:
        """Get current schema version"""
        return self._registry.get(self.current_version)
    
    def list_versions(self) -> List[str]:
        """List all registered schema versions"""
        return sorted(self._registry.keys(), key=lambda v: self._version_sort_key(v), reverse=True)
    
    def _version_sort_key(self, version: str) -> Tuple:
        """Generate sort key for version ordering"""
        try:
            parts = [int(x) for x in version.lstrip('v').split('.')]
            return tuple(parts)
        except (ValueError, AttributeError):
            return (0,)  # Fallback for non-semantic versions


class SchemaEvolutionManager:
    """Advanced schema evolution management system"""

    def __init__(self, config: Union[SchemaConfig, "Layer0Config"]):
        if isinstance(config, SchemaConfig):
            self.config = config
        else:
            self.config = getattr(config, "schema", SchemaConfig())
        self.version_controller = SchemaVersionController(self.config)
        self.validator = SchemaValidator(self.config)
        self.evolution_history: deque = deque(maxlen=1000)
        self.auto_evolution_enabled = getattr(self.config, 'auto_evolution', False)
        self.compatibility_threshold = getattr(self.config, 'compatibility_threshold', 0.8)
    
    async def validate_and_sanitize_input(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Validate and sanitize input data against current schema"""
        
        # Get current schema
        current_schema = self.version_controller.get_current_schema()
        if not current_schema:
            # No schema defined, return data as-is
            return event
        
        # Validate against current schema
        validation_result = self.validator.validate_data(event, current_schema.definition)
        
        # Handle validation results
        if not validation_result.valid:
            if self.auto_evolution_enabled:
                # Attempt automatic schema evolution
                evolved_schema = await self._evolve_schema_automatically(event, validation_result)
                if evolved_schema:
                    # Re-validate against evolved schema
                    validation_result = self.validator.validate_data(event, evolved_schema.definition)
            
            if not validation_result.valid:
                # Log validation errors
                logger.warning(f"Input validation failed: {validation_result.errors}")
                
                # Apply sanitization
                sanitized_data = self._sanitize_data(event, current_schema.definition)
                return sanitized_data
        
        return event
    
    async def _evolve_schema_automatically(self, data: Dict[str, Any], 
                                         validation_result: ValidationResult) -> Optional[SchemaVersion]:
        """Automatically evolve schema based on validation failures"""
        
        current_schema = self.version_controller.get_current_schema()
        if not current_schema:
            return None
        
        # Analyze validation failures to determine needed changes
        schema_changes = self._analyze_validation_failures(data, validation_result, current_schema.definition)
        
        if not schema_changes:
            return None
        
        # Create evolved schema definition
        evolved_definition = copy.deepcopy(current_schema.definition)
        
        for change in schema_changes:
            evolved_definition = self._apply_schema_change(evolved_definition, change)
        
        # Generate new version number
        new_version = self._generate_next_version(current_schema.version)
        
        # Register evolved schema
        self.version_controller.register_schema_version(
            version=new_version,
            schema_definition=evolved_definition,
            description="Auto-evolved based on validation failures",
            author="auto_evolution"
        )
        
        # Log evolution
        self.evolution_history.append({
            'timestamp': time.time(),
            'from_version': current_schema.version,
            'to_version': new_version,
            'changes': [change.__dict__ for change in schema_changes],
            'trigger': 'validation_failure'
        })
        
        logger.info(f"Schema automatically evolved from {current_schema.version} to {new_version}")
        
        return self.version_controller.get_schema_version(new_version)
    
    def _analyze_validation_failures(self, data: Dict[str, Any], validation_result: ValidationResult,
                                   schema: Dict[str, Any]) -> List[SchemaChange]:
        """Analyze validation failures to determine needed schema changes"""
        changes = []
        
        for error in validation_result.errors:
            # Parse error messages to determine changes
            if "is missing" in error:
                # Extract field name from error
                field_match = re.search(r"Required field '([^']+)' is missing", error)
                if field_match:
                    field_name = field_match.group(1)
                    if field_name in data:
                        # Field exists in data but not marked as required in schema
                        # Add field to schema
                        changes.append(SchemaChange(
                            change_type=SchemaChangeType.ADD_FIELD,
                            field_path=field_name,
                            new_value={
                                'type': self._infer_type(data[field_name]),
                                'required': False
                            },
                            description=f"Add field '{field_name}' found in data"
                        ))
            
            elif "Unexpected field" in error:
                # Extract field name from error
                field_match = re.search(r"Unexpected field '([^']+)' is not allowed", error)
                if field_match:
                    field_name = field_match.group(1)
                    if field_name in data:
                        # Add unexpected field to schema
                        changes.append(SchemaChange(
                            change_type=SchemaChangeType.ADD_FIELD,
                            field_path=field_name,
                            new_value={
                                'type': self._infer_type(data[field_name]),
                                'required': False
                            },
                            description=f"Add unexpected field '{field_name}'"
                        ))
            
            elif "has type" in error and "expected" in error:
                # Type mismatch - potentially relax type constraint
                field_match = re.search(r"Field '([^']+)' has type ([^,]+), expected ([^']+)", error)
                if field_match:
                    field_name = field_match.group(1)
                    actual_type = field_match.group(2).lower()
                    expected_type = field_match.group(3)
                    
                    # Consider union types or more permissive types
                    new_type = self._resolve_type_conflict(actual_type, expected_type)
                    if new_type:
                        changes.append(SchemaChange(
                            change_type=SchemaChangeType.MODIFY_TYPE,
                            field_path=field_name,
                            old_value=expected_type,
                            new_value=new_type,
                            description=f"Relax type constraint for '{field_name}'"
                        ))
        
        return changes
    
    def _infer_type(self, value: Any) -> str:
        """Infer JSON schema type from Python value"""
        if isinstance(value, bool):
            return 'boolean'
        elif isinstance(value, int):
            return 'integer'
        elif isinstance(value, float):
            return 'number'
        elif isinstance(value, str):
            return 'string'
        elif isinstance(value, list):
            return 'array'
        elif isinstance(value, dict):
            return 'object'
        elif value is None:
            return 'null'
        else:
            return 'string'  # Default fallback
    
    def _resolve_type_conflict(self, actual_type: str, expected_type: str) -> Optional[str]:
        """Resolve type conflicts by finding compatible type"""
        
        # Type compatibility matrix
        compatibility_map = {
            ('int', 'number'): 'number',
            ('float', 'integer'): 'number',
            ('str', 'number'): 'string',  # Be more permissive
            ('bool', 'string'): 'string'
        }
        
        # Normalize type names
        type_mapping = {
            'int': 'integer',
            'float': 'number',
            'str': 'string',
            'bool': 'boolean',
            'list': 'array',
            'dict': 'object'
        }
        
        actual_normalized = type_mapping.get(actual_type, actual_type)
        
        # Check direct compatibility
        return compatibility_map.get((actual_type, expected_type))
    
    def _apply_schema_change(self, schema: Dict[str, Any], change: SchemaChange) -> Dict[str, Any]:
        """Apply schema change to schema definition"""
        
        if change.change_type == SchemaChangeType.ADD_FIELD:
            if 'properties' not in schema:
                schema['properties'] = {}
            schema['properties'][change.field_path] = change.new_value
        
        elif change.change_type == SchemaChangeType.REMOVE_FIELD:
            if 'properties' in schema and change.field_path in schema['properties']:
                del schema['properties'][change.field_path]
        
        elif change.change_type == SchemaChangeType.MODIFY_TYPE:
            if 'properties' in schema and change.field_path in schema['properties']:
                schema['properties'][change.field_path]['type'] = change.new_value
        
        return schema
    
    def _generate_next_version(self, current_version: str) -> str:
        """Generate next version number"""
        try:
            # Parse semantic version
            version_parts = current_version.lstrip('v').split('.')
            major, minor, patch = [int(x) for x in version_parts[:3]]
            
            # Increment patch version for auto-evolution
            patch += 1
            
            return f"v{major}.{minor}.{patch}"
            
        except (ValueError, IndexError):
            # Fallback for non-semantic versions
            import time
            return f"auto-{int(time.time())}"
    
    def _sanitize_data(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize data to conform to schema"""
        
        sanitized = {}
        properties = schema.get('properties', {})
        additional_properties = schema.get('additionalProperties', True)
        
        # Include known properties
        for field, field_schema in properties.items():
            if field in data:
                value = data[field]
                # Apply basic type coercion
                sanitized[field] = self._coerce_type(value, field_schema.get('type'))
            elif field_schema.get('required'):
                # Add default value for required fields
                default_value = field_schema.get('default')
                if default_value is not None:
                    sanitized[field] = default_value
        
        # Include additional properties if allowed
        if additional_properties:
            for field, value in data.items():
                if field not in properties:
                    sanitized[field] = value
        
        return sanitized
    
    def _coerce_type(self, value: Any, expected_type: Optional[str]) -> Any:
        """Coerce value to expected type"""
        
        if expected_type is None:
            return value
        
        try:
            if expected_type == 'string':
                return str(value)
            elif expected_type == 'number':
                return float(value) if not isinstance(value, bool) else value
            elif expected_type == 'integer':
                return int(value) if not isinstance(value, bool) else value
            elif expected_type == 'boolean':
                if isinstance(value, str):
                    return value.lower() in ['true', '1', 'yes', 'on']
                return bool(value)
            elif expected_type == 'array':
                return list(value) if hasattr(value, '__iter__') and not isinstance(value, (str, dict)) else [value]
            elif expected_type == 'object':
                return dict(value) if isinstance(value, dict) else {'value': value}
        except (ValueError, TypeError):
            pass
        
        return value
    
    def evolve_schema(self, new_fields: Dict[str, Any], description: str = "") -> str:
        """Manually evolve schema with new fields"""
        
        current_schema = self.version_controller.get_current_schema()
        if not current_schema:
            # Create initial schema
            initial_schema = {
                'type': 'object',
                'properties': new_fields,
                'additionalProperties': True
            }
            return self.version_controller.register_schema_version(
                version="v1.0.0",
                schema_definition=initial_schema,
                description=description or "Initial schema version"
            )
        
        # Evolve current schema
        evolved_definition = copy.deepcopy(current_schema.definition)
        
        if 'properties' not in evolved_definition:
            evolved_definition['properties'] = {}
        
        # Add new fields
        evolved_definition['properties'].update(new_fields)
        
        # Generate new version
        new_version = self._generate_next_version(current_schema.version)
        
        # Register evolved schema
        return self.version_controller.register_schema_version(
            version=new_version,
            schema_definition=evolved_definition,
            description=description or f"Schema evolution with {len(new_fields)} new fields"
        )
    
    def maintain_backward_compatibility(self, old_schema: Dict[str, Any], 
                                      new_schema: Dict[str, Any]) -> bool:
        """Check if new schema maintains backward compatibility"""
        
        changes = self.version_controller._detect_changes(old_schema, new_schema)
        
        # Check for breaking changes
        breaking_changes = [change for change in changes if change.breaking]
        
        return len(breaking_changes) == 0
    
    def generate_migration_scripts(self, schema_changes: Dict[str, Any]) -> str:
        """Generate migration scripts for schema changes"""
        
        # This would generate more sophisticated migration scripts
        # For now, return a basic template
        
        return f'''
# Migration script for schema changes
# Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}

def migrate_data(data, from_version, to_version):
    \"\"\"
    Migrate data between schema versions
    
    Args:
        data: Input data dictionary
        from_version: Source schema version
        to_version: Target schema version
    
    Returns:
        Migrated data dictionary
    \"\"\"
    
    migrated_data = dict(data)
    
    # Apply schema changes
    {json.dumps(schema_changes, indent=4)}
    
    return migrated_data
'''
    
    def get_evolution_summary(self) -> Dict[str, Any]:
        """Get summary of schema evolution"""
        
        versions = self.version_controller.list_versions()
        current_schema = self.version_controller.get_current_schema()
        
        return {
            'total_versions': len(versions),
            'current_version': current_schema.version if current_schema else None,
            'auto_evolution_enabled': self.auto_evolution_enabled,
            'recent_evolutions': list(self.evolution_history)[-10:],  # Last 10 evolutions
            'compatibility_stats': {
                level.value: sum(1 for v in versions 
                               if self.version_controller.get_schema_version(v) and 
                               self.version_controller.get_schema_version(v).compatibility_level == level)
                for level in CompatibilityLevel
            }
        }