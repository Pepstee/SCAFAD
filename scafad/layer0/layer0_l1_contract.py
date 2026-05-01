"""
SCAFAD Layer 0→Layer 1 Contract Validation
==========================================

Implements contract validation between Layer 0 and Layer 1:
- Schema versioning with backward/forward compatibility
- Interface contract validation
- Data format standardization  
- Protocol negotiation and capability exchange
- Migration path management
- Contract breach detection and handling

Academic References:
- Interface contracts (Meyer, Design by Contract)
- Schema evolution (Bernstein & Newcomer, Principles of Transaction Processing)
- API versioning strategies (Fowler, Refactoring)
- Protocol negotiation (RFC 7231, HTTP/1.1 Semantics)
"""

import time
import json
import logging
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import uuid
from collections import deque, defaultdict
import jsonschema
from packaging import version

# Import configuration
from .app_config import Layer0Config

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Enumerations and Data Structures
# =============================================================================

class SchemaVersion(Enum):
    """Supported schema versions"""
    V1_0 = "1.0"
    V1_1 = "1.1"
    V2_0 = "2.0"
    V2_1 = "2.1"

class CompatibilityLevel(Enum):
    """Compatibility levels between versions"""
    FULLY_COMPATIBLE = "fully_compatible"
    BACKWARD_COMPATIBLE = "backward_compatible"
    FORWARD_COMPATIBLE = "forward_compatible"
    BREAKING_CHANGE = "breaking_change"

class ContractViolationType(Enum):
    """Types of contract violations"""
    SCHEMA_MISMATCH = "schema_mismatch"
    REQUIRED_FIELD_MISSING = "required_field_missing"
    TYPE_MISMATCH = "type_mismatch"
    VERSION_INCOMPATIBLE = "version_incompatible"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    PROTOCOL_VIOLATION = "protocol_violation"

class InterfaceType(Enum):
    """Types of interfaces between layers"""
    TELEMETRY_INGESTION = "telemetry_ingestion"
    ANOMALY_DETECTION_RESULT = "anomaly_detection_result"
    HEALTH_STATUS = "health_status"
    CONFIGURATION_UPDATE = "configuration_update"
    ALERT_NOTIFICATION = "alert_notification"

@dataclass
class ContractSchema:
    """Contract schema definition"""
    interface_type: InterfaceType
    version: SchemaVersion
    schema_definition: Dict[str, Any]
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    deprecated_fields: List[str] = field(default_factory=list)
    max_payload_size_bytes: int = 1024 * 1024  # 1MB default

@dataclass
class ContractViolation:
    """Contract violation record"""
    violation_id: str
    timestamp: float
    interface_type: InterfaceType
    violation_type: ContractViolationType
    expected_version: SchemaVersion
    actual_version: Optional[SchemaVersion]
    details: Dict[str, Any] = field(default_factory=dict)
    payload_sample: Optional[Dict[str, Any]] = None

@dataclass
class ValidationResult:
    """Result of contract validation"""
    is_valid: bool
    schema_version: SchemaVersion
    interface_type: InterfaceType
    violations: List[ContractViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    compatibility_level: CompatibilityLevel = CompatibilityLevel.FULLY_COMPATIBLE

@dataclass
class ContractMetrics:
    """Metrics for contract validation"""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    contract_violations: int = 0
    
    version_distribution: Dict[SchemaVersion, int] = field(default_factory=dict)
    interface_usage: Dict[InterfaceType, int] = field(default_factory=dict)
    violation_types: Dict[ContractViolationType, int] = field(default_factory=dict)

# =============================================================================
# Schema Registry
# =============================================================================

class SchemaRegistry:
    """Registry for managing contract schemas"""
    
    def __init__(self):
        self.schemas: Dict[Tuple[InterfaceType, SchemaVersion], ContractSchema] = {}
        self._load_default_schemas()
        logger.info("Schema Registry initialized")
    
    def _load_default_schemas(self):
        """Load default contract schemas"""
        
        # Telemetry Ingestion Schema v1.0
        telemetry_v1_0 = ContractSchema(
            interface_type=InterfaceType.TELEMETRY_INGESTION,
            version=SchemaVersion.V1_0,
            schema_definition={
                "type": "object",
                "properties": {
                    "telemetry_id": {"type": "string"},
                    "timestamp": {"type": "number"},
                    "function_id": {"type": "string"},
                    "execution_phase": {"type": "string", "enum": ["cold_start", "invoke", "cleanup"]},
                    "duration": {"type": "number", "minimum": 0},
                    "memory_spike_kb": {"type": "integer", "minimum": 0},
                    "cpu_utilization": {"type": "number", "minimum": 0, "maximum": 100},
                    "anomaly_type": {"type": "string"},
                    "custom_fields": {"type": "object"}
                },
                "required": ["telemetry_id", "timestamp", "function_id", "execution_phase"],
                "additionalProperties": False
            },
            required_fields=["telemetry_id", "timestamp", "function_id", "execution_phase"],
            optional_fields=["duration", "memory_spike_kb", "cpu_utilization", "anomaly_type", "custom_fields"]
        )
        
        # Telemetry Ingestion Schema v2.0 (with additional fields)
        telemetry_v2_0 = ContractSchema(
            interface_type=InterfaceType.TELEMETRY_INGESTION,
            version=SchemaVersion.V2_0,
            schema_definition={
                "type": "object",
                "properties": {
                    "telemetry_id": {"type": "string"},
                    "timestamp": {"type": "number"},
                    "function_id": {"type": "string"},
                    "execution_phase": {"type": "string", "enum": ["cold_start", "invoke", "cleanup", "timeout"]},
                    "duration": {"type": "number", "minimum": 0},
                    "memory_spike_kb": {"type": "integer", "minimum": 0},
                    "cpu_utilization": {"type": "number", "minimum": 0, "maximum": 100},
                    "anomaly_type": {"type": "string"},
                    "custom_fields": {"type": "object"},
                    # New fields in v2.0
                    "correlation_id": {"type": "string"},
                    "trace_id": {"type": "string"},
                    "span_id": {"type": "string"},
                    "network_latency_ms": {"type": "number", "minimum": 0},
                    "disk_io_bytes": {"type": "integer", "minimum": 0}
                },
                "required": ["telemetry_id", "timestamp", "function_id", "execution_phase"],
                "additionalProperties": False
            },
            required_fields=["telemetry_id", "timestamp", "function_id", "execution_phase"],
            optional_fields=["duration", "memory_spike_kb", "cpu_utilization", "anomaly_type", "custom_fields",
                           "correlation_id", "trace_id", "span_id", "network_latency_ms", "disk_io_bytes"]
        )
        
        # Anomaly Detection Result Schema v1.0
        anomaly_result_v1_0 = ContractSchema(
            interface_type=InterfaceType.ANOMALY_DETECTION_RESULT,
            version=SchemaVersion.V1_0,
            schema_definition={
                "type": "object",
                "properties": {
                    "result_id": {"type": "string"},
                    "telemetry_id": {"type": "string"},
                    "timestamp": {"type": "number"},
                    "overall_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "detections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "anomaly_type": {"type": "string"},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                "algorithm_name": {"type": "string"},
                                "details": {"type": "object"}
                            },
                            "required": ["anomaly_type", "confidence", "algorithm_name"]
                        }
                    }
                },
                "required": ["result_id", "telemetry_id", "timestamp", "overall_confidence", "detections"],
                "additionalProperties": False
            },
            required_fields=["result_id", "telemetry_id", "timestamp", "overall_confidence", "detections"]
        )
        
        # Health Status Schema v1.0
        health_status_v1_0 = ContractSchema(
            interface_type=InterfaceType.HEALTH_STATUS,
            version=SchemaVersion.V1_0,
            schema_definition={
                "type": "object",
                "properties": {
                    "component_id": {"type": "string"},
                    "timestamp": {"type": "number"},
                    "status": {"type": "string", "enum": ["healthy", "degraded", "critical", "failed", "unknown"]},
                    "metrics": {"type": "object"},
                    "alerts": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["component_id", "timestamp", "status"],
                "additionalProperties": False
            },
            required_fields=["component_id", "timestamp", "status"],
            optional_fields=["metrics", "alerts"]
        )
        
        # Register all schemas
        schemas = [telemetry_v1_0, telemetry_v2_0, anomaly_result_v1_0, health_status_v1_0]
        for schema in schemas:
            key = (schema.interface_type, schema.version)
            self.schemas[key] = schema
    
    def register_schema(self, schema: ContractSchema):
        """Register a new contract schema"""
        key = (schema.interface_type, schema.version)
        self.schemas[key] = schema
        logger.info(f"Registered schema: {schema.interface_type.value} v{schema.version.value}")
    
    def get_schema(self, interface_type: InterfaceType, version: SchemaVersion) -> Optional[ContractSchema]:
        """Get schema for specific interface and version"""
        key = (interface_type, version)
        return self.schemas.get(key)
    
    def get_latest_schema(self, interface_type: InterfaceType) -> Optional[ContractSchema]:
        """Get latest schema for interface type"""
        interface_schemas = [
            schema for (iface, ver), schema in self.schemas.items()
            if iface == interface_type
        ]
        
        if not interface_schemas:
            return None
        
        # Sort by version and return latest
        interface_schemas.sort(key=lambda s: version.parse(s.version.value), reverse=True)
        return interface_schemas[0]
    
    def get_compatible_versions(self, interface_type: InterfaceType, 
                               target_version: SchemaVersion) -> List[SchemaVersion]:
        """Get list of compatible versions for given interface and version"""
        target_schema = self.get_schema(interface_type, target_version)
        if not target_schema:
            return []
        
        compatible_versions = []
        for (iface, ver), schema in self.schemas.items():
            if iface == interface_type:
                compatibility = self._check_compatibility(target_schema, schema)
                if compatibility != CompatibilityLevel.BREAKING_CHANGE:
                    compatible_versions.append(ver)
        
        return compatible_versions
    
    def _check_compatibility(self, schema1: ContractSchema, schema2: ContractSchema) -> CompatibilityLevel:
        """Check compatibility between two schemas"""
        # Simple version-based compatibility check
        v1 = version.parse(schema1.version.value)
        v2 = version.parse(schema2.version.value)
        
        if v1 == v2:
            return CompatibilityLevel.FULLY_COMPATIBLE
        elif v1.major == v2.major:
            if v1.minor <= v2.minor:
                return CompatibilityLevel.BACKWARD_COMPATIBLE
            else:
                return CompatibilityLevel.FORWARD_COMPATIBLE
        else:
            return CompatibilityLevel.BREAKING_CHANGE

# =============================================================================
# Contract Validator
# =============================================================================

class ContractValidator:
    """Validates data against contract schemas"""
    
    def __init__(self, schema_registry: SchemaRegistry):
        self.schema_registry = schema_registry
        self.metrics = ContractMetrics()
        self.violations: deque = deque(maxlen=1000)
        self._lock = threading.RLock()
        logger.info("Contract Validator initialized")
    
    def validate_payload(self, payload: Dict[str, Any], 
                        interface_type: InterfaceType,
                        expected_version: SchemaVersion = None) -> ValidationResult:
        """Validate payload against contract schema"""
        start_time = time.time()
        
        with self._lock:
            self.metrics.total_validations += 1
            self.metrics.interface_usage[interface_type] = (
                self.metrics.interface_usage.get(interface_type, 0) + 1
            )
        
        # Determine schema to use
        if expected_version is None:
            schema = self.schema_registry.get_latest_schema(interface_type)
            if not schema:
                return ValidationResult(
                    is_valid=False,
                    schema_version=SchemaVersion.V1_0,
                    interface_type=interface_type,
                    violations=[ContractViolation(
                        violation_id=str(uuid.uuid4()),
                        timestamp=time.time(),
                        interface_type=interface_type,
                        violation_type=ContractViolationType.SCHEMA_MISMATCH,
                        expected_version=SchemaVersion.V1_0,
                        actual_version=None,
                        details={"error": "No schema found for interface"}
                    )]
                )
        else:
            schema = self.schema_registry.get_schema(interface_type, expected_version)
            if not schema:
                return ValidationResult(
                    is_valid=False,
                    schema_version=expected_version,
                    interface_type=interface_type,
                    violations=[ContractViolation(
                        violation_id=str(uuid.uuid4()),
                        timestamp=time.time(),
                        interface_type=interface_type,
                        violation_type=ContractViolationType.VERSION_INCOMPATIBLE,
                        expected_version=expected_version,
                        actual_version=None,
                        details={"error": f"Schema not found for version {expected_version.value}"}
                    )]
                )
        
        result = ValidationResult(
            is_valid=True,
            schema_version=schema.version,
            interface_type=interface_type
        )
        
        # Check payload size
        payload_size = len(json.dumps(payload))
        if payload_size > schema.max_payload_size_bytes:
            violation = ContractViolation(
                violation_id=str(uuid.uuid4()),
                timestamp=time.time(),
                interface_type=interface_type,
                violation_type=ContractViolationType.PAYLOAD_TOO_LARGE,
                expected_version=schema.version,
                actual_version=schema.version,
                details={
                    "payload_size": payload_size,
                    "max_size": schema.max_payload_size_bytes
                }
            )
            result.violations.append(violation)
            result.is_valid = False
        
        # Validate against JSON schema
        try:
            jsonschema.validate(payload, schema.schema_definition)
        except jsonschema.ValidationError as e:
            violation = ContractViolation(
                violation_id=str(uuid.uuid4()),
                timestamp=time.time(),
                interface_type=interface_type,
                violation_type=ContractViolationType.SCHEMA_MISMATCH,
                expected_version=schema.version,
                actual_version=None,
                details={
                    "validation_error": str(e),
                    "error_path": list(e.path) if e.path else [],
                    "error_message": e.message
                },
                payload_sample=payload
            )
            result.violations.append(violation)
            result.is_valid = False
        except jsonschema.SchemaError as e:
            logger.error(f"Schema error: {e}")
            result.is_valid = False
        
        # Check required fields
        for required_field in schema.required_fields:
            if required_field not in payload:
                violation = ContractViolation(
                    violation_id=str(uuid.uuid4()),
                    timestamp=time.time(),
                    interface_type=interface_type,
                    violation_type=ContractViolationType.REQUIRED_FIELD_MISSING,
                    expected_version=schema.version,
                    actual_version=None,
                    details={"missing_field": required_field}
                )
                result.violations.append(violation)
                result.is_valid = False
        
        # Check for deprecated fields (warnings only)
        for deprecated_field in schema.deprecated_fields:
            if deprecated_field in payload:
                result.warnings.append(f"Field '{deprecated_field}' is deprecated in version {schema.version.value}")
        
        # Update metrics
        with self._lock:
            if result.is_valid:
                self.metrics.successful_validations += 1
            else:
                self.metrics.failed_validations += 1
                self.metrics.contract_violations += len(result.violations)
                
                # Track violation types
                for violation in result.violations:
                    self.metrics.violation_types[violation.violation_type] = (
                        self.metrics.violation_types.get(violation.violation_type, 0) + 1
                    )
                    self.violations.append(violation)
            
            self.metrics.version_distribution[schema.version] = (
                self.metrics.version_distribution.get(schema.version, 0) + 1
            )
        
        logger.debug(f"Contract validation: {'PASS' if result.is_valid else 'FAIL'} "
                    f"({interface_type.value} v{schema.version.value})")
        
        return result
    
    def get_validation_metrics(self) -> Dict[str, Any]:
        """Get contract validation metrics"""
        with self._lock:
            success_rate = (
                self.metrics.successful_validations / max(1, self.metrics.total_validations)
            )
            
            return {
                "total_validations": self.metrics.total_validations,
                "successful_validations": self.metrics.successful_validations,
                "failed_validations": self.metrics.failed_validations,
                "success_rate": success_rate,
                "contract_violations": self.metrics.contract_violations,
                "version_distribution": {
                    v.value: count for v, count in self.metrics.version_distribution.items()
                },
                "interface_usage": {
                    iface.value: count for iface, count in self.metrics.interface_usage.items()
                },
                "violation_types": {
                    vtype.value: count for vtype, count in self.metrics.violation_types.items()
                }
            }
    
    def get_recent_violations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent contract violations"""
        with self._lock:
            violations = []
            for violation in list(self.violations)[-limit:]:
                violations.append({
                    "violation_id": violation.violation_id,
                    "timestamp": violation.timestamp,
                    "interface_type": violation.interface_type.value,
                    "violation_type": violation.violation_type.value,
                    "expected_version": violation.expected_version.value if violation.expected_version else None,
                    "actual_version": violation.actual_version.value if violation.actual_version else None,
                    "details": violation.details
                })
            return violations

# =============================================================================
# L0-L1 Contract Manager
# =============================================================================

class L0L1ContractManager:
    """
    Main contract manager for L0→L1 interface
    
    Features:
    - Schema registry and versioning
    - Contract validation
    - Compatibility checking
    - Migration support
    - Metrics and monitoring
    """
    
    def __init__(self, config: Layer0Config = None):
        self.config = config
        self.schema_registry = SchemaRegistry()
        self.validator = ContractValidator(self.schema_registry)
        self._lock = threading.RLock()
        
        logger.info("L0-L1 Contract Manager initialized")
    
    def validate_telemetry_record(self, telemetry_data: Dict[str, Any], 
                                 version: SchemaVersion = None) -> ValidationResult:
        """Validate telemetry record for L0→L1 interface"""
        return self.validator.validate_payload(
            telemetry_data, 
            InterfaceType.TELEMETRY_INGESTION,
            version
        )
    
    def validate_anomaly_result(self, anomaly_result: Dict[str, Any],
                               version: SchemaVersion = None) -> ValidationResult:
        """Validate anomaly detection result for L0→L1 interface"""
        return self.validator.validate_payload(
            anomaly_result,
            InterfaceType.ANOMALY_DETECTION_RESULT,
            version
        )
    
    def validate_health_status(self, health_data: Dict[str, Any],
                              version: SchemaVersion = None) -> ValidationResult:
        """Validate health status data for L0→L1 interface"""
        return self.validator.validate_payload(
            health_data,
            InterfaceType.HEALTH_STATUS,
            version
        )
    
    def check_version_compatibility(self, interface_type: InterfaceType,
                                   from_version: SchemaVersion,
                                   to_version: SchemaVersion) -> CompatibilityLevel:
        """Check compatibility between schema versions"""
        from_schema = self.schema_registry.get_schema(interface_type, from_version)
        to_schema = self.schema_registry.get_schema(interface_type, to_version)
        
        if not from_schema or not to_schema:
            return CompatibilityLevel.BREAKING_CHANGE
        
        return self.schema_registry._check_compatibility(from_schema, to_schema)
    
    def get_supported_versions(self, interface_type: InterfaceType) -> List[SchemaVersion]:
        """Get supported versions for interface type"""
        versions = []
        for (iface, ver), schema in self.schema_registry.schemas.items():
            if iface == interface_type:
                versions.append(ver)
        
        # Sort by version
        versions.sort(key=lambda v: version.parse(v.value))
        return versions
    
    def get_migration_path(self, interface_type: InterfaceType,
                          from_version: SchemaVersion,
                          to_version: SchemaVersion) -> List[SchemaVersion]:
        """Get migration path between versions"""
        # Simple implementation - direct migration for now
        # In practice, this would handle complex migration paths
        supported_versions = self.get_supported_versions(interface_type)
        
        from_idx = supported_versions.index(from_version) if from_version in supported_versions else -1
        to_idx = supported_versions.index(to_version) if to_version in supported_versions else -1
        
        if from_idx == -1 or to_idx == -1:
            return []
        
        if from_idx <= to_idx:
            return supported_versions[from_idx:to_idx + 1]
        else:
            return supported_versions[to_idx:from_idx + 1][::-1]
    
    def get_contract_status(self) -> Dict[str, Any]:
        """Get comprehensive contract status"""
        return {
            "schema_registry": {
                "total_schemas": len(self.schema_registry.schemas),
                "interface_types": list(set(iface.value for iface, ver in self.schema_registry.schemas.keys())),
                "supported_versions": list(set(ver.value for iface, ver in self.schema_registry.schemas.keys()))
            },
            "validation_metrics": self.validator.get_validation_metrics(),
            "recent_violations_count": len(self.validator.violations)
        }
    
    def register_custom_schema(self, schema: ContractSchema):
        """Register custom contract schema"""
        self.schema_registry.register_schema(schema)

# =============================================================================
# Factory Functions
# =============================================================================

def create_l0_l1_contract_manager(config: Layer0Config = None) -> L0L1ContractManager:
    """Create L0-L1 contract manager"""
    return L0L1ContractManager(config)

# =============================================================================
# Testing Functions
# =============================================================================

async def test_l0_l1_contract():
    """Test L0-L1 contract validation"""
    print("🧪 Testing L0-L1 Contract Validation...")
    
    contract_manager = create_l0_l1_contract_manager()
    
    # Test valid telemetry record
    valid_telemetry = {
        "telemetry_id": "test_001",
        "timestamp": time.time(),
        "function_id": "test_function",
        "execution_phase": "invoke",
        "duration": 150.5,
        "memory_spike_kb": 1024,
        "cpu_utilization": 45.2,
        "anomaly_type": "benign",
        "custom_fields": {"test": True}
    }
    
    result = contract_manager.validate_telemetry_record(valid_telemetry, SchemaVersion.V1_0)
    assert result.is_valid, f"Valid telemetry should pass validation: {result.violations}"
    
    # Test invalid telemetry record (missing required field)
    invalid_telemetry = {
        "timestamp": time.time(),
        "function_id": "test_function",
        "execution_phase": "invoke"
        # Missing telemetry_id
    }
    
    result = contract_manager.validate_telemetry_record(invalid_telemetry, SchemaVersion.V1_0)
    assert not result.is_valid, "Invalid telemetry should fail validation"
    assert len(result.violations) > 0, "Should have violations"
    assert any(v.violation_type == ContractViolationType.REQUIRED_FIELD_MISSING 
              for v in result.violations), "Should have missing field violation"
    
    # Test valid anomaly result
    valid_anomaly_result = {
        "result_id": "result_001",
        "telemetry_id": "test_001", 
        "timestamp": time.time(),
        "overall_confidence": 0.85,
        "detections": [
            {
                "anomaly_type": "cpu_spike",
                "confidence": 0.9,
                "algorithm_name": "isolation_forest",
                "details": {"threshold": 0.8}
            }
        ]
    }
    
    result = contract_manager.validate_anomaly_result(valid_anomaly_result, SchemaVersion.V1_0)
    assert result.is_valid, f"Valid anomaly result should pass validation: {result.violations}"
    
    # Test version compatibility
    compatibility = contract_manager.check_version_compatibility(
        InterfaceType.TELEMETRY_INGESTION,
        SchemaVersion.V1_0,
        SchemaVersion.V2_0
    )
    assert compatibility != CompatibilityLevel.BREAKING_CHANGE, "Should be compatible"
    
    # Get contract status
    status = contract_manager.get_contract_status()
    assert status["schema_registry"]["total_schemas"] > 0, "Should have schemas registered"
    assert status["validation_metrics"]["total_validations"] > 0, "Should have validation metrics"
    
    print(f"✅ L0-L1 Contract Validation test completed")
    print(f"   Total schemas: {status['schema_registry']['total_schemas']}")
    print(f"   Validations performed: {status['validation_metrics']['total_validations']}")
    print(f"   Success rate: {status['validation_metrics']['success_rate']:.3f}")
    
    return "L0-L1 Contract Validation test completed successfully"


# ---------------------------------------------------------------------------
# Com


# ---------------------------------------------------------------------------
# Compatibility alias — layer0_comprehensive_validation.py imports this name.
# The class was originally implemented as ContractValidator.
# ---------------------------------------------------------------------------
L0L1ContractValidator = ContractValidator


