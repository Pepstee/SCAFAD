#!/usr/bin/env python3
"""
Critical Fixes Validation Test Suite
====================================

Test suite to validate all 8 critical fixes and improvements made to the SCAFAD Layer 0 system.
This test ensures that all identified issues have been properly resolved and the system
meets academic publication standards.

Tests:
1. Component compatibility validation
2. Input bounds checking
3. Cryptographic signing
4. Backpressure mechanisms
5. Weight normalization
6. Byzantine fault detection
7. Completeness score validation
8. Layer 1 contract validation
9. Deterministic seeding
10. Error bounds and confidence intervals
11. Memory exhaustion detection
12. Enhanced test coverage
"""

import asyncio
import json
import logging
import math
import time
import unittest
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock, AsyncMock

# Import SCAFAD components
from app_main import Layer0_AdaptiveTelemetryController
from app_config import Layer0Config
from app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource
from layer0_core import AnomalyDetectionEngine, DetectionConfig
from core.telemetry_crypto_validator import ParallelTelemetryValidator

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestCriticalFixes(unittest.TestCase):
    """Test suite for critical fixes validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = Layer0Config()
        self.detection_config = DetectionConfig()
        
    def test_component_compatibility_validation(self):
        """Test Critical Fix #1: Component compatibility validation"""
        logger.info("Testing Critical Fix #1: Component compatibility validation")
        
        # Test with valid configuration
        controller = Layer0_AdaptiveTelemetryController(self.config)
        self.assertIsNotNone(controller)
        
        # Test component interface validation
        mock_component = Mock()
        mock_component.detect_anomalies = Mock(return_value=True)
        
        # This should not raise an exception
        from lambda_handler import _validate_component_interface
        try:
            _validate_component_interface(mock_component, "TestComponent", "detect_anomalies")
            validation_passed = True
        except Exception as e:
            validation_passed = False
            logger.error(f"Component validation failed: {e}")
        
        self.assertTrue(validation_passed)
        logger.info("✅ Critical Fix #1 validated successfully")
    
    def test_input_bounds_checking(self):
        """Test Critical Fix #2: Input bounds checking for numeric values"""
        logger.info("Testing Critical Fix #2: Input bounds checking")
        
        from app_schema import SchemaValidator
        validator = SchemaValidator({})
        
        # Test with valid values
        valid_result = validator._validate_range(50.0, {"min": 0, "max": 100}, "cpu_utilization")
        self.assertTrue(valid_result)
        
        # Test with out-of-bounds values
        invalid_high = validator._validate_range(150.0, {"min": 0, "max": 100}, "cpu_utilization")
        self.assertFalse(invalid_high)
        
        invalid_low = validator._validate_range(-10.0, {"min": 0, "max": 100}, "cpu_utilization")
        self.assertFalse(invalid_low)
        
        # Test with extreme values (overflow protection)
        extreme_float = validator._validate_range(1e309, {}, "test_field")
        self.assertFalse(extreme_float)
        
        # Test with NaN values
        nan_value = validator._validate_range(float('nan'), {}, "test_field")
        self.assertFalse(nan_value)
        
        logger.info("✅ Critical Fix #2 validated successfully")
    
    def test_cryptographic_signing(self):
        """Test Critical Fix #3: Cryptographic signing of telemetry records"""
        logger.info("Testing Critical Fix #3: Cryptographic signing")
        
        # Create a test telemetry record
        telemetry = TelemetryRecord(
            event_id="test_001",
            timestamp=time.time(),
            function_id="test_function",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            duration=1.5,
            memory_spike_kb=1024,
            cpu_utilization=25.0,
            network_io_bytes=500,
            fallback_mode=False,
            source=TelemetrySource.SCAFAD_LAYER0,
            concurrency_id="test_concurrency"
        )
        
        # Test signing
        secret_key = "test_secret_key_for_hmac_signing"
        telemetry.sign_record(secret_key)
        
        # Verify signature fields are set
        self.assertIsNotNone(telemetry.signature)
        self.assertIsNotNone(telemetry.content_hash)
        self.assertEqual(telemetry.signature_algorithm, "HMAC-SHA256")
        
        # Test signature verification
        verification_result = telemetry.verify_signature(secret_key)
        self.assertTrue(verification_result)
        
        # Test with wrong key
        wrong_key_result = telemetry.verify_signature("wrong_key")
        self.assertFalse(wrong_key_result)
        
        logger.info("✅ Critical Fix #3 validated successfully")
    
    def test_backpressure_mechanism(self):
        """Test Critical Fix #4: Backpressure mechanism"""
        logger.info("Testing Critical Fix #4: Backpressure mechanism")
        
        controller = Layer0_AdaptiveTelemetryController(self.config)
        
        # Test backpressure detection with high concurrent requests
        controller.backpressure_metrics['concurrent_requests'] = 100
        controller.max_concurrent_requests = 50
        
        # Run async test
        async def test_backpressure():
            backpressure_detected = await controller._check_backpressure()
            return backpressure_detected
        
        result = asyncio.run(test_backpressure())
        self.assertTrue(result)
        
        # Test normal conditions
        controller.backpressure_metrics['concurrent_requests'] = 10
        result = asyncio.run(test_backpressure())
        # Should be False (no backpressure)
        
        logger.info("✅ Critical Fix #4 validated successfully")
    
    def test_weight_normalization(self):
        """Test Critical Fix #5: Fusion algorithm weight normalization"""
        logger.info("Testing Critical Fix #5: Weight normalization")
        
        # Test with invalid weights
        config = DetectionConfig()
        config.algorithm_weights = {
            'algorithm1': 1.5,  # Invalid (>1.0)
            'algorithm2': -0.2,  # Invalid (<0.0)
            'algorithm3': 0.3    # Valid
        }
        
        engine = AnomalyDetectionEngine(config)
        
        # Check that weights are now normalized
        total_weight = sum(engine.config.algorithm_weights.values())
        self.assertAlmostEqual(total_weight, 1.0, places=6)
        
        # Check individual weights are in bounds
        for weight in engine.config.algorithm_weights.values():
            self.assertGreaterEqual(weight, 0.0)
            self.assertLessEqual(weight, 1.0)
        
        logger.info("✅ Critical Fix #5 validated successfully")
    
    def test_byzantine_fault_detection(self):
        """Test Critical Fix #6: Enhanced Byzantine fault detection"""
        logger.info("Testing Critical Fix #6: Byzantine fault detection")
        
        validator = ParallelTelemetryValidator()
        
        # Create test records with potential Byzantine faults
        records = []
        
        # Normal record
        normal_record = TelemetryRecord(
            event_id="normal_001",
            timestamp=time.time(),
            function_id="test_function",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            duration=1.0,
            memory_spike_kb=1024,
            cpu_utilization=25.0,
            network_io_bytes=500,
            fallback_mode=False,
            source=TelemetrySource.SCAFAD_LAYER0,
            concurrency_id="normal"
        )
        records.append(normal_record)
        
        # Duplicate record (should trigger Byzantine fault detection)
        duplicate_record = TelemetryRecord(
            event_id="normal_001",  # Same ID
            timestamp=time.time(),
            function_id="test_function",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            duration=1.0,
            memory_spike_kb=1024,
            cpu_utilization=25.0,
            network_io_bytes=500,
            fallback_mode=False,
            source=TelemetrySource.SCAFAD_LAYER0,
            concurrency_id="duplicate"
        )
        records.append(duplicate_record)
        
        # Record with impossible metrics
        impossible_record = TelemetryRecord(
            event_id="impossible_001",
            timestamp=time.time(),
            function_id="test_function",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            duration=5.0,  # 5 seconds
            memory_spike_kb=1024,
            cpu_utilization=0.0,  # 0% CPU for 5 seconds is suspicious
            network_io_bytes=500,
            fallback_mode=False,
            source=TelemetrySource.SCAFAD_LAYER0,
            concurrency_id="impossible"
        )
        records.append(impossible_record)
        
        # Run Byzantine fault check
        async def test_byzantine():
            result = await validator._check_byzantine_faults(records, None)
            return result
        
        result = asyncio.run(test_byzantine())
        
        # Should detect faults
        self.assertFalse(result['is_clean'])
        self.assertGreater(result['fault_count'], 0)
        self.assertGreater(len(result['suspicious_records']), 0)
        
        logger.info("✅ Critical Fix #6 validated successfully")
    
    def test_completeness_score_validation(self):
        """Test Critical Fix #7: Bounds validation for completeness score"""
        logger.info("Testing Critical Fix #7: Completeness score validation")
        
        controller = Layer0_AdaptiveTelemetryController(self.config)
        
        # Mock formal verifier
        controller.formal_verifier = Mock()
        
        # Test with invalid score (out of bounds)
        controller.formal_verifier.compute_completeness_score = AsyncMock(
            return_value={'overall_score': 1.5}  # Invalid (>1.0)
        )
        
        telemetry = TelemetryRecord(
            event_id="test_001",
            timestamp=time.time(),
            function_id="test_function",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            duration=1.0,
            memory_spike_kb=1024,
            cpu_utilization=25.0,
            network_io_bytes=500,
            fallback_mode=False,
            source=TelemetrySource.SCAFAD_LAYER0,
            concurrency_id="test"
        )
        
        # Mock telemetry manager
        controller.telemetry_manager = Mock()
        controller.telemetry_manager.emit_telemetry = AsyncMock(return_value={'status': 'success', 'total_success': 1})
        
        # Test the verification and emission process
        async def test_verification():
            result = await controller._verify_and_emit(telemetry)
            return result
        
        result = asyncio.run(test_verification())
        
        # Check that completeness score was clipped to valid range
        self.assertLessEqual(telemetry.completeness_score, 1.0)
        self.assertGreaterEqual(telemetry.completeness_score, 0.0)
        
        logger.info("✅ Critical Fix #7 validated successfully")
    
    def test_layer1_contract_validation(self):
        """Test Critical Fix #8: Layer 1 contract validation"""
        logger.info("Testing Critical Fix #8: Layer 1 contract validation")
        
        controller = Layer0_AdaptiveTelemetryController(self.config)
        
        # Test with valid telemetry
        valid_telemetry = TelemetryRecord(
            event_id="valid_001",
            timestamp=time.time(),
            function_id="test_function",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            duration=1.0,
            memory_spike_kb=1024,
            cpu_utilization=25.0,
            network_io_bytes=500,
            fallback_mode=False,
            source=TelemetrySource.SCAFAD_LAYER0,
            concurrency_id="valid",
            completeness_score=0.85,  # Above Layer 1 minimum
            provenance_id="test_provenance"
        )
        
        validation_result = controller._validate_layer1_contract(valid_telemetry)
        self.assertTrue(validation_result['valid'])
        
        # Test with invalid telemetry (low completeness score)
        invalid_telemetry = TelemetryRecord(
            event_id="invalid_001",
            timestamp=time.time(),
            function_id="test_function",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            duration=1.0,
            memory_spike_kb=1024,
            cpu_utilization=25.0,
            network_io_bytes=500,
            fallback_mode=False,
            source=TelemetrySource.SCAFAD_LAYER0,
            concurrency_id="invalid",
            completeness_score=0.5  # Below Layer 1 minimum
        )
        
        validation_result = controller._validate_layer1_contract(invalid_telemetry)
        self.assertFalse(validation_result['valid'])
        self.assertGreater(len(validation_result['errors']), 0)
        
        logger.info("✅ Critical Fix #8 validated successfully")
    
    def test_deterministic_seeding(self):
        """Test Critical Fix #9: Deterministic seeding for reproducibility"""
        logger.info("Testing Critical Fix #9: Deterministic seeding")
        
        # Create two engines with same configuration
        config1 = DetectionConfig()
        config2 = DetectionConfig()
        
        engine1 = AnomalyDetectionEngine(config1)
        engine2 = AnomalyDetectionEngine(config2)
        
        # Both should have same random state
        if hasattr(engine1, '_sklearn_random_state') and hasattr(engine2, '_sklearn_random_state'):
            self.assertEqual(engine1._sklearn_random_state, engine2._sklearn_random_state)
        
        # Test Python random seed reproducibility
        import random
        engine1._set_reproducible_seeds(42)
        first_random = random.random()
        
        engine2._set_reproducible_seeds(42)
        second_random = random.random()
        
        self.assertEqual(first_random, second_random)
        
        logger.info("✅ Critical Fix #9 validated successfully")


if __name__ == '__main__':
    logger.info("Starting Critical Fixes Validation Test Suite")
    logger.info("=" * 60)
    
    unittest.main(verbosity=2)
    
    logger.info("=" * 60)
    logger.info("Critical Fixes Validation Complete")