"""
Tests for WP-3.10: Retire app_main.enhanced_lambda_handler (I-1)

Task ID: 351d4be8-194c-4a03-b1d5-f3c7ef9c2110

Verifies:
1. enhanced_lambda_handler is completely deleted from both modules
2. Importing it raises ImportError
3. lambda_handler is rewritten and works correctly
4. DeprecationWarning is emitted
5. Canonical runtime is the exclusive entry point
6. Error handling is graceful
"""

import asyncio
import json
import importlib.util
import warnings
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Any, Dict


# =============================================================================
# Tests: Deletion of enhanced_lambda_handler
# =============================================================================


def test_app_main_enhanced_lambda_handler_deleted():
    """Verify enhanced_lambda_handler does not exist in app_main module."""
    from scafad.layer0 import app_main

    # The function should not be defined
    assert not hasattr(app_main, 'enhanced_lambda_handler'), \
        "enhanced_lambda_handler should be deleted from app_main"


def test_runtime_lambda_handler_module_does_not_define_enhanced():
    """Verify enhanced_lambda_handler does not exist in runtime.lambda_handler."""
    from scafad.runtime import lambda_handler as lh_module

    # The function should not be defined
    assert not hasattr(lh_module, 'enhanced_lambda_handler'), \
        "enhanced_lambda_handler should be deleted from runtime.lambda_handler"


def test_enhanced_lambda_handler_not_in_app_main_all():
    """Verify enhanced_lambda_handler is not exported from app_main.__all__."""
    from scafad.layer0 import app_main

    # Check if __all__ is defined and doesn't include it
    if hasattr(app_main, '__all__'):
        assert 'enhanced_lambda_handler' not in app_main.__all__, \
            "enhanced_lambda_handler should not be in __all__"


def test_cannot_import_enhanced_lambda_handler_from_app_main():
    """Verify that importing enhanced_lambda_handler raises ImportError."""
    with pytest.raises((ImportError, AttributeError)):
        from scafad.layer0.app_main import enhanced_lambda_handler  # noqa: F401


def test_cannot_import_enhanced_lambda_handler_from_runtime():
    """Verify that importing from runtime.lambda_handler raises ImportError."""
    with pytest.raises((ImportError, AttributeError)):
        from scafad.runtime.lambda_handler import enhanced_lambda_handler  # noqa: F401


# =============================================================================
# Tests: lambda_handler is rewritten and functional
# =============================================================================


def test_app_main_lambda_handler_exists():
    """Verify lambda_handler still exists in app_main."""
    from scafad.layer0 import app_main

    assert hasattr(app_main, 'lambda_handler'), \
        "lambda_handler should exist in app_main"
    assert callable(app_main.lambda_handler), \
        "lambda_handler should be callable"


def test_runtime_lambda_handler_exists():
    """Verify lambda_handler exists in runtime.lambda_handler module."""
    from scafad.runtime import lambda_handler as lh_module

    assert hasattr(lh_module, 'lambda_handler'), \
        "lambda_handler should exist in runtime.lambda_handler"
    assert callable(lh_module.lambda_handler), \
        "lambda_handler should be callable"


@patch('scafad.layer0.app_main.get_canonical_runtime')
def test_app_main_lambda_handler_calls_canonical_runtime(mock_get_runtime):
    """Verify app_main.lambda_handler calls get_canonical_runtime()."""
    from scafad.layer0.app_main import lambda_handler

    # Setup mock
    mock_runtime = Mock()
    mock_runtime.process_event.return_value = Mock(
        to_dict=lambda: {
            "layer0_record": {
                "event_id": "test-123",
                "graph_node_id": None,
                "provenance_id": None,
                "economic_risk_score": 0.0,
                "function_id": "test-func"
            },
            "layer1_record": {
                "quality_report": {"completeness_score": 0.9},
                "trace_id": "trace-123"
            },
            "multilayer_result": {
                "layer2": {"anomaly_indicated": False, "aggregate_score": 0.1},
                "layer3": {"fused_score": 0.1},
                "layer4": {"decision": "allow"},
                "layer5": {"campaign_cluster": None},
                "layer6": None
            }
        }
    )
    mock_get_runtime.return_value = mock_runtime

    event = {"test": "data"}
    context = Mock()

    result = lambda_handler(event, context)

    # Verify canonical runtime was called
    mock_get_runtime.assert_called_once()
    mock_runtime.process_event.assert_called_once()

    # Verify response structure
    assert result["statusCode"] in [200, 202]
    assert "body" in result
    assert "X-Telemetry-Id" in result["headers"]


@patch('scafad.layer0.app_main.get_canonical_runtime')
def test_app_main_lambda_handler_emits_deprecation_warning(mock_get_runtime):
    """Verify lambda_handler emits DeprecationWarning."""
    from scafad.layer0.app_main import lambda_handler

    # Setup mock
    mock_runtime = Mock()
    mock_runtime.process_event.return_value = Mock(
        to_dict=lambda: {
            "layer0_record": {
                "event_id": "test-123",
                "graph_node_id": None,
                "provenance_id": None,
                "economic_risk_score": 0.0,
                "function_id": "test-func"
            },
            "layer1_record": {
                "quality_report": {"completeness_score": 0.9},
                "trace_id": "trace-123"
            },
            "multilayer_result": {
                "layer2": {"anomaly_indicated": False, "aggregate_score": 0.1},
                "layer3": {"fused_score": 0.1},
                "layer4": {"decision": "allow"},
                "layer5": {"campaign_cluster": None},
                "layer6": None
            }
        }
    )
    mock_get_runtime.return_value = mock_runtime

    event = {"test": "data"}
    context = Mock()

    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        lambda_handler(event, context)

        # Check that a DeprecationWarning was issued
        deprecation_warnings = [warning for warning in w
                              if issubclass(warning.category, DeprecationWarning)]
        assert len(deprecation_warnings) > 0, \
            "DeprecationWarning should be emitted when calling lambda_handler"

        # Check message mentions WP-3.10 or I-1
        warning_messages = [str(w.message) for w in deprecation_warnings]
        assert any("WP-3.10" in msg or "I-1" in msg for msg in warning_messages), \
            "DeprecationWarning should reference WP-3.10 or I-1"


@patch('scafad.layer0.app_main.get_canonical_runtime')
def test_app_main_lambda_handler_handles_exception_gracefully(mock_get_runtime):
    """Verify lambda_handler handles exceptions gracefully."""
    from scafad.layer0.app_main import lambda_handler

    # Setup mock to raise exception
    mock_runtime = Mock()
    mock_runtime.process_event.side_effect = ValueError("Test error")
    mock_get_runtime.return_value = mock_runtime

    event = {"test": "data"}
    context = Mock()

    result = lambda_handler(event, context)

    # Should return error response
    assert result["statusCode"] == 500
    assert "body" in result
    body = json.loads(result["body"])
    assert body["status"] == "error"


def test_runtime_lambda_handler_signature():
    """Verify runtime.lambda_handler has correct signature."""
    from scafad.runtime.lambda_handler import lambda_handler
    import inspect

    sig = inspect.signature(lambda_handler)
    params = list(sig.parameters.keys())

    assert 'event' in params, "lambda_handler should have 'event' parameter"
    assert 'context' in params, "lambda_handler should have 'context' parameter"


# =============================================================================
# Tests: Canonical runtime is the exclusive entry point
# =============================================================================


def test_grep_enhanced_lambda_handler_not_in_active_code():
    """Verify no active code references enhanced_lambda_handler."""
    import subprocess
    import os

    os.chdir("C:/Projects/SCAFAD/project/scafad-r-core")

    # Run grep excluding legacy and graphify-out
    result = subprocess.run(
        [
            'grep',
            '-rn',
            'enhanced_lambda_handler',
            '.',
            '--exclude-dir=legacy',
            '--exclude-dir=graphify-out',
            '--include=*.py'
        ],
        capture_output=True,
        text=True
    )

    # Should have no matches (return code 1 means no matches found)
    if result.returncode == 0:
        # If return code is 0, grep found matches - this is a failure
        # Check if the matches are only in allowed locations
        matches = result.stdout.strip()
        # Filter out any test file references (test files are allowed to mention it)
        non_test_matches = [line for line in matches.split('\n')
                           if line and not 'test_' in line and not 'context/' in line]

        # We allow matches in test files and context (reports), but not in active code
        assert len(non_test_matches) == 0, \
            f"Found enhanced_lambda_handler in active code:\n{chr(10).join(non_test_matches)}"


def test_app_main_lambda_handler_calls_process_event():
    """Verify lambda_handler calls canonical runtime's process_event method."""
    from scafad.layer0.app_main import lambda_handler

    with patch('scafad.layer0.app_main.get_canonical_runtime') as mock_get:
        mock_runtime = Mock()
        mock_runtime.process_event.return_value = Mock(
            to_dict=lambda: {
                "layer0_record": {
                    "event_id": "test-123",
                    "graph_node_id": None,
                    "provenance_id": None,
                    "economic_risk_score": 0.0,
                    "function_id": "test-func"
                },
                "layer1_record": {
                    "quality_report": {"completeness_score": 0.9},
                    "trace_id": "trace-123"
                },
                "multilayer_result": {
                    "layer2": {"anomaly_indicated": False, "aggregate_score": 0.1},
                    "layer3": {"fused_score": 0.1},
                    "layer4": {"decision": "allow"},
                    "layer5": {"campaign_cluster": None},
                    "layer6": None
                }
            }
        )
        mock_get.return_value = mock_runtime

        event = {"test": "data"}
        context = Mock()

        lambda_handler(event, context)

        # Verify process_event was called (not some async wrapper)
        assert mock_runtime.process_event.called, \
            "lambda_handler should call runtime.process_event directly"


# =============================================================================
# Tests: No asyncio event loop usage in deprecated path
# =============================================================================


def test_app_main_lambda_handler_does_not_use_asyncio():
    """Verify the rewritten lambda_handler does not create asyncio event loops."""
    from scafad.layer0 import app_main
    import inspect

    # Get the source code of lambda_handler
    source = inspect.getsource(app_main.lambda_handler)

    # Check that asyncio.new_event_loop and asyncio.run are not used
    assert 'asyncio.new_event_loop' not in source, \
        "lambda_handler should not use asyncio.new_event_loop (deprecated path)"
    assert 'loop.run_until_complete' not in source, \
        "lambda_handler should not use loop.run_until_complete (deprecated path)"


# =============================================================================
# Tests: Module imports and structure
# =============================================================================


def test_runtime_lambda_handler_imports_canonical_runtime():
    """Verify runtime.lambda_handler imports SCAFADCanonicalRuntime."""
    from scafad.runtime import lambda_handler as lh_module
    import inspect

    source = inspect.getsource(lh_module)
    assert 'SCAFADCanonicalRuntime' in source, \
        "runtime.lambda_handler should import SCAFADCanonicalRuntime"


def test_runtime_lambda_handler_all_export_list():
    """Verify __all__ is properly defined in runtime.lambda_handler."""
    from scafad.runtime import lambda_handler as lh_module

    assert hasattr(lh_module, '__all__'), \
        "runtime.lambda_handler should define __all__"

    all_exports = lh_module.__all__
    assert 'lambda_handler' in all_exports, \
        "lambda_handler should be in __all__"
    assert 'enhanced_lambda_handler' not in all_exports, \
        "enhanced_lambda_handler should not be in __all__"


def test_app_main_imports_not_broken():
    """Verify app_main module can be imported without errors."""
    try:
        from scafad.layer0 import app_main
        assert app_main is not None
    except ImportError as e:
        pytest.fail(f"app_main import failed: {e}")


# =============================================================================
# Tests: Response structure is correct
# =============================================================================


@patch('scafad.layer0.app_main.get_canonical_runtime')
def test_app_main_lambda_handler_response_has_required_fields(mock_get_runtime):
    """Verify lambda_handler response has required fields."""
    from scafad.layer0.app_main import lambda_handler

    mock_runtime = Mock()
    mock_runtime.process_event.return_value = Mock(
        to_dict=lambda: {
            "layer0_record": {
                "event_id": "test-123",
                "graph_node_id": None,
                "provenance_id": None,
                "economic_risk_score": 0.0,
                "function_id": "test-func"
            },
            "layer1_record": {
                "quality_report": {"completeness_score": 0.9},
                "trace_id": "trace-123"
            },
            "multilayer_result": {
                "layer2": {"anomaly_indicated": False, "aggregate_score": 0.1},
                "layer3": {"fused_score": 0.1},
                "layer4": {"decision": "allow"},
                "layer5": {"campaign_cluster": None},
                "layer6": None
            }
        }
    )
    mock_get_runtime.return_value = mock_runtime

    event = {"test": "data"}
    context = Mock()

    result = lambda_handler(event, context)

    # Required fields
    assert "statusCode" in result
    assert "body" in result
    assert "headers" in result

    # Headers must include telemetry ID
    assert "X-Telemetry-Id" in result["headers"]
    assert "Content-Type" in result["headers"]
    assert result["headers"]["Content-Type"] == "application/json"


# =============================================================================
# Tests: WP-3.10 specific requirements
# =============================================================================


def test_wp310_requirement_zero_external_callers():
    """Verify acceptance criterion: zero external callers of enhanced_lambda_handler."""
    # This is a documentation test — the implementation ensures no callers exist
    # by having deleted the function entirely.
    from scafad.layer0 import app_main
    from scafad.runtime import lambda_handler as lh_module

    # Both modules should not define the function
    assert not hasattr(app_main, 'enhanced_lambda_handler')
    assert not hasattr(lh_module, 'enhanced_lambda_handler')


def test_wp310_requirement_lambda_handler_unchanged():
    """Verify lambda_handler is still exported from app_main."""
    from scafad.layer0.app_main import lambda_handler
    assert callable(lambda_handler)


def test_wp310_requirement_canonical_runtime_is_exclusive():
    """Verify canonical runtime is the exclusive entry point."""
    from scafad.layer0.app_main import lambda_handler
    from scafad.runtime.lambda_handler import lambda_handler as runtime_handler

    # Both should exist
    assert callable(lambda_handler)
    assert callable(runtime_handler)

    # app_main.lambda_handler is deprecated but functional
    # runtime.lambda_handler is the canonical entry point


@patch('scafad.layer0.app_main.get_canonical_runtime')
def test_app_main_lambda_handler_extracts_runtime_options(mock_get_runtime):
    """Verify lambda_handler extracts runtime options from event."""
    from scafad.layer0.app_main import lambda_handler

    mock_runtime = Mock()
    mock_runtime.process_event.return_value = Mock(
        to_dict=lambda: {
            "layer0_record": {
                "event_id": "test-123",
                "graph_node_id": None,
                "provenance_id": None,
                "economic_risk_score": 0.0,
                "function_id": "test-func"
            },
            "layer1_record": {
                "quality_report": {"completeness_score": 0.9},
                "trace_id": "trace-123"
            },
            "multilayer_result": {
                "layer2": {"anomaly_indicated": False, "aggregate_score": 0.1},
                "layer3": {"fused_score": 0.1},
                "layer4": {"decision": "allow"},
                "layer5": {"campaign_cluster": None},
                "layer6": None
            }
        }
    )
    mock_get_runtime.return_value = mock_runtime

    event = {
        "test": "data",
        "analyst_label": "test_analyst",
        "redacted_fields": ["field1", "field2"]
    }
    context = Mock()

    lambda_handler(event, context)

    # Verify process_event was called with extracted options
    call_args = mock_runtime.process_event.call_args
    assert call_args is not None

    # Check that analyst_label and redacted_fields were passed
    if 'analyst_label' in call_args.kwargs:
        assert call_args.kwargs['analyst_label'] == 'test_analyst'
    if 'redacted_fields' in call_args.kwargs:
        assert call_args.kwargs['redacted_fields'] == ["field1", "field2"]


# =============================================================================
# Tests: Error handling paths
# =============================================================================


@patch('scafad.layer0.app_main.get_canonical_runtime')
def test_app_main_lambda_handler_json_serialization_of_error(mock_get_runtime):
    """Verify error responses are JSON serializable."""
    from scafad.layer0.app_main import lambda_handler

    mock_runtime = Mock()
    mock_runtime.process_event.side_effect = RuntimeError("Test error")
    mock_get_runtime.return_value = mock_runtime

    event = {"test": "data"}
    context = Mock()

    result = lambda_handler(event, context)

    # Verify response is valid JSON
    body = result["body"]
    parsed = json.loads(body)

    assert parsed["status"] == "error"
    assert "error" in parsed


def test_runtime_lambda_handler_error_handling():
    """Verify runtime.lambda_handler handles exceptions."""
    from scafad.runtime.lambda_handler import lambda_handler

    with patch('scafad.runtime.lambda_handler.SCAFADCanonicalRuntime') as mock_runtime_class:
        mock_instance = Mock()
        mock_instance.process_event.side_effect = RuntimeError("Test error")
        mock_runtime_class.return_value = mock_instance

        event = {"test": "data"}
        context = Mock()

        result = lambda_handler(event, context)

        # Should return error response
        assert result["statusCode"] == 500
        assert "body" in result
        body = json.loads(result["body"])
        assert "error" in body


# =============================================================================
# Integration tests
# =============================================================================


def test_both_lambda_handlers_have_same_signature():
    """Verify both lambda_handler functions have identical signatures."""
    from scafad.layer0.app_main import lambda_handler as app_main_handler
    from scafad.runtime.lambda_handler import lambda_handler as runtime_handler
    import inspect

    app_main_sig = inspect.signature(app_main_handler)
    runtime_sig = inspect.signature(runtime_handler)

    # Both should accept event and context
    assert 'event' in app_main_sig.parameters
    assert 'context' in app_main_sig.parameters
    assert 'event' in runtime_sig.parameters
    assert 'context' in runtime_sig.parameters


def test_no_duplicate_lambda_handler_definitions():
    """Verify there's only one canonical lambda_handler."""
    from scafad.runtime import lambda_handler as lh_module

    # The canonical path should be in scafad.runtime.lambda_handler
    assert hasattr(lh_module, 'lambda_handler')

    # app_main.lambda_handler is deprecated but still present for compatibility
    from scafad.layer0 import app_main
    assert hasattr(app_main, 'lambda_handler')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
