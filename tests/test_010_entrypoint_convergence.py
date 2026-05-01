"""
Test #010: single entrypoint converges on the canonical runtime.

After DL-039 the repository has exactly one Lambda entrypoint:

    scafad.runtime.lambda_handler.lambda_handler

This test asserts that this entrypoint:
  (a) constructs SCAFADCanonicalRuntime and calls process_event (not any legacy path),
  (b) returns statusCode 200 with a serialisable body on success,
  (c) returns statusCode 500 on unhandled exception without propagating,
  (d) passes the event through to process_event unchanged.

WP-1.1 / DL-019 / DL-039
"""

import json
import sys
import unittest
from unittest.mock import MagicMock, patch

import scafad.runtime.lambda_handler as lh


class _MockContext:
    aws_request_id = "entrypoint-test-010"
    function_name   = "entrypoint-function"
    function_version = "$LATEST"
    memory_limit_in_mb = 256

    def get_remaining_time_in_millis(self):
        return 30_000


def _make_mock_runtime(result_dict=None):
    if result_dict is None:
        result_dict = {
            "layer0_record":     {"event_id": "t010"},
            "adapted_record":    {"record_id": "ar-001"},
            "layer1_record":     {"trace_id": "tr-001"},
            "multilayer_result": {"layer2": {"anomaly_indicated": True}},
        }
    mock_result = MagicMock()
    mock_result.to_dict.return_value = result_dict
    instance = MagicMock()
    instance.process_event.return_value = mock_result
    cls = MagicMock(return_value=instance)
    return cls, instance


class TestSingleEntrypointConvergence(unittest.TestCase):
    """T-010 -- exactly one Lambda entrypoint, routes to SCAFADCanonicalRuntime."""

    def test_010a_canonical_runtime_constructed_once(self):
        """lambda_handler must instantiate SCAFADCanonicalRuntime exactly once."""
        cls_mock, instance_mock = _make_mock_runtime()
        event = {"event_id": "t010a", "function_id": "fn-test"}

        with patch.object(lh, "SCAFADCanonicalRuntime", cls_mock):
            lh.lambda_handler(event, _MockContext())

        cls_mock.assert_called_once_with()

    def test_010b_process_event_called_with_event(self):
        """process_event must receive the original event dict unchanged."""
        cls_mock, instance_mock = _make_mock_runtime()
        event = {"event_id": "t010b", "custom_field": "value"}

        with patch.object(lh, "SCAFADCanonicalRuntime", cls_mock):
            lh.lambda_handler(event, _MockContext())

        instance_mock.process_event.assert_called_once()
        actual_event = instance_mock.process_event.call_args[0][0]
        self.assertEqual(actual_event, event)

    def test_010c_response_status_200_on_success(self):
        """Successful invocation must return statusCode 200."""
        cls_mock, _ = _make_mock_runtime()

        with patch.object(lh, "SCAFADCanonicalRuntime", cls_mock):
            response = lh.lambda_handler({"event_id": "t010c"}, _MockContext())

        self.assertEqual(response["statusCode"], 200)

    def test_010d_response_body_is_json_serialisable(self):
        """Response body must be valid JSON."""
        cls_mock, _ = _make_mock_runtime()

        with patch.object(lh, "SCAFADCanonicalRuntime", cls_mock):
            response = lh.lambda_handler({"event_id": "t010d"}, _MockContext())

        body = json.loads(response["body"])
        self.assertIsInstance(body, dict)

    def test_010e_status_500_on_runtime_exception(self):
        """Unhandled exception in SCAFADCanonicalRuntime must yield statusCode 500."""
        cls_mock = MagicMock(side_effect=RuntimeError("boom"))

        with patch.object(lh, "SCAFADCanonicalRuntime", cls_mock):
            response = lh.lambda_handler({"event_id": "t010e"}, _MockContext())

        self.assertEqual(response["statusCode"], 500)
        body = json.loads(response["body"])
        self.assertIn("error", body)

    def test_010f_no_legacy_app_main_delegation(self):
        """lambda_handler must NOT call any app_main path."""
        cls_mock, _ = _make_mock_runtime()
        legacy_spy = MagicMock()

        with patch.object(lh, "SCAFADCanonicalRuntime", cls_mock), \
             patch.dict(sys.modules, {"app_main": MagicMock(lambda_handler=legacy_spy)}):
            lh.lambda_handler({"event_id": "t010f"}, _MockContext())

        legacy_spy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
