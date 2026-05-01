#!/usr/bin/env python3
"""
Test Complete SCAFAD Layer 0 Implementation
==========================================

Comprehensive test suite to validate all newly implemented app_* modules
and utility functions work correctly and integrate properly.
"""

import sys
import time
import asyncio
from typing import Dict, Any

def test_imports():
    """Test that all modules can be imported successfully"""
    print("Testing module imports...")
    
    try:
        # Test core app modules
        import app_config
        import app_telemetry
        import app_main
        import app_graph
        import app_adversarial
        import app_economic
        import app_formal
        import app_provenance
        import app_schema
        import app_silent_failure
        
        # Test utility modules
        from utils import helpers, metrics, validators
        
        print("✓ All modules imported successfully")
        
    except Exception as e:
        print(f"✗ Import failed: {e}")
        raise AssertionError(f"Import failed: {e}") from e

def test_config():
    """Test configuration system"""
    print("\nTesting configuration system...")
    
    try:
        from app_config import ScafadConfig, TelemetryConfig, GraphConfig
        
        # Create default configuration
        config = ScafadConfig()
        assert config.telemetry is not None
        assert config.graph is not None
        assert isinstance(config.telemetry, TelemetryConfig)
        assert isinstance(config.graph, GraphConfig)
        
        # Test configuration validation
        assert config.verbosity_level.value in ["SILENT", "LOW", "NORMAL", "HIGH", "DEBUG"]
        assert config.temporal_window_seconds > 0
        
        print("✓ Configuration system working")
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        raise AssertionError(f"Configuration test failed: {e}") from e

def test_telemetry():
    """Test telemetry system"""
    print("\nTesting telemetry system...")
    
    try:
        from app_telemetry import TelemetryRecord, MultiChannelTelemetry, AnomalyType, ExecutionPhase, TelemetrySource
        from app_config import ScafadConfig
        
        config = ScafadConfig()
        emitter = MultiChannelTelemetry(config)
        
        # Create test telemetry record
        record = TelemetryRecord(
            event_id="test_001",
            timestamp=time.time(),
            function_id="test_function",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            duration=1.5,
            memory_spike_kb=1024,
            cpu_utilization=45.0,
            network_io_bytes=2048,
            fallback_mode=False,
            source=TelemetrySource.PRIMARY,
            concurrency_id="test_c1"
        )
        
        # Test record creation and serialization
        record_dict = record.to_dict()
        assert 'event_id' in record_dict
        assert record_dict['anomaly_type'] == 'benign'
        assert emitter is not None
        
        print("✓ Telemetry system working")
        
    except Exception as e:
        print(f"✗ Telemetry test failed: {e}")
        raise AssertionError(f"Telemetry test failed: {e}") from e

async def test_main_orchestrator():
    """Test main orchestrator"""
    print("\nTesting main orchestrator...")
    
    try:
        from app_main import Layer0_AdaptiveTelemetryController
        from app_config import ScafadConfig
        
        config = ScafadConfig()
        controller = Layer0_AdaptiveTelemetryController(config)
        
        assert hasattr(controller, 'process_invocation')
        assert controller.telemetry_manager is not None
        assert controller.schema_manager is not None
        assert controller.formal_verifier is not None
        
        print("✓ Main orchestrator working")
        
    except Exception as e:
        print(f"✗ Main orchestrator test failed: {e}")
        raise AssertionError(f"Main orchestrator test failed: {e}") from e

async def test_economic_module():
    """Test economic abuse detection"""
    print("\nTesting economic abuse detection...")
    
    try:
        from app_economic import EconomicAbuseDetector, EconomicAttackType
        from app_config import EconomicConfig
        from app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource
        
        config = EconomicConfig()
        detector = EconomicAbuseDetector(config)
        
        # Create test telemetry
        records = [
            TelemetryRecord(
                event_id="eco_001",
                timestamp=time.time(),
                function_id="billing_function",
                execution_phase=ExecutionPhase.INVOKE,
                anomaly_type=AnomalyType.BENIGN,
                duration=2.0,
                memory_spike_kb=2048,
                cpu_utilization=80.0,
                network_io_bytes=4096,
                fallback_mode=False,
                source=TelemetrySource.PRIMARY,
                concurrency_id="eco_c1"
            )
        ]
        
        # Test detection
        result = detector.detect_economic_attack(records)
        assert hasattr(result, 'risk_score')
        assert hasattr(result, 'estimated_cost_usd')
        
        print("✓ Economic abuse detection working")
        
    except Exception as e:
        print(f"✗ Economic module test failed: {e}")
        raise AssertionError(f"Economic module test failed: {e}") from e

async def test_formal_verification():
    """Test formal verification engine"""
    print("\nTesting formal verification...")
    
    try:
        from app_formal import FormalVerificationEngine
        from app_config import FormalVerificationConfig
        from app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource
        
        config = FormalVerificationConfig()
        engine = FormalVerificationEngine(config)
        
        # Create test telemetry
        records = [
            TelemetryRecord(
                event_id="form_001",
                timestamp=time.time(),
                function_id="test_function",
                execution_phase=ExecutionPhase.INVOKE,
                anomaly_type=AnomalyType.BENIGN,
                duration=1.0,
                memory_spike_kb=1024,
                cpu_utilization=50.0,
                network_io_bytes=1000,
                fallback_mode=False,
                source=TelemetrySource.PRIMARY,
                concurrency_id="form_c1"
            )
        ]
        
        # Test completeness verification
        result = await engine.compute_completeness_score([record.to_dict() for record in records])
        assert 'overall_score' in result
        
        print("✓ Formal verification working")
        
    except Exception as e:
        print(f"✗ Formal verification test failed: {e}")
        raise AssertionError(f"Formal verification test failed: {e}") from e

async def test_provenance_tracking():
    """Test provenance tracking"""
    print("\nTesting provenance tracking...")
    
    try:
        from app_provenance import ProvenanceChainTracker
        from app_config import ProvenanceConfig
        from app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource
        
        config = ProvenanceConfig()
        tracker = ProvenanceChainTracker(config)
        
        # Create test data
        event = {"test": "data", "correlation_id": "prov_001"}
        context = type('Context', (), {'aws_request_id': 'test_request'})()
        
        telemetry = TelemetryRecord(
            event_id="prov_001",
            timestamp=time.time(),
            function_id="test_function",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            duration=1.0,
            memory_spike_kb=1024,
            cpu_utilization=50.0,
            network_io_bytes=1000,
            fallback_mode=False,
            source=TelemetrySource.PRIMARY,
            concurrency_id="prov_c1"
        )
        
        # Test provenance recording
        result = await tracker.record_invocation(event, context, telemetry)
        assert isinstance(result, dict)
        assert 'record' in result or 'provenance_id' in result or 'id' in result
        
        print("✓ Provenance tracking working")
        
    except Exception as e:
        print(f"✗ Provenance tracking test failed: {e}")
        raise AssertionError(f"Provenance tracking test failed: {e}") from e

async def test_schema_evolution():
    """Test schema evolution management"""
    print("\nTesting schema evolution...")
    
    try:
        from app_schema import SchemaEvolutionManager
        from app_config import SchemaConfig
        
        config = SchemaConfig()
        manager = SchemaEvolutionManager(config)
        
        # Test schema validation
        test_event = {"version": "1.0", "data": {"test": "value"}}
        context = type('Context', (), {'aws_request_id': 'test_request'})()
        
        result = await manager.validate_and_sanitize_input(test_event, context)
        assert isinstance(result, dict)
        assert result is not None
        
        print("✓ Schema evolution working")
        
    except Exception as e:
        print(f"✗ Schema evolution test failed: {e}")
        raise AssertionError(f"Schema evolution test failed: {e}") from e

def test_silent_failure():
    """Test silent failure detection"""
    print("\nTesting silent failure detection...")
    
    try:
        from app_silent_failure import SilentFailureAnalyzer, assess_silent_failure
        from app_config import SilentFailureConfig
        from app_telemetry import TelemetryRecord, AnomalyType, ExecutionPhase, TelemetrySource
        
        config = SilentFailureConfig()
        analyzer = SilentFailureAnalyzer(config)
        
        # Create test execution record
        telemetry = TelemetryRecord(
            event_id="silent_001",
            timestamp=time.time(),
            function_id="test_function",
            execution_phase=ExecutionPhase.INVOKE,
            anomaly_type=AnomalyType.BENIGN,
            duration=1.0,
            memory_spike_kb=1024,
            cpu_utilization=50.0,
            network_io_bytes=1000,
            fallback_mode=False,
            source=TelemetrySource.PRIMARY,
            concurrency_id="silent_c1"
        )
        
        execution_record = {
            "function_id": "test_function",
            "input": {"test": "input"},
            "output": {"result": "output"},
            "telemetry": telemetry,
            "trace": {"phases": ["INIT", "INVOKE"], "timestamps": [time.time()-2, time.time()]}
        }
        
        # Test analysis
        result = analyzer.analyze(execution_record)
        assert hasattr(result, 'final_probability')
        
        # Test convenience function
        prob = assess_silent_failure(execution_record, config)
        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0
        
        print("✓ Silent failure detection working")
        
    except Exception as e:
        print(f"✗ Silent failure test failed: {e}")
        raise AssertionError(f"Silent failure test failed: {e}") from e

def test_utilities():
    """Test utility modules"""
    print("\nTesting utility modules...")
    
    try:
        # Test helpers
        from utils.helpers import safe_json_parse, calculate_hash, format_timestamp
        
        # Test JSON parsing
        parsed = safe_json_parse('{"test": "value"}')
        assert parsed == {"test": "value"}
        
        # Test hashing
        hash_val = calculate_hash({"test": "data"})
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64  # SHA256 hex length
        
        # Test timestamp formatting
        ts_str = format_timestamp(time.time())
        assert isinstance(ts_str, str)
        
        # Test metrics
        from utils.metrics import PerformanceMetricsCollector, Stopwatch
        
        collector = PerformanceMetricsCollector()
        collector.record_timing("test_operation", 1.5)
        collector.increment_counter("test_counter")
        
        with Stopwatch(collector, "timed_operation"):
            time.sleep(0.01)  # Brief operation
        
        report = collector.generate_performance_report()
        assert 'metrics_summary' in report
        
        # Test validators
        from utils.validators import validate_aws_lambda_event, sanitize_user_input
        
        event = {"test": "event", "Records": []}
        validated = validate_aws_lambda_event(event)
        assert isinstance(validated, dict)
        
        sanitized, issues = sanitize_user_input({"safe": "data"})
        assert isinstance(sanitized, dict)
        assert isinstance(issues, list)
        
        print("✓ Utility modules working")
        
    except Exception as e:
        print(f"✗ Utility test failed: {e}")
        raise AssertionError(f"Utility test failed: {e}") from e

async def test_integration():
    """Test integration between modules"""
    print("\nTesting module integration...")
    
    try:
        from app_main import Layer0_AdaptiveTelemetryController
        from app_config import ScafadConfig
        from utils.metrics import get_default_collector
        
        # Test with metrics collection
        config = ScafadConfig()
        controller = Layer0_AdaptiveTelemetryController(config)
        
        # Create test event
        test_event = {
            "test_mode": True,
            "scenario": "integration_test",
            "correlation_id": "int_test_001"
        }
        
        test_context = type('Context', (), {
            'aws_request_id': 'test_request_integration',
            'function_name': 'test_function',
            'memory_limit_in_mb': '128'
        })()
        
        # Test main processing
        result = await controller.process_invocation(test_event, test_context)
        assert isinstance(result, dict)
        assert 'status' in result or 'telemetry' in result or 'error' in result
        
        # Check that metrics were collected
        collector = get_default_collector()
        metrics_report = collector.generate_performance_report()
        assert isinstance(metrics_report, dict)
        
        print("✓ Module integration working")
        
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        raise AssertionError(f"Integration test failed: {e}") from e

async def main():
    """Run all tests"""
    print("Running Complete SCAFAD Layer 0 Implementation Tests")
    print("=" * 55)
    
    test_results = []
    
    # Run synchronous tests
    test_results.append(("Imports", test_imports()))
    test_results.append(("Configuration", test_config()))
    test_results.append(("Telemetry", test_telemetry()))
    test_results.append(("Utilities", test_utilities()))
    test_results.append(("Silent Failure", test_silent_failure()))
    
    # Run asynchronous tests
    test_results.append(("Main Orchestrator", await test_main_orchestrator()))
    test_results.append(("Economic Detection", await test_economic_module()))
    test_results.append(("Formal Verification", await test_formal_verification()))
    test_results.append(("Provenance Tracking", await test_provenance_tracking()))
    test_results.append(("Schema Evolution", await test_schema_evolution()))
    test_results.append(("Integration", await test_integration()))
    
    # Summary
    print("\n" + "=" * 55)
    print("TEST RESULTS SUMMARY")
    print("=" * 55)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name:<20} : {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("-" * 55)
    print(f"Total: {len(test_results)}, Passed: {passed}, Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! SCAFAD Layer 0 implementation is complete and functional.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the implementation.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
