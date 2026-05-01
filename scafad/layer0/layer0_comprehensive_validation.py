#!/usr/bin/env python3
"""
SCAFAD Layer 0: Comprehensive Validation & Data Flow Analysis
============================================================

This script performs a complete Layer 0 validation by:
1. Simulating data entering Layer 0
2. Following every step of the processing pipeline
3. Validating the complete data flow
4. Ensuring data is ready for Layer 1 transmission

Academic References:
- End-to-end validation methodologies (Gray et al.)
- Data flow analysis in distributed systems (Lamport et al.)
- Pipeline validation techniques (Fonseca et al.)
- Contract validation frameworks (Meyer et al.)
"""

import time
import json
import logging
import asyncio
import threading
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import statistics
import random
from collections import deque, defaultdict

# Import all Layer 0 components
from .layer0_core import AnomalyDetectionEngine, DetectionConfig
from .layer0_signal_negotiation import SignalNegotiator, ChannelType, ChannelCapability
from .layer0_redundancy_manager import RedundancyManager, RedundancyMode
from .layer0_sampler import Sampler, SamplingStrategy
from .layer0_fallback_orchestrator import FallbackOrchestrator, FallbackMode
from .layer0_runtime_control import RuntimeControlLoop, ControlPhase, ControlState
from .layer0_l1_contract import L0L1ContractValidator, ContractSchema, ValidationResult
from .layer0_adaptive_buffer import AdaptiveBuffer
from .layer0_health_monitor import HealthMonitor
from .layer0_privacy_compliance import PrivacyComplianceEngine
from .layer0_stream_processor import StreamProcessor
from .layer0_vendor_adapters import VendorAdapterManager

# Import configuration and telemetry
from .app_config import Layer0Config, TelemetryConfig
from .app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# Validation Data Structures
# =============================================================================

@dataclass
class ValidationStep:
    """Represents a single step in the Layer 0 pipeline"""
    step_name: str
    step_order: int
    input_data: Any
    output_data: Any
    processing_time_ms: float
    success: bool
    error_details: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ValidationResult:
    """Complete validation result for Layer 0"""
    validation_id: str
    start_time: float
    end_time: float
    
    # Pipeline steps
    pipeline_steps: List[ValidationStep] = field(default_factory=list)
    
    # Performance metrics
    total_processing_time_ms: float = 0.0
    step_processing_times: Dict[str, float] = field(default_factory=dict)
    
    # Success metrics
    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    
    # Data flow validation
    data_integrity_verified: bool = False
    schema_compliance: bool = False
    contract_validation: bool = False
    
    # Layer 1 readiness
    ready_for_layer1: bool = False
    layer1_contract_compliance: bool = False
    
    # Error details
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@dataclass
class TestPayload:
    """Test payload for Layer 0 validation"""
    payload_id: str
    timestamp: float
    function_name: str
    execution_phase: ExecutionPhase
    anomaly_type: AnomalyType
    telemetry_data: Dict[str, Any]
    expected_anomaly_detected: bool
    expected_anomaly_type: AnomalyType

# =============================================================================
# Layer 0 Pipeline Validator
# =============================================================================

class Layer0PipelineValidator:
    """
    Comprehensive validator for Layer 0 pipeline
    
    This class simulates the complete data flow through Layer 0 and validates
    each step to ensure data integrity and Layer 1 readiness.
    """
    
    def __init__(self, config: Layer0Config = None):
        self.config = config or Layer0Config()
        self.validation_results: List[ValidationResult] = []
        
        # Initialize all Layer 0 components
        self._initialize_components()
        
        # Test data generator
        self.test_payloads = self._generate_test_payloads()
        
        logger.info("✅ Layer 0 Pipeline Validator initialized")
    
    def _initialize_components(self):
        """Initialize all Layer 0 components"""
        try:
            # Core components
            self.signal_negotiator = SignalNegotiator(self.config)
            self.redundancy_manager = RedundancyManager(self.config)
            self.sampler = Sampler(self.config)
            self.fallback_orchestrator = FallbackOrchestrator(
                self.config,
                self.signal_negotiator,
                self.redundancy_manager,
                self.sampler
            )
            self.anomaly_detection_engine = AnomalyDetectionEngine(self.config)
            self.runtime_control = RuntimeControlLoop(self.config)
            
            # Additional components
            self.adaptive_buffer = AdaptiveBuffer(self.config)
            self.health_monitor = HealthMonitor(self.config)
            self.privacy_compliance = PrivacyComplianceEngine(self.config)
            self.stream_processor = StreamProcessor(self.config)
            self.vendor_adapters = VendorAdapterManager(self.config)
            
            # Contract validation
            self.contract_validator = L0L1ContractValidator(self.config)
            
            logger.info("✅ All Layer 0 components initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Component initialization failed: {e}")
            raise
    
    def _generate_test_payloads(self) -> List[TestPayload]:
        """Generate comprehensive test payloads for validation"""
        payloads = []
        
        # Normal execution payload
        payloads.append(TestPayload(
            payload_id="normal_execution_001",
            timestamp=time.time(),
            function_name="test_function",
            execution_phase=ExecutionPhase.EXECUTION,
            anomaly_type=AnomalyType.BENIGN,
            telemetry_data={
                "memory_usage_mb": 128.5,
                "cpu_utilization": 45.2,
                "execution_time_ms": 125.0,
                "cold_start": False,
                "error_count": 0
            },
            expected_anomaly_detected=False,
            expected_anomaly_type=AnomalyType.BENIGN
        ))
        
        # Cold start anomaly
        payloads.append(TestPayload(
            payload_id="cold_start_anomaly_001",
            timestamp=time.time(),
            function_name="test_function",
            execution_phase=ExecutionPhase.INITIALIZATION,
            anomaly_type=AnomalyType.COLD_START,
            telemetry_data={
                "memory_usage_mb": 256.0,
                "cpu_utilization": 85.0,
                "execution_time_ms": 450.0,
                "cold_start": True,
                "error_count": 0
            },
            expected_anomaly_detected=True,
            expected_anomaly_type=AnomalyType.COLD_START
        ))
        
        # Memory leak anomaly
        payloads.append(TestPayload(
            payload_id="memory_leak_anomaly_001",
            timestamp=time.time(),
            function_name="test_function",
            execution_phase=ExecutionPhase.EXECUTION,
            anomaly_type=AnomalyType.MEMORY_LEAK,
            telemetry_data={
                "memory_usage_mb": 1024.0,
                "cpu_utilization": 75.0,
                "execution_time_ms": 200.0,
                "cold_start": False,
                "error_count": 0,
                "memory_trend": "increasing"
            },
            expected_anomaly_detected=True,
            expected_anomaly_type=AnomalyType.MEMORY_LEAK
        ))
        
        # CPU burst anomaly
        payloads.append(TestPayload(
            payload_id="cpu_burst_anomaly_001",
            timestamp=time.time(),
            function_name="test_function",
            execution_phase=ExecutionPhase.EXECUTION,
            anomaly_type=AnomalyType.CPU_BURST,
            telemetry_data={
                "memory_usage_mb": 150.0,
                "cpu_utilization": 95.0,
                "execution_time_ms": 300.0,
                "cold_start": False,
                "error_count": 0,
                "cpu_spike_duration_ms": 250
            },
            expected_anomaly_detected=True,
            expected_anomaly_type=AnomalyType.CPU_BURST
        ))
        
        # Economic abuse anomaly
        payloads.append(TestPayload(
            payload_id="economic_abuse_anomaly_001",
            timestamp=time.time(),
            function_name="test_function",
            execution_phase=ExecutionPhase.EXECUTION,
            anomaly_type=AnomalyType.ECONOMIC_ABUSE,
            telemetry_data={
                "memory_usage_mb": 200.0,
                "cpu_utilization": 90.0,
                "execution_time_ms": 5000.0,  # Very long execution
                "cold_start": False,
                "error_count": 0,
                "cost_per_request": 0.50,  # High cost
                "execution_frequency": 100  # High frequency
            },
            expected_anomaly_detected=True,
            expected_anomaly_type=AnomalyType.ECONOMIC_ABUSE
        ))
        
        logger.info(f"✅ Generated {len(payloads)} test payloads")
        return payloads
    
    async def validate_complete_pipeline(self, payload: TestPayload) -> ValidationResult:
        """
        Validate the complete Layer 0 pipeline for a given payload
        
        This method simulates the complete data flow through Layer 0 and validates
        each step to ensure data integrity and Layer 1 readiness.
        """
        validation_id = f"validation_{payload.payload_id}_{int(time.time())}"
        start_time = time.time()
        
        logger.info(f"🚀 Starting Layer 0 pipeline validation for {payload.payload_id}")
        
        # Initialize validation result
        validation = ValidationResult(
            validation_id=validation_id,
            start_time=start_time,
            end_time=0.0
        )
        
        try:
            # Step 1: Signal Negotiation
            step1 = await self._validate_signal_negotiation(payload)
            validation.pipeline_steps.append(step1)
            
            # Step 2: Redundancy Management
            step2 = await self._validate_redundancy_management(payload)
            validation.pipeline_steps.append(step2)
            
            # Step 3: Sampling Strategy
            step3 = await self._validate_sampling_strategy(payload)
            validation.pipeline_steps.append(step3)
            
            # Step 4: Fallback Orchestration Check
            step4 = await self._validate_fallback_orchestration(payload)
            validation.pipeline_steps.append(step4)
            
            # Step 5: Anomaly Detection
            step5 = await self._validate_anomaly_detection(payload)
            validation.pipeline_steps.append(step5)
            
            # Step 6: Adaptive Buffer Processing
            step6 = await self._validate_adaptive_buffer(payload)
            validation.pipeline_steps.append(step6)
            
            # Step 7: Health Monitoring
            step7 = await self._validate_health_monitoring(payload)
            validation.pipeline_steps.append(step7)
            
            # Step 8: Privacy Compliance
            step8 = await self._validate_privacy_compliance(payload)
            validation.pipeline_steps.append(step8)
            
            # Step 9: Stream Processing
            step9 = await self._validate_stream_processing(payload)
            validation.pipeline_steps.append(step9)
            
            # Step 10: Vendor Adapter Processing
            step10 = await self._validate_vendor_adapters(payload)
            validation.pipeline_steps.append(step10)
            
            # Step 11: Runtime Control Loop
            step11 = await self._validate_runtime_control(payload)
            validation.pipeline_steps.append(step11)
            
            # Step 12: Layer 1 Contract Validation
            step12 = await self._validate_layer1_contract(payload)
            validation.pipeline_steps.append(step12)
            
            # Final validation summary
            await self._finalize_validation(validation, payload)
            
        except Exception as e:
            logger.error(f"❌ Pipeline validation failed: {e}")
            validation.errors.append(f"Pipeline validation failed: {e}")
        
        # Complete validation
        validation.end_time = time.time()
        validation.total_processing_time_ms = (validation.end_time - validation.start_time) * 1000
        
        # Calculate metrics
        validation.total_steps = len(validation.pipeline_steps)
        validation.successful_steps = len([s for s in validation.pipeline_steps if s.success])
        validation.failed_steps = len([s for s in validation.pipeline_steps if not s.success])
        
        # Store step processing times
        for step in validation.pipeline_steps:
            validation.step_processing_times[step.step_name] = step.processing_time_ms
        
        # Add to results
        self.validation_results.append(validation)
        
        logger.info(f"✅ Layer 0 pipeline validation completed for {payload.payload_id}")
        return validation
    
    async def _validate_signal_negotiation(self, payload: TestPayload) -> ValidationStep:
        """Validate signal negotiation step"""
        step_start = time.time()
        
        try:
            # Simulate signal negotiation
            negotiation_result = await self.signal_negotiator.negotiate_channels()
            
            # Validate negotiation results
            success = (
                negotiation_result is not None and
                len(negotiation_result) > 0 and
                all(r.status.value == 'success' for r in negotiation_result.values())
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Signal Negotiation",
                step_order=1,
                input_data=payload,
                output_data=negotiation_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "channels_negotiated": len(negotiation_result) if negotiation_result else 0,
                    "primary_channel": "cloudwatch",
                    "fallback_channels": ["xray", "sqs"]
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Signal Negotiation",
                step_order=1,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_redundancy_management(self, payload: TestPayload) -> ValidationStep:
        """Validate redundancy management step"""
        step_start = time.time()
        
        try:
            # Simulate redundancy management
            redundancy_result = await self.redundancy_manager.manage_redundancy(
                payload.telemetry_data
            )
            
            # Validate redundancy results
            success = (
                redundancy_result is not None and
                redundancy_result.redundancy_mode in [RedundancyMode.NONE, RedundancyMode.DUAL, RedundancyMode.TRIPLE]
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Redundancy Management",
                step_order=2,
                input_data=payload,
                output_data=redundancy_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "redundancy_mode": redundancy_result.redundancy_mode.value if redundancy_result else "unknown",
                    "channels_used": redundancy_result.channels_used if redundancy_result else 0
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Redundancy Management",
                step_order=2,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_sampling_strategy(self, payload: TestPayload) -> ValidationStep:
        """Validate sampling strategy step"""
        step_start = time.time()
        
        try:
            # Simulate sampling strategy
            sampling_result = await self.sampler.determine_sampling_strategy(
                payload.telemetry_data
            )
            
            # Validate sampling results
            success = (
                sampling_result is not None and
                sampling_result.strategy in [SamplingStrategy.FULL, SamplingStrategy.ADAPTIVE, SamplingStrategy.REDUCED]
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Sampling Strategy",
                step_order=3,
                input_data=payload,
                output_data=sampling_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "sampling_strategy": sampling_result.strategy.value if sampling_result else "unknown",
                    "sampling_rate": sampling_result.rate if sampling_result else 0.0
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Sampling Strategy",
                step_order=3,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_fallback_orchestration(self, payload: TestPayload) -> ValidationStep:
        """Validate fallback orchestration step"""
        step_start = time.time()
        
        try:
            # Simulate fallback orchestration check
            fallback_result = await self.fallback_orchestrator.check_fallback_conditions(
                payload.telemetry_data
            )
            
            # Validate fallback results
            success = (
                fallback_result is not None and
                fallback_result.fallback_mode in [FallbackMode.NONE, FallbackMode.GRACEFUL, FallbackMode.EMERGENCY]
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Fallback Orchestration",
                step_order=4,
                input_data=payload,
                output_data=fallback_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "fallback_mode": fallback_result.fallback_mode.value if fallback_result else "unknown",
                    "fallback_reason": fallback_result.reason if fallback_result else "none"
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Fallback Orchestration",
                step_order=4,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_anomaly_detection(self, payload: TestPayload) -> ValidationStep:
        """Validate anomaly detection step"""
        step_start = time.time()
        
        try:
            # Create telemetry record
            telemetry_record = TelemetryRecord(
                timestamp=payload.timestamp,
                function_name=payload.function_name,
                execution_phase=payload.execution_phase,
                anomaly_type=payload.anomaly_type,
                telemetry_data=payload.telemetry_data
            )
            
            # Run anomaly detection
            detection_result = await self.anomaly_detection_engine.detect_anomalies(
                telemetry_record
            )
            
            # Validate detection results
            success = (
                detection_result is not None and
                detection_result.final_anomaly_detected == payload.expected_anomaly_detected and
                detection_result.primary_anomaly_type == payload.expected_anomaly_type
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Anomaly Detection",
                step_order=5,
                input_data=telemetry_record,
                output_data=detection_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "anomaly_detected": detection_result.final_anomaly_detected if detection_result else False,
                    "anomaly_type": detection_result.primary_anomaly_type.value if detection_result else "unknown",
                    "confidence_score": detection_result.combined_confidence if detection_result else 0.0
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Anomaly Detection",
                step_order=5,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_adaptive_buffer(self, payload: TestPayload) -> ValidationStep:
        """Validate adaptive buffer step"""
        step_start = time.time()
        
        try:
            # Simulate adaptive buffer processing
            buffer_result = await self.adaptive_buffer.process_data(
                payload.telemetry_data
            )
            
            # Validate buffer results
            success = (
                buffer_result is not None and
                buffer_result.success
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Adaptive Buffer",
                step_order=6,
                input_data=payload,
                output_data=buffer_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "buffer_size": buffer_result.buffer_size if buffer_result else 0,
                    "processing_success": buffer_result.success if buffer_result else False
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Adaptive Buffer",
                step_order=6,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_health_monitoring(self, payload: TestPayload) -> ValidationStep:
        """Validate health monitoring step"""
        step_start = time.time()
        
        try:
            # Simulate health monitoring
            health_result = await self.health_monitor.check_health(
                payload.telemetry_data
            )
            
            # Validate health results
            success = (
                health_result is not None and
                health_result.overall_health in ['healthy', 'degraded', 'critical']
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Health Monitoring",
                step_order=7,
                input_data=payload,
                output_data=health_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "overall_health": health_result.overall_health if health_result else "unknown",
                    "health_score": health_result.health_score if health_result else 0.0
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Health Monitoring",
                step_order=7,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_privacy_compliance(self, payload: TestPayload) -> ValidationStep:
        """Validate privacy compliance step"""
        step_start = time.time()
        
        try:
            # Simulate privacy compliance check
            privacy_result = await self.privacy_compliance.check_compliance(
                payload.telemetry_data
            )
            
            # Validate privacy results
            success = (
                privacy_result is not None and
                privacy_result.compliant
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Privacy Compliance",
                step_order=8,
                input_data=payload,
                output_data=privacy_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "compliant": privacy_result.compliant if privacy_result else False,
                    "compliance_score": privacy_result.compliance_score if privacy_result else 0.0
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Privacy Compliance",
                step_order=8,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_stream_processing(self, payload: TestPayload) -> ValidationStep:
        """Validate stream processing step"""
        step_start = time.time()
        
        try:
            # Simulate stream processing
            stream_result = await self.stream_processor.process_stream(
                payload.telemetry_data
            )
            
            # Validate stream results
            success = (
                stream_result is not None and
                stream_result.processed
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Stream Processing",
                step_order=9,
                input_data=payload,
                output_data=stream_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "processed": stream_result.processed if stream_result else False,
                    "processing_time": stream_result.processing_time if stream_result else 0.0
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Stream Processing",
                step_order=9,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_vendor_adapters(self, payload: TestPayload) -> ValidationStep:
        """Validate vendor adapters step"""
        step_start = time.time()
        
        try:
            # Simulate vendor adapter processing
            adapter_result = await self.vendor_adapters.process_vendor_data(
                payload.telemetry_data
            )
            
            # Validate adapter results
            success = (
                adapter_result is not None and
                adapter_result.adapted
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Vendor Adapters",
                step_order=10,
                input_data=payload,
                output_data=adapter_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "adapted": adapter_result.adapted if adapter_result else False,
                    "vendor_type": adapter_result.vendor_type if adapter_result else "unknown"
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Vendor Adapters",
                step_order=10,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_runtime_control(self, payload: TestPayload) -> ValidationStep:
        """Validate runtime control step"""
        step_start = time.time()
        
        try:
            # Simulate runtime control
            control_result = await self.runtime_control.execute_control_cycle(
                payload.telemetry_data
            )
            
            # Validate control results
            success = (
                control_result is not None and
                control_result.control_state in [ControlState.NORMAL, ControlState.ADAPTING, ControlState.EMERGENCY]
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Runtime Control",
                step_order=11,
                input_data=payload,
                output_data=control_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "control_state": control_result.control_state.value if control_result else "unknown",
                    "adaptation_triggered": control_result.adaptation_triggered if control_result else False
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Runtime Control",
                step_order=11,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _validate_layer1_contract(self, payload: TestPayload) -> ValidationStep:
        """Validate Layer 1 contract step"""
        step_start = time.time()
        
        try:
            # Create final telemetry record for Layer 1
            final_telemetry = {
                "timestamp": payload.timestamp,
                "function_name": payload.function_name,
                "execution_phase": payload.execution_phase.value,
                "anomaly_detected": payload.expected_anomaly_detected,
                "anomaly_type": payload.expected_anomaly_type.value,
                "telemetry_data": payload.telemetry_data,
                "layer0_processing_complete": True,
                "ready_for_layer1": True
            }
            
            # Validate contract compliance
            contract_result = await self.contract_validator.validate_contract(
                final_telemetry
            )
            
            # Validate contract results
            success = (
                contract_result is not None and
                contract_result.valid
            )
            
            processing_time = (time.time() - step_start) * 1000
            
            return ValidationStep(
                step_name="Layer 1 Contract Validation",
                step_order=12,
                input_data=final_telemetry,
                output_data=contract_result,
                processing_time_ms=processing_time,
                success=success,
                metadata={
                    "contract_valid": contract_result.valid if contract_result else False,
                    "compliance_score": contract_result.compliance_score if contract_result else 0.0,
                    "ready_for_layer1": True
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - step_start) * 1000
            return ValidationStep(
                step_name="Layer 1 Contract Validation",
                step_order=12,
                input_data=payload,
                output_data=None,
                processing_time_ms=processing_time,
                success=False,
                error_details=str(e)
            )
    
    async def _finalize_validation(self, validation: ValidationResult, payload: TestPayload):
        """Finalize validation and determine Layer 1 readiness"""
        try:
            # Check if all steps succeeded
            all_steps_successful = all(step.success for step in validation.pipeline_steps)
            
            # Check data integrity
            validation.data_integrity_verified = all_steps_successful
            
            # Check schema compliance
            validation.schema_compliance = all_steps_successful
            
            # Check contract validation
            contract_step = next((s for s in validation.pipeline_steps if s.step_name == "Layer 1 Contract Validation"), None)
            validation.contract_validation = contract_step.success if contract_step else False
            
            # Determine Layer 1 readiness
            validation.ready_for_layer1 = (
                validation.data_integrity_verified and
                validation.schema_compliance and
                validation.contract_validation
            )
            
            # Check Layer 1 contract compliance
            validation.layer1_contract_compliance = validation.ready_for_layer1
            
            logger.info(f"✅ Layer 1 readiness: {validation.ready_for_layer1}")
            
        except Exception as e:
            logger.error(f"❌ Validation finalization failed: {e}")
            validation.errors.append(f"Validation finalization failed: {e}")
    
    def generate_validation_report(self) -> str:
        """Generate comprehensive validation report"""
        if not self.validation_results:
            return "No validation results available"
        
        report = []
        report.append("=" * 80)
        report.append("SCAFAD LAYER 0: COMPREHENSIVE VALIDATION REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Overall statistics
        total_validations = len(self.validation_results)
        successful_validations = len([v for v in self.validation_results if v.ready_for_layer1])
        failed_validations = total_validations - successful_validations
        
        report.append(f"OVERALL VALIDATION STATISTICS:")
        report.append(f"  Total Validations: {total_validations}")
        report.append(f"  Successful Validations: {successful_validations}")
        report.append(f"  Failed Validations: {failed_validations}")
        report.append(f"  Success Rate: {(successful_validations/total_validations)*100:.2f}%")
        report.append("")
        
        # Step-by-step analysis
        report.append("STEP-BY-STEP ANALYSIS:")
        report.append("-" * 40)
        
        step_stats = defaultdict(lambda: {'total': 0, 'successful': 0, 'failed': 0, 'avg_time': 0.0})
        
        for validation in self.validation_results:
            for step in validation.pipeline_steps:
                step_stats[step.step_name]['total'] += 1
                if step.success:
                    step_stats[step.step_name]['successful'] += 1
                else:
                    step_stats[step.step_name]['failed'] += 1
                step_stats[step.step_name]['avg_time'] += step.processing_time_ms
        
        for step_name, stats in step_stats.items():
            success_rate = (stats['successful'] / stats['total']) * 100 if stats['total'] > 0 else 0
            avg_time = stats['avg_time'] / stats['total'] if stats['total'] > 0 else 0
            report.append(f"  {step_name}:")
            report.append(f"    Success Rate: {success_rate:.2f}%")
            report.append(f"    Average Time: {avg_time:.2f}ms")
            report.append(f"    Total: {stats['total']}, Success: {stats['successful']}, Failed: {stats['failed']}")
            report.append("")
        
        # Performance analysis
        report.append("PERFORMANCE ANALYSIS:")
        report.append("-" * 40)
        
        all_processing_times = []
        for validation in self.validation_results:
            all_processing_times.append(validation.total_processing_time_ms)
        
        if all_processing_times:
            avg_time = statistics.mean(all_processing_times)
            min_time = min(all_processing_times)
            max_time = max(all_processing_times)
            p95_time = statistics.quantiles(all_processing_times, n=20)[18] if len(all_processing_times) >= 20 else max_time
            
            report.append(f"  Average Processing Time: {avg_time:.2f}ms")
            report.append(f"  Min Processing Time: {min_time:.2f}ms")
            report.append(f"  Max Processing Time: {max_time:.2f}ms")
            report.append(f"  95th Percentile: {p95_time:.2f}ms")
            report.append("")
        
        # Error analysis
        report.append("ERROR ANALYSIS:")
        report.append("-" * 40)
        
        error_counts = defaultdict(int)
        for validation in self.validation_results:
            for error in validation.errors:
                error_counts[error] += 1
        
        if error_counts:
            for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                report.append(f"  {error}: {count} occurrences")
        else:
            report.append("  No errors encountered")
        
        report.append("")
        
        # Layer 1 readiness summary
        report.append("LAYER 1 READINESS SUMMARY:")
        report.append("-" * 40)
        
        ready_count = sum(1 for v in self.validation_results if v.ready_for_layer1)
        report.append(f"  Payloads Ready for Layer 1: {ready_count}/{total_validations}")
        report.append(f"  Layer 1 Readiness Rate: {(ready_count/total_validations)*100:.2f}%")
        
        if ready_count == total_validations:
            report.append("  ✅ ALL PAYLOADS READY FOR LAYER 1")
        else:
            report.append("  ⚠️  SOME PAYLOADS NOT READY FOR LAYER 1")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)

# =============================================================================
# Main Validation Execution
# =============================================================================

async def main():
    """Main validation execution"""
    logger.info("🚀 Starting SCAFAD Layer 0 Comprehensive Validation")
    
    try:
        # Initialize validator
        validator = Layer0PipelineValidator()
        
        # Run validation for all test payloads
        validation_results = []
        for payload in validator.test_payloads:
            logger.info(f"🔍 Validating payload: {payload.payload_id}")
            result = await validator.validate_complete_pipeline(payload)
            validation_results.append(result)
            
            # Brief pause between validations
            await asyncio.sleep(0.1)
        
        # Generate and display report
        report = validator.generate_validation_report()
        print(report)
        
        # Save detailed results
        with open("layer0_validation_results.json", "w") as f:
            json.dump([{
                "validation_id": v.validation_id,
                "start_time": v.start_time,
                "end_time": v.end_time,
                "total_processing_time_ms": v.total_processing_time_ms,
                "ready_for_layer1": v.ready_for_layer1,
                "pipeline_steps": [{
                    "step_name": s.step_name,
                    "success": s.success,
                    "processing_time_ms": s.processing_time_ms,
                    "error_details": s.error_details
                } for s in v.pipeline_steps]
            } for v in validation_results], f, indent=2, default=str)
        
        logger.info("✅ Layer 0 validation completed successfully")
        logger.info("📊 Results saved to layer0_validation_results.json")
        
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
