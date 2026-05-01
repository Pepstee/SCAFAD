#!/usr/bin/env python3
"""
SCAFAD Layer 1: Field Mapper Utility
====================================

The Field Mapper handles schema field mapping and transformation for Layer 1's
behavioral intake zone. It provides:

- Schema field mapping and transformation
- Field type conversion and validation
- Schema evolution support
- Field mapping rule management
- Performance-optimized mapping
- Mapping validation and testing

Author: SCAFAD Research Team
Institution: Birmingham Newman University
License: MIT
Version: 1.0.0
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Union, Tuple, Set, Callable
from enum import Enum, auto
from datetime import datetime, timezone
import copy
from collections import defaultdict

# =============================================================================
# Field Mapper Data Models
# =============================================================================

class FieldType(Enum):
    """Field data types"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    JSON_OBJECT = "json_object"
    JSON_ARRAY = "json_array"
    BINARY = "binary"
    ENUM = "enum"
    CUSTOM = "custom"

class MappingStrategy(Enum):
    """Field mapping strategies"""
    DIRECT = "direct"               # Direct field copy
    TRANSFORM = "transform"         # Transform field value
    CALCULATE = "calculate"         # Calculate from other fields
    CONDITIONAL = "conditional"     # Conditional mapping
    AGGREGATE = "aggregate"         # Aggregate multiple fields
    SPLIT = "split"                 # Split field into multiple
    MERGE = "merge"                 # Merge multiple fields
    DEFAULT = "default"             # Use default value

class TransformationType(Enum):
    """Field transformation types"""
    TYPE_CONVERSION = "type_conversion"
    FORMAT_CHANGE = "format_change"
    VALUE_MAPPING = "value_mapping"
    CALCULATION = "calculation"
    VALIDATION = "validation"
    SANITIZATION = "sanitization"
    NORMALIZATION = "normalization"

@dataclass
class FieldMapping:
    """Field mapping definition"""
    source_field: str
    target_field: str
    strategy: MappingStrategy
    transformation: Optional[TransformationType] = None
    transform_function: Optional[Callable] = None
    default_value: Optional[Any] = None
    required: bool = False
    validation_rules: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class SchemaMapping:
    """Schema mapping definition"""
    mapping_id: str
    source_schema: str
    target_schema: str
    version: str
    field_mappings: List[FieldMapping]
    validation_rules: Dict[str, Any]
    performance_mode: bool = False
    preserve_unknown_fields: bool = False
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class MappingResult:
    """Result of field mapping operation"""
    source_data: Dict[str, Any]
    mapped_data: Dict[str, Any]
    mapping_applied: Dict[str, Dict[str, Any]]
    fields_mapped: List[str]
    fields_failed: List[str]
    validation_errors: List[str]
    mapping_time_ms: float
    schema_mapping_used: str
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class FieldValidation:
    """Field validation result"""
    field_name: str
    is_valid: bool
    validation_errors: List[str]
    warnings: List[str]
    original_value: Any
    transformed_value: Any
    validation_time_ms: float
    metadata: Optional[Dict[str, Any]] = None

# =============================================================================
# Field Mapper Core Class
# =============================================================================

class FieldMapper:
    """
    Field Mapper for schema field mapping and transformation
    
    The Field Mapper provides comprehensive field mapping capabilities
    with support for schema evolution and complex transformations.
    """
    
    def __init__(self, config: Any = None):
        """Initialize the Field Mapper"""
        self.config = config
        self.logger = logging.getLogger("SCAFAD.Layer1.FieldMapper")
        
        # Schema mappings
        self.schema_mappings: Dict[str, SchemaMapping] = {}
        self.active_mapping: Optional[str] = None
        
        # Built-in transformation functions
        self.transform_functions: Dict[str, Callable] = {}
        
        # Field type validators
        self.type_validators: Dict[FieldType, Callable] = {}
        
        # Performance tracking
        self.mapper_stats = {
            'total_mappings': 0,
            'total_fields_mapped': 0,
            'total_validation_errors': 0,
            'average_mapping_time_ms': 0.0
        }
        
        # Initialize built-in functions and validators
        self._initialize_transform_functions()
        self._initialize_type_validators()
        self._initialize_default_mappings()
        
        self.logger.info("Field Mapper initialized")
    
    def register_schema_mapping(self, mapping: SchemaMapping) -> bool:
        """
        Register a schema mapping
        
        Args:
            mapping: SchemaMapping to register
            
        Returns:
            bool: True if registration successful
        """
        try:
            # Validate mapping
            if not self._validate_schema_mapping(mapping):
                self.logger.error(f"Schema mapping validation failed for {mapping.mapping_id}")
                return False
            
            # Register mapping
            self.schema_mappings[mapping.mapping_id] = mapping
            
            # Set as active if first mapping
            if not self.active_mapping:
                self.active_mapping = mapping.mapping_id
            
            self.logger.info(f"Schema mapping {mapping.mapping_id} registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register schema mapping {mapping.mapping_id}: {str(e)}")
            return False
    
    def set_active_mapping(self, mapping_id: str) -> bool:
        """
        Set active schema mapping
        
        Args:
            mapping_id: Mapping ID to activate
            
        Returns:
            bool: True if activation successful
        """
        if mapping_id not in self.schema_mappings:
            self.logger.error(f"Schema mapping {mapping_id} not found")
            return False
        
        self.active_mapping = mapping_id
        self.logger.info(f"Active mapping set to {mapping_id}")
        return True
    
    def add_transform_function(self, name: str, function: Callable):
        """
        Add a custom transformation function
        
        Args:
            name: Function name
            function: Transformation function
        """
        try:
            if not callable(function):
                raise ValueError("Function must be callable")
            
            self.transform_functions[name] = function
            self.logger.info(f"Transform function '{name}' added successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to add transform function '{name}': {str(e)}")
    
    def map_fields(self, source_data: Dict[str, Any], mapping_id: Optional[str] = None,
                   validate_output: bool = True) -> MappingResult:
        """
        Map fields from source schema to target schema
        
        Args:
            source_data: Source data to map
            mapping_id: Mapping ID to use (uses active mapping if None)
            validate_output: Whether to validate output data
            
        Returns:
            MappingResult with mapping details
        """
        import time
        start_time = time.time()
        
        try:
            # Get mapping
            if mapping_id is None:
                mapping_id = self.active_mapping
            
            if not mapping_id or mapping_id not in self.schema_mappings:
                raise ValueError(f"No valid mapping specified: {mapping_id}")
            
            schema_mapping = self.schema_mappings[mapping_id]
            
            # Create mapping result
            result = MappingResult(
                source_data=copy.deepcopy(source_data),
                mapped_data={},
                mapping_applied={},
                fields_mapped=[],
                fields_failed=[],
                validation_errors=[],
                mapping_time_ms=0.0,
                schema_mapping_used=mapping_id,
                metadata={}
            )
            
            # Apply field mappings
            for field_mapping in schema_mapping.field_mappings:
                try:
                    mapped_value = self._apply_field_mapping(
                        field_mapping, source_data, schema_mapping
                    )
                    
                    if mapped_value is not None:
                        result.mapped_data[field_mapping.target_field] = mapped_value
                        result.fields_mapped.append(field_mapping.target_field)
                        
                        result.mapping_applied[field_mapping.target_field] = {
                            'source_field': field_mapping.source_field,
                            'strategy': field_mapping.strategy.value,
                            'transformation': field_mapping.transformation.value if field_mapping.transformation else None
                        }
                    else:
                        result.fields_failed.append(field_mapping.target_field)
                        
                except Exception as e:
                    self.logger.warning(f"Field mapping failed for {field_mapping.target_field}: {str(e)}")
                    result.fields_failed.append(field_mapping.target_field)
            
            # Handle unknown fields if configured
            if schema_mapping.preserve_unknown_fields:
                self._preserve_unknown_fields(source_data, result.mapped_data, schema_mapping)
            
            # Validate output if requested
            if validate_output:
                validation_errors = self._validate_mapped_data(result.mapped_data, schema_mapping)
                result.validation_errors.extend(validation_errors)
            
            # Calculate mapping time
            mapping_time = (time.time() - start_time) * 1000
            result.mapping_time_ms = mapping_time
            
            # Update statistics
            self._update_mapper_stats(result, mapping_time)
            
            self.logger.debug(f"Field mapping completed in {mapping_time:.2f}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"Field mapping failed: {str(e)}")
            raise
    
    def validate_field(self, field_name: str, field_value: Any, 
                      field_type: FieldType, validation_rules: Optional[Dict[str, Any]] = None) -> FieldValidation:
        """
        Validate a single field
        
        Args:
            field_name: Name of the field
            field_value: Value to validate
            field_type: Expected field type
            validation_rules: Optional validation rules
            
        Returns:
            FieldValidation with validation details
        """
        import time
        start_time = time.time()
        
        try:
            # Create validation result
            validation = FieldValidation(
                field_name=field_name,
                is_valid=True,
                validation_errors=[],
                warnings=[],
                original_value=field_value,
                transformed_value=field_value,
                validation_time_ms=0.0,
                metadata={}
            )
            
            # Type validation
            if not self._validate_field_type(field_value, field_type):
                validation.is_valid = False
                validation.validation_errors.append(f"Field type mismatch: expected {field_type.value}")
            
            # Custom validation rules
            if validation_rules:
                custom_errors = self._apply_custom_validation(field_value, validation_rules)
                validation.validation_errors.extend(custom_errors)
                validation.is_valid = validation.is_valid and len(custom_errors) == 0
            
            # Calculate validation time
            validation_time = (time.time() - start_time) * 1000
            validation.validation_time_ms = validation_time
            
            return validation
            
        except Exception as e:
            self.logger.error(f"Field validation failed: {str(e)}")
            raise
    
    def get_schema_mappings(self) -> List[str]:
        """Get list of registered mapping IDs"""
        return list(self.schema_mappings.keys())
    
    def get_active_mapping(self) -> Optional[SchemaMapping]:
        """Get currently active schema mapping"""
        if self.active_mapping:
            return self.schema_mappings.get(self.active_mapping)
        return None
    
    def get_transform_functions(self) -> List[str]:
        """Get list of available transform function names"""
        return list(self.transform_functions.keys())
    
    def get_mapper_stats(self) -> Dict[str, Any]:
        """Get mapper statistics"""
        return self.mapper_stats.copy()
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _initialize_transform_functions(self):
        """Initialize built-in transformation functions"""
        # Type conversion functions
        self.transform_functions['to_string'] = str
        self.transform_functions['to_int'] = int
        self.transform_functions['to_float'] = float
        self.transform_functions['to_bool'] = bool
        
        # String transformation functions
        self.transform_functions['to_lowercase'] = lambda x: str(x).lower()
        self.transform_functions['to_uppercase'] = lambda x: str(x).upper()
        self.transform_functions['trim'] = lambda x: str(x).strip()
        self.transform_functions['capitalize'] = lambda x: str(x).capitalize()
        
        # Numeric transformation functions
        self.transform_functions['round'] = lambda x: round(float(x))
        self.transform_functions['abs'] = lambda x: abs(float(x))
        self.transform_functions['sqrt'] = lambda x: float(x) ** 0.5
        
        # Timestamp transformation functions
        self.transform_functions['to_timestamp'] = self._to_timestamp
        self.transform_functions['from_timestamp'] = self._from_timestamp
        self.transform_functions['format_date'] = self._format_date
        
        # JSON transformation functions
        self.transform_functions['to_json'] = json.dumps
        self.transform_functions['from_json'] = json.loads
        
        # Custom transformation functions
        self.transform_functions['hash_value'] = self._hash_value
        self.transform_functions['anonymize'] = self._anonymize_value
        self.transform_functions['normalize'] = self._normalize_value
    
    def _initialize_type_validators(self):
        """Initialize field type validators"""
        self.type_validators[FieldType.STRING] = lambda x: isinstance(x, str)
        self.type_validators[FieldType.INTEGER] = lambda x: isinstance(x, int) and not isinstance(x, bool)
        self.type_validators[FieldType.FLOAT] = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)
        self.type_validators[FieldType.BOOLEAN] = lambda x: isinstance(x, bool)
        self.type_validators[FieldType.TIMESTAMP] = self._is_valid_timestamp
        self.type_validators[FieldType.JSON_OBJECT] = lambda x: isinstance(x, dict)
        self.type_validators[FieldType.JSON_ARRAY] = lambda x: isinstance(x, list)
        self.type_validators[FieldType.BINARY] = lambda x: isinstance(x, bytes)
        self.type_validators[FieldType.ENUM] = lambda x: isinstance(x, str)
        self.type_validators[FieldType.CUSTOM] = lambda x: True
    
    def _initialize_default_mappings(self):
        """Initialize default schema mappings"""
        # v2.0 to v2.1 mapping
        v2_0_to_v2_1_mapping = SchemaMapping(
            mapping_id="v2.0_to_v2.1",
            source_schema="v2.0",
            target_schema="v2.1",
            version="1.0",
            field_mappings=[
                FieldMapping(
                    source_field="id",
                    target_field="record_id",
                    strategy=MappingStrategy.DIRECT,
                    required=True
                ),
                FieldMapping(
                    source_field="timestamp",
                    target_field="timestamp",
                    strategy=MappingStrategy.DIRECT,
                    required=True
                ),
                FieldMapping(
                    source_field="function",
                    target_field="function_name",
                    strategy=MappingStrategy.DIRECT,
                    required=True
                ),
                FieldMapping(
                    source_field="phase",
                    target_field="execution_phase",
                    strategy=MappingStrategy.DIRECT,
                    required=True
                ),
                FieldMapping(
                    source_field="anomaly",
                    target_field="anomaly_type",
                    strategy=MappingStrategy.DIRECT,
                    required=True
                ),
                FieldMapping(
                    source_field="data",
                    target_field="telemetry_data",
                    strategy=MappingStrategy.DIRECT,
                    required=True
                ),
                FieldMapping(
                    source_field="provenance",
                    target_field="provenance_chain",
                    strategy=MappingStrategy.DIRECT,
                    required=False
                ),
                FieldMapping(
                    source_field="context",
                    target_field="context_metadata",
                    strategy=MappingStrategy.DIRECT,
                    required=False
                ),
                FieldMapping(
                    source_field="schema_version",
                    target_field="schema_version",
                    strategy=MappingStrategy.DIRECT,
                    default_value="v2.1",
                    required=False
                )
            ],
            validation_rules={
                'required_fields': ['record_id', 'timestamp', 'function_name', 'execution_phase', 'anomaly_type', 'telemetry_data'],
                'field_types': {
                    'record_id': FieldType.STRING,
                    'timestamp': FieldType.TIMESTAMP,
                    'function_name': FieldType.STRING,
                    'execution_phase': FieldType.ENUM,
                    'anomaly_type': FieldType.STRING,
                    'telemetry_data': FieldType.JSON_OBJECT
                }
            },
            performance_mode=False,
            preserve_unknown_fields=True
        )
        
        # Register default mapping
        self.register_schema_mapping(v2_0_to_v2_1_mapping)
    
    def _validate_schema_mapping(self, mapping: SchemaMapping) -> bool:
        """Validate schema mapping"""
        try:
            if not mapping.mapping_id:
                return False
            
            if not mapping.source_schema:
                return False
            
            if not mapping.target_schema:
                return False
            
            if not mapping.field_mappings:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _apply_field_mapping(self, field_mapping: FieldMapping, source_data: Dict[str, Any],
                            schema_mapping: SchemaMapping) -> Any:
        """Apply individual field mapping"""
        try:
            # Get source value
            source_value = source_data.get(field_mapping.source_field)
            
            # Handle missing required fields
            if source_value is None:
                if field_mapping.required:
                    if field_mapping.default_value is not None:
                        return field_mapping.default_value
                    else:
                        raise ValueError(f"Required field {field_mapping.source_field} is missing")
                else:
                    return None
            
            # Apply mapping strategy
            if field_mapping.strategy == MappingStrategy.DIRECT:
                mapped_value = source_value
            elif field_mapping.strategy == MappingStrategy.TRANSFORM:
                mapped_value = self._apply_transformation(source_value, field_mapping)
            elif field_mapping.strategy == MappingStrategy.CALCULATE:
                mapped_value = self._apply_calculation(field_mapping, source_data)
            elif field_mapping.strategy == MappingStrategy.CONDITIONAL:
                mapped_value = self._apply_conditional_mapping(field_mapping, source_data)
            elif field_mapping.strategy == MappingStrategy.AGGREGATE:
                mapped_value = self._apply_aggregation(field_mapping, source_data)
            elif field_mapping.strategy == MappingStrategy.SPLIT:
                mapped_value = self._apply_split_mapping(field_mapping, source_value)
            elif field_mapping.strategy == MappingStrategy.MERGE:
                mapped_value = self._apply_merge_mapping(field_mapping, source_data)
            elif field_mapping.strategy == MappingStrategy.DEFAULT:
                mapped_value = field_mapping.default_value
            else:
                mapped_value = source_value
            
            # Apply transformation if specified
            if field_mapping.transformation and field_mapping.transform_function:
                mapped_value = self._apply_transformation(mapped_value, field_mapping)
            
            return mapped_value
            
        except Exception as e:
            self.logger.error(f"Field mapping failed for {field_mapping.target_field}: {str(e)}")
            raise
    
    def _apply_transformation(self, value: Any, field_mapping: FieldMapping) -> Any:
        """Apply transformation to field value"""
        try:
            if field_mapping.transform_function:
                if callable(field_mapping.transform_function):
                    return field_mapping.transform_function(value)
                elif isinstance(field_mapping.transform_function, str):
                    # Look up transform function by name
                    transform_func = self.transform_functions.get(field_mapping.transform_function)
                    if transform_func:
                        return transform_func(value)
                    else:
                        raise ValueError(f"Transform function '{field_mapping.transform_function}' not found")
            
            return value
            
        except Exception as e:
            self.logger.error(f"Transformation failed: {str(e)}")
            return value
    
    def _apply_calculation(self, field_mapping: FieldMapping, source_data: Dict[str, Any]) -> Any:
        """Apply calculation mapping"""
        # Placeholder for calculation logic
        # In a real implementation, this would evaluate mathematical expressions
        return field_mapping.default_value
    
    def _apply_conditional_mapping(self, field_mapping: FieldMapping, source_data: Dict[str, Any]) -> Any:
        """Apply conditional mapping"""
        # Placeholder for conditional logic
        # In a real implementation, this would evaluate conditions
        return field_mapping.default_value
    
    def _apply_aggregation(self, field_mapping: FieldMapping, source_data: Dict[str, Any]) -> Any:
        """Apply aggregation mapping"""
        # Placeholder for aggregation logic
        # In a real implementation, this would aggregate multiple fields
        return field_mapping.default_value
    
    def _apply_split_mapping(self, field_mapping: FieldMapping, source_value: Any) -> Any:
        """Apply split mapping"""
        # Placeholder for split logic
        # In a real implementation, this would split field values
        return source_value
    
    def _apply_merge_mapping(self, field_mapping: FieldMapping, source_data: Dict[str, Any]) -> Any:
        """Apply merge mapping"""
        # Placeholder for merge logic
        # In a real implementation, this would merge multiple fields
        return field_mapping.default_value
    
    def _preserve_unknown_fields(self, source_data: Dict[str, Any], mapped_data: Dict[str, Any],
                                schema_mapping: SchemaMapping):
        """Preserve unknown fields from source data"""
        mapped_field_names = {fm.target_field for fm in schema_mapping.field_mappings}
        
        for field_name, field_value in source_data.items():
            if field_name not in mapped_field_names:
                mapped_data[field_name] = field_value
    
    def _validate_mapped_data(self, mapped_data: Dict[str, Any], 
                             schema_mapping: SchemaMapping) -> List[str]:
        """Validate mapped data against schema rules"""
        validation_errors = []
        
        # Check required fields
        required_fields = schema_mapping.validation_rules.get('required_fields', [])
        for field_name in required_fields:
            if field_name not in mapped_data or mapped_data[field_name] is None:
                validation_errors.append(f"Required field '{field_name}' is missing")
        
        # Check field types
        field_types = schema_mapping.validation_rules.get('field_types', {})
        for field_name, expected_type in field_types.items():
            if field_name in mapped_data and mapped_data[field_name] is not None:
                if not self._validate_field_type(mapped_data[field_name], expected_type):
                    validation_errors.append(
                        f"Field '{field_name}' has invalid type: expected {expected_type.value}"
                    )
        
        return validation_errors
    
    def _validate_field_type(self, value: Any, field_type: FieldType) -> bool:
        """Validate field type"""
        validator = self.type_validators.get(field_type)
        if validator:
            try:
                return validator(value)
            except Exception:
                return False
        return True
    
    def _apply_custom_validation(self, value: Any, validation_rules: Dict[str, Any]) -> List[str]:
        """Apply custom validation rules"""
        validation_errors = []
        
        # Check minimum/maximum values
        if 'min_value' in validation_rules:
            try:
                if float(value) < validation_rules['min_value']:
                    validation_errors.append(f"Value {value} is below minimum {validation_rules['min_value']}")
            except (ValueError, TypeError):
                pass
        
        if 'max_value' in validation_rules:
            try:
                if float(value) > validation_rules['max_value']:
                    validation_errors.append(f"Value {value} is above maximum {validation_rules['max_value']}")
            except (ValueError, TypeError):
                pass
        
        # Check string length
        if 'min_length' in validation_rules and isinstance(value, str):
            if len(value) < validation_rules['min_length']:
                validation_errors.append(f"String length {len(value)} is below minimum {validation_rules['min_length']}")
        
        if 'max_length' in validation_rules and isinstance(value, str):
            if len(value) > validation_rules['max_length']:
                validation_errors.append(f"String length {len(value)} is above maximum {validation_rules['max_length']}")
        
        # Check pattern matching
        if 'pattern' in validation_rules and isinstance(value, str):
            try:
                if not re.match(validation_rules['pattern'], value):
                    validation_errors.append(f"Value '{value}' does not match pattern '{validation_rules['pattern']}'")
            except re.error:
                pass
        
        return validation_errors
    
    def _update_mapper_stats(self, result: MappingResult, mapping_time: float):
        """Update mapper statistics"""
        self.mapper_stats['total_mappings'] += 1
        self.mapper_stats['total_fields_mapped'] += len(result.fields_mapped)
        self.mapper_stats['total_validation_errors'] += len(result.validation_errors)
        
        # Update average mapping time
        current_avg = self.mapper_stats['average_mapping_time_ms']
        total_mappings = self.mapper_stats['total_mappings']
        
        if total_mappings > 0:
            self.mapper_stats['average_mapping_time_ms'] = (
                (current_avg * (total_mappings - 1) + mapping_time) / total_mappings
            )
    
    # =========================================================================
    # Built-in Transformation Functions
    # =========================================================================
    
    def _to_timestamp(self, value: Any) -> float:
        """Convert value to timestamp"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                # Try to parse ISO format
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt.timestamp()
            elif isinstance(value, datetime):
                return value.timestamp()
            else:
                return time.time()
        except Exception:
            return time.time()
    
    def _from_timestamp(self, value: Any) -> str:
        """Convert timestamp to ISO string"""
        try:
            if isinstance(value, (int, float)):
                dt = datetime.fromtimestamp(value, tz=timezone.utc)
                return dt.isoformat()
            else:
                return str(value)
        except Exception:
            return str(value)
    
    def _format_date(self, value: Any, format_str: str = "%Y-%m-%d") -> str:
        """Format date value"""
        try:
            if isinstance(value, (int, float)):
                dt = datetime.fromtimestamp(value, tz=timezone.utc)
            elif isinstance(value, str):
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif isinstance(value, datetime):
                dt = value
            else:
                return str(value)
            
            return dt.strftime(format_str)
        except Exception:
            return str(value)
    
    def _hash_value(self, value: Any) -> str:
        """Hash a value"""
        try:
            import hashlib
            return hashlib.md5(str(value).encode()).hexdigest()[:16]
        except Exception:
            return str(value)
    
    def _anonymize_value(self, value: Any) -> str:
        """Anonymize a value"""
        try:
            if isinstance(value, str):
                if len(value) <= 2:
                    return '*' * len(value)
                else:
                    return value[:2] + '*' * (len(value) - 2)
            else:
                return '***'
        except Exception:
            return '***'
    
    def _normalize_value(self, value: Any) -> Any:
        """Normalize a value"""
        try:
            if isinstance(value, str):
                return value.strip().lower()
            elif isinstance(value, (int, float)):
                return float(value)
            else:
                return value
        except Exception:
            return value
    
    def _is_valid_timestamp(self, value: Any) -> bool:
        """Check if value is a valid timestamp"""
        try:
            if isinstance(value, (int, float)):
                # Unix timestamp
                if value < 0 or value > 9999999999999:
                    return False
                return True
            elif isinstance(value, str):
                # ISO format timestamp
                datetime.fromisoformat(value.replace('Z', '+00:00'))
                return True
            elif isinstance(value, datetime):
                return True
            else:
                return False
        except (ValueError, TypeError):
            return False

# =============================================================================
# Field Mapper Factory Functions
# =============================================================================

def create_field_mapper(config: Optional[Any] = None) -> FieldMapper:
    """Create a field mapper with default configuration"""
    return FieldMapper(config)

if __name__ == "__main__":
    # Example usage
    mapper = create_field_mapper()
    
    # Test data (v2.0 format)
    test_data_v2_0 = {
        'id': 'test123',
        'timestamp': 1640995200.0,
        'function': 'test_function',
        'phase': 'invocation',
        'anomaly': 'performance',
        'data': {'cpu_usage': 85.5},
        'provenance': {'source': 'test'},
        'context': {'environment': 'development'}
    }
    
    # Map to v2.1 format
    result = mapper.map_fields(test_data_v2_0, mapping_id="v2.0_to_v2.1")
    print(f"Mapping completed in {result.mapping_time_ms:.2f}ms")
    print(f"Fields mapped: {result.fields_mapped}")
    print(f"Fields failed: {result.fields_failed}")
    
    if result.validation_errors:
        print(f"Validation errors: {result.validation_errors}")
    
    # Show mapped data
    print("\nMapped data:")
    for field_name, value in result.mapped_data.items():
        print(f"  {field_name}: {value}")
    
    # Test field validation
    validation = mapper.validate_field(
        field_name="record_id",
        field_value="test123",
        field_type=FieldType.STRING,
        validation_rules={'min_length': 5, 'max_length': 20}
    )
    print(f"\nField validation: {validation.is_valid}")
    if validation.validation_errors:
        print(f"Validation errors: {validation.validation_errors}")
    
    # Get mapper stats
    stats = mapper.get_mapper_stats()
    print(f"\nMapper stats: {stats}")

# Backward-compat alias
FieldMappingEngine = FieldMapper
