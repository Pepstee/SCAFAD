#!/usr/bin/env python3
"""
SCAFAD Layer 1: Validators Utility
==================================

The Validators utility provides input validation utilities for telemetry records
and other data structures in Layer 1's behavioral intake zone. It supports:

- Telemetry record validation
- Field type validation
- Range and constraint validation
- Custom validation rules
- Validation result reporting
- Performance-optimized validation

Author: SCAFAD Research Team
Institution: Birmingham Newman University
License: MIT
Version: 1.0.0
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Tuple, Callable, Set
from enum import Enum, auto
from datetime import datetime, timezone
import ipaddress
import uuid
import email_validator
from urllib.parse import urlparse

# =============================================================================
# Validators Data Models
# =============================================================================

class ValidationSeverity(Enum):
    """Validation error severity levels"""
    INFO = "info"           # Informational, non-blocking
    WARNING = "warning"     # Warning, may cause issues
    ERROR = "error"         # Error, validation failed
    CRITICAL = "critical"   # Critical error, must be fixed

class FieldType(Enum):
    """Supported field types for validation"""
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

@dataclass
class ValidationRule:
    """Validation rule definition"""
    field_name: str
    rule_type: str
    parameters: Dict[str, Any]
    severity: ValidationSeverity = ValidationSeverity.ERROR
    description: str = ""
    custom_validator: Optional[Callable] = None

@dataclass
class ValidationError:
    """Validation error details"""
    field_name: str
    error_type: str
    message: str
    severity: ValidationSeverity
    actual_value: Optional[Any] = None
    expected_value: Optional[Any] = None
    suggestion: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

@dataclass
class ValidationResult:
    """Result of a validation operation"""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    validation_time_ms: float = 0.0
    fields_validated: int = 0
    metadata: Optional[Dict[str, Any]] = None

# =============================================================================
# Validators Core Classes
# =============================================================================

class TelemetryRecordValidator:
    """
    Validator for telemetry records
    
    Provides comprehensive validation for Layer 1 telemetry records,
    ensuring data quality and schema compliance.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize telemetry record validator"""
        self.config = config or {}
        self.logger = logging.getLogger("SCAFAD.Layer1.TelemetryRecordValidator")
        
        # Validation rules
        self.validation_rules: Dict[str, List[ValidationRule]] = {}
        
        # Performance tracking
        self.validation_stats = {
            'total_validations': 0,
            'total_errors': 0,
            'total_warnings': 0,
            'average_validation_time_ms': 0.0
        }
        
        # Initialize default validation rules
        self._initialize_default_rules()
    
    def validate_record(self, record: Dict[str, Any], 
                       schema_version: str = "v2.1") -> ValidationResult:
        """
        Validate a telemetry record
        
        Args:
            record: Telemetry record to validate
            schema_version: Schema version for validation
            
        Returns:
            ValidationResult with validation details
        """
        import time
        start_time = time.time()
        
        try:
            self.validation_stats['total_validations'] += 1
            
            # Initialize validation result
            errors = []
            warnings = []
            fields_validated = 0
            
            # Get validation rules for schema version
            rules = self.validation_rules.get(schema_version, [])
            
            # Apply validation rules
            for rule in rules:
                field_value = record.get(rule.field_name)
                
                if field_value is not None:
                    fields_validated += 1
                    
                    # Apply validation rule
                    rule_result = self._apply_validation_rule(rule, field_value, record)
                    
                    if rule_result:
                        if rule_result.severity == ValidationSeverity.ERROR:
                            errors.append(rule_result)
                        elif rule_result.severity == ValidationSeverity.WARNING:
                            warnings.append(rule_result)
                        elif rule_result.severity == ValidationSeverity.INFO:
                            # Info level doesn't affect validation result
                            pass
            
            # Check for required fields
            required_field_errors = self._validate_required_fields(record, schema_version)
            errors.extend(required_field_errors)
            
            # Check for unknown fields
            unknown_field_warnings = self._validate_unknown_fields(record, schema_version)
            warnings.extend(unknown_field_warnings)
            
            # Determine overall validation result
            is_valid = len(errors) == 0
            
            validation_time = (time.time() - start_time) * 1000
            
            # Update statistics
            self._update_validation_stats(len(errors), len(warnings), validation_time)
            
            # Create validation result
            result = ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                validation_time_ms=validation_time,
                fields_validated=fields_validated,
                metadata={
                    'schema_version': schema_version,
                    'record_id': record.get('record_id', 'unknown')
                }
            )
            
            self.logger.debug(f"Record validation completed in {validation_time:.2f}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"Record validation failed: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    field_name='validation_system',
                    error_type='system_error',
                    message=f"Validation system error: {str(e)}",
                    severity=ValidationSeverity.CRITICAL
                )],
                warnings=[],
                validation_time_ms=0.0,
                fields_validated=0
            )
    
    def add_validation_rule(self, rule: ValidationRule, schema_version: str = "v2.1"):
        """
        Add a custom validation rule
        
        Args:
            rule: ValidationRule to add
            schema_version: Schema version for the rule
        """
        if schema_version not in self.validation_rules:
            self.validation_rules[schema_version] = []
        
        self.validation_rules[schema_version].append(rule)
        self.logger.info(f"Added validation rule for {rule.field_name} in schema {schema_version}")
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics"""
        return self.validation_stats.copy()
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _initialize_default_rules(self):
        """Initialize default validation rules for v2.1 schema"""
        v2_1_rules = [
            # Required field validation
            ValidationRule(
                field_name='record_id',
                rule_type='required',
                parameters={},
                severity=ValidationSeverity.ERROR,
                description="Record ID is required"
            ),
            ValidationRule(
                field_name='timestamp',
                rule_type='required',
                parameters={},
                severity=ValidationSeverity.ERROR,
                description="Timestamp is required"
            ),
            ValidationRule(
                field_name='function_name',
                rule_type='required',
                parameters={},
                severity=ValidationSeverity.ERROR,
                description="Function name is required"
            ),
            ValidationRule(
                field_name='execution_phase',
                rule_type='required',
                parameters={},
                severity=ValidationSeverity.ERROR,
                description="Execution phase is required"
            ),
            ValidationRule(
                field_name='anomaly_type',
                rule_type='required',
                parameters={},
                severity=ValidationSeverity.ERROR,
                description="Anomaly type is required"
            ),
            ValidationRule(
                field_name='telemetry_data',
                rule_type='required',
                parameters={},
                severity=ValidationSeverity.ERROR,
                description="Telemetry data is required"
            ),
            
            # Field type validation
            ValidationRule(
                field_name='record_id',
                rule_type='type',
                parameters={'expected_type': FieldType.STRING},
                severity=ValidationSeverity.ERROR,
                description="Record ID must be a string"
            ),
            ValidationRule(
                field_name='timestamp',
                rule_type='type',
                parameters={'expected_type': FieldType.TIMESTAMP},
                severity=ValidationSeverity.ERROR,
                description="Timestamp must be a valid timestamp"
            ),
            ValidationRule(
                field_name='function_name',
                rule_type='type',
                parameters={'expected_type': FieldType.STRING},
                severity=ValidationSeverity.ERROR,
                description="Function name must be a string"
            ),
            ValidationRule(
                field_name='execution_phase',
                rule_type='enum',
                parameters={'allowed_values': ['invocation', 'execution', 'completion', 'error']},
                severity=ValidationSeverity.ERROR,
                description="Execution phase must be one of the allowed values"
            ),
            ValidationRule(
                field_name='anomaly_type',
                rule_type='type',
                parameters={'expected_type': FieldType.STRING},
                severity=ValidationSeverity.ERROR,
                description="Anomaly type must be a string"
            ),
            ValidationRule(
                field_name='telemetry_data',
                rule_type='type',
                parameters={'expected_type': FieldType.JSON_OBJECT},
                severity=ValidationSeverity.ERROR,
                description="Telemetry data must be a JSON object"
            ),
            
            # Field constraint validation
            ValidationRule(
                field_name='timestamp',
                rule_type='range',
                parameters={'min_value': 0, 'max_value': 9999999999999},
                severity=ValidationSeverity.ERROR,
                description="Timestamp must be a valid Unix timestamp"
            ),
            ValidationRule(
                field_name='function_name',
                rule_type='pattern',
                parameters={'pattern': r'^[a-zA-Z_][a-zA-Z0-9_]*$'},
                severity=ValidationSeverity.WARNING,
                description="Function name should follow Python naming conventions"
            ),
            
            # Optional field validation
            ValidationRule(
                field_name='provenance_chain',
                rule_type='type',
                parameters={'expected_type': FieldType.JSON_OBJECT},
                severity=ValidationSeverity.WARNING,
                description="Provenance chain should be a JSON object if present"
            ),
            ValidationRule(
                field_name='context_metadata',
                rule_type='type',
                parameters={'expected_type': FieldType.JSON_OBJECT},
                severity=ValidationSeverity.WARNING,
                description="Context metadata should be a JSON object if present"
            ),
            ValidationRule(
                field_name='schema_version',
                rule_type='type',
                parameters={'expected_type': FieldType.STRING},
                severity=ValidationSeverity.WARNING,
                description="Schema version should be a string if present"
            )
        ]
        
        self.validation_rules["v2.1"] = v2_1_rules
    
    def _apply_validation_rule(self, rule: ValidationRule, field_value: Any, 
                              record: Dict[str, Any]) -> Optional[ValidationError]:
        """Apply a validation rule to a field value"""
        try:
            if rule.custom_validator:
                # Use custom validator
                if not rule.custom_validator(field_value, record):
                    return ValidationError(
                        field_name=rule.field_name,
                        error_type='custom_validation_failed',
                        message=rule.description or "Custom validation failed",
                        severity=rule.severity,
                        actual_value=field_value
                    )
                return None
            
            # Apply built-in validation rules
            if rule.rule_type == 'type':
                return self._validate_field_type(rule, field_value)
            elif rule.rule_type == 'range':
                return self._validate_field_range(rule, field_value)
            elif rule.rule_type == 'pattern':
                return self._validate_field_pattern(rule, field_value)
            elif rule.rule_type == 'enum':
                return self._validate_field_enum(rule, field_value)
            elif rule.rule_type == 'required':
                # Required field validation is handled separately
                return None
            else:
                self.logger.warning(f"Unknown validation rule type: {rule.rule_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error applying validation rule: {str(e)}")
            return ValidationError(
                field_name=rule.field_name,
                error_type='validation_error',
                message=f"Validation error: {str(e)}",
                severity=ValidationSeverity.ERROR,
                actual_value=field_value
            )
    
    def _validate_field_type(self, rule: ValidationRule, field_value: Any) -> Optional[ValidationError]:
        """Validate field type"""
        expected_type = rule.parameters.get('expected_type')
        if not expected_type:
            return None
        
        is_valid = False
        
        if expected_type == FieldType.STRING:
            is_valid = isinstance(field_value, str)
        elif expected_type == FieldType.INTEGER:
            is_valid = isinstance(field_value, int) and not isinstance(field_value, bool)
        elif expected_type == FieldType.FLOAT:
            is_valid = isinstance(field_value, (int, float)) and not isinstance(field_value, bool)
        elif expected_type == FieldType.BOOLEAN:
            is_valid = isinstance(field_value, bool)
        elif expected_type == FieldType.TIMESTAMP:
            is_valid = self._is_valid_timestamp(field_value)
        elif expected_type == FieldType.IP_ADDRESS:
            is_valid = self._is_valid_ip_address(field_value)
        elif expected_type == FieldType.URL:
            is_valid = self._is_valid_url(field_value)
        elif expected_type == FieldType.EMAIL:
            is_valid = self._is_valid_email(field_value)
        elif expected_type == FieldType.JSON_OBJECT:
            is_valid = isinstance(field_value, dict)
        elif expected_type == FieldType.BASE64:
            is_valid = self._is_valid_base64(field_value)
        elif expected_type == FieldType.UUID:
            is_valid = self._is_valid_uuid(field_value)
        elif expected_type == FieldType.ARRAY:
            is_valid = isinstance(field_value, list)
        elif expected_type == FieldType.NESTED_OBJECT:
            is_valid = isinstance(field_value, dict)
        
        if not is_valid:
            return ValidationError(
                field_name=rule.field_name,
                error_type='type_mismatch',
                message=f"Field must be of type {expected_type.value}",
                severity=rule.severity,
                actual_value=field_value,
                expected_value=expected_type.value
            )
        
        return None
    
    def _validate_field_range(self, rule: ValidationRule, field_value: Any) -> Optional[ValidationError]:
        """Validate field range"""
        min_value = rule.parameters.get('min_value')
        max_value = rule.parameters.get('max_value')
        
        if min_value is not None and field_value < min_value:
            return ValidationError(
                field_name=rule.field_name,
                error_type='range_violation',
                message=f"Field value must be >= {min_value}",
                severity=rule.severity,
                actual_value=field_value,
                expected_value=f">= {min_value}"
            )
        
        if max_value is not None and field_value > max_value:
            return ValidationError(
                field_name=rule.field_name,
                error_type='range_violation',
                message=f"Field value must be <= {max_value}",
                severity=rule.severity,
                actual_value=field_value,
                expected_value=f"<= {max_value}"
            )
        
        return None
    
    def _validate_field_pattern(self, rule: ValidationRule, field_value: Any) -> Optional[ValidationError]:
        """Validate field pattern"""
        if not isinstance(field_value, str):
            return None  # Type validation will catch this
        
        pattern = rule.parameters.get('pattern')
        if not pattern:
            return None
        
        if not re.match(pattern, field_value):
            return ValidationError(
                field_name=rule.field_name,
                error_type='pattern_mismatch',
                message=f"Field value does not match required pattern",
                severity=rule.severity,
                actual_value=field_value,
                expected_value=f"pattern: {pattern}"
            )
        
        return None
    
    def _validate_field_enum(self, rule: ValidationRule, field_value: Any) -> Optional[ValidationError]:
        """Validate field enum values"""
        allowed_values = rule.parameters.get('allowed_values', [])
        if not allowed_values:
            return None
        
        if field_value not in allowed_values:
            return ValidationError(
                field_name=rule.field_name,
                error_type='enum_violation',
                message=f"Field value must be one of: {', '.join(map(str, allowed_values))}",
                severity=rule.severity,
                actual_value=field_value,
                expected_value=allowed_values
            )
        
        return None
    
    def _validate_required_fields(self, record: Dict[str, Any], schema_version: str) -> List[ValidationError]:
        """Validate that all required fields are present"""
        errors = []
        
        # Get required fields for schema version
        required_fields = self._get_required_fields(schema_version)
        
        for field_name in required_fields:
            if field_name not in record or record[field_name] is None:
                errors.append(ValidationError(
                    field_name=field_name,
                    error_type='missing_required_field',
                    message=f"Required field '{field_name}' is missing",
                    severity=ValidationSeverity.ERROR
                ))
        
        return errors
    
    def _validate_unknown_fields(self, record: Dict[str, Any], schema_version: str) -> List[ValidationError]:
        """Validate that no unknown fields are present"""
        warnings = []
        
        # Get known fields for schema version
        known_fields = self._get_known_fields(schema_version)
        
        for field_name in record.keys():
            if field_name not in known_fields:
                warnings.append(ValidationError(
                    field_name=field_name,
                    error_type='unknown_field',
                    message=f"Unknown field '{field_name}' not in schema {schema_version}",
                    severity=ValidationSeverity.WARNING,
                    actual_value=field_name
                ))
        
        return warnings
    
    def _get_required_fields(self, schema_version: str) -> Set[str]:
        """Get required fields for a schema version"""
        if schema_version == "v2.1":
            return {
                'record_id', 'timestamp', 'function_name', 
                'execution_phase', 'anomaly_type', 'telemetry_data'
            }
        else:
            return set()
    
    def _get_known_fields(self, schema_version: str) -> Set[str]:
        """Get known fields for a schema version"""
        if schema_version == "v2.1":
            return {
                'record_id', 'timestamp', 'function_name', 
                'execution_phase', 'anomaly_type', 'telemetry_data',
                'provenance_chain', 'context_metadata', 'schema_version'
            }
        else:
            return set()
    
    def _update_validation_stats(self, error_count: int, warning_count: int, validation_time: float):
        """Update validation statistics"""
        self.validation_stats['total_errors'] += error_count
        self.validation_stats['total_warnings'] += warning_count
        
        # Update average validation time
        current_avg = self.validation_stats['average_validation_time_ms']
        total_validations = self.validation_stats['total_validations']
        
        if total_validations > 0:
            self.validation_stats['average_validation_time_ms'] = (
                (current_avg * (total_validations - 1) + validation_time) / total_validations
            )
    
    # =========================================================================
    # Field Type Validation Helpers
    # =========================================================================
    
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
    
    def _is_valid_ip_address(self, value: Any) -> bool:
        """Check if value is a valid IP address"""
        try:
            if isinstance(value, str):
                ipaddress.ip_address(value)
                return True
            else:
                return False
        except ValueError:
            return False
    
    def _is_valid_url(self, value: Any) -> bool:
        """Check if value is a valid URL"""
        try:
            if isinstance(value, str):
                result = urlparse(value)
                return all([result.scheme, result.netloc])
            else:
                return False
        except Exception:
            return False
    
    def _is_valid_email(self, value: Any) -> bool:
        """Check if value is a valid email address"""
        try:
            if isinstance(value, str):
                email_validator.validate_email(value)
                return True
            else:
                return False
        except Exception:
            return False
    
    def _is_valid_base64(self, value: Any) -> bool:
        """Check if value is valid base64"""
        try:
            if isinstance(value, str):
                # Try to decode
                import base64
                base64.b64decode(value)
                return True
            else:
                return False
        except Exception:
            return False
    
    def _is_valid_uuid(self, value: Any) -> bool:
        """Check if value is a valid UUID"""
        try:
            if isinstance(value, str):
                uuid.UUID(value)
                return True
            else:
                return False
        except ValueError:
            return False

# =============================================================================
# Utility Functions
# =============================================================================

def validate_telemetry_record(record: Dict[str, Any], 
                            schema_version: str = "v2.1") -> ValidationResult:
    """Quick validation function for telemetry records"""
    validator = TelemetryRecordValidator()
    return validator.validate_record(record, schema_version)

def validate_field_type(field_value: Any, expected_type: FieldType) -> bool:
    """Quick field type validation"""
    validator = TelemetryRecordValidator()
    
    # Create a temporary rule for type validation
    rule = ValidationRule(
        field_name='temp',
        rule_type='type',
        parameters={'expected_type': expected_type},
        severity=ValidationSeverity.ERROR
    )
    
    # Apply the rule
    error = validator._apply_validation_rule(rule, field_value, {})
    return error is None

def validate_required_fields(record: Dict[str, Any], required_fields: List[str]) -> List[str]:
    """Quick required field validation"""
    missing_fields = []
    
    for field_name in required_fields:
        if field_name not in record or record[field_name] is None:
            missing_fields.append(field_name)
    
    return missing_fields

# =============================================================================
# Validator Factory Functions
# =============================================================================

def create_telemetry_record_validator(config: Optional[Dict[str, Any]] = None) -> TelemetryRecordValidator:
    """Create a telemetry record validator with default configuration"""
    return TelemetryRecordValidator(config)

if __name__ == "__main__":
    # Example usage
    validator = create_telemetry_record_validator()
    
    # Test valid record
    valid_record = {
        'record_id': 'test123',
        'timestamp': 1640995200.0,
        'function_name': 'test_function',
        'execution_phase': 'invocation',
        'anomaly_type': 'performance',
        'telemetry_data': {'cpu_usage': 85.5}
    }
    
    result = validator.validate_record(valid_record)
    print(f"Valid record validation: {result.is_valid}")
    print(f"Errors: {len(result.errors)}, Warnings: {len(result.warnings)}")
    
    # Test invalid record
    invalid_record = {
        'record_id': 'test123',
        'timestamp': 'invalid_timestamp',
        'function_name': 'test_function',
        'execution_phase': 'invalid_phase',
        'anomaly_type': 'performance',
        'telemetry_data': {'cpu_usage': 85.5}
    }
    
    result = validator.validate_record(invalid_record)
    print(f"\nInvalid record validation: {result.is_valid}")
    print(f"Errors: {len(result.errors)}, Warnings: {len(result.warnings)}")
    
    for error in result.errors:
        print(f"- {error.field_name}: {error.message}")
    
    # Get validation stats
    stats = validator.get_validation_stats()
    print(f"\nValidation stats: {stats}")
