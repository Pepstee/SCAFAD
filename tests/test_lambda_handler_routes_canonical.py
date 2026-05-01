"""
T-010 — lambda_handler routes through SCAFADCanonicalRuntime
=============================================================

Permanent test. Asserts that scafad.runtime.lambda_handler.lambda_handler
constructs SCAFADCanonicalRuntime and delegates to process_event — never to
the legacy app_main path.

WP-1.1 / DL-019 / DL-020 / DL-039
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

import scafad.runtime.lambda_handler as lh


class MockContext:
    """Minimal AWS Lambda context stub."""

    function_name = "scafad-test"
    memory_limit_in_mb = 512
    invoked_function_arn = (
        "arn:aws:lambda:eu-west-1:000000000000:function:scafad-test"
    )
    aws_request_id = "test-request-id"


def _make_mock_runtime():
    """Return a (cls_mock, instance_mock) pair with a plausible process_event result."""
    mock_result = MagicMock()
    mock_result.to_dict.return_value = {
        "layer0_record": {},
        "adapted_record": {},
        "layer1_record": {},
        "multilayer_result": {},
    }
    instance = MagicMock()
    instance.process_event.return_value = mock_result
    cls = MagicMock(return_value=instance)
    return cls, instance


class TestLambdaHandlerRoutesCanonical(unittest.TestCase):
    """Assert that the entrypoint delegates exclusively to SCAFADCanonicalRuntime."""

    def test_runtime_constructed_and_process_event_called(self):
        """SCAFADCanonicalRuntime must be constructed and process_event invoked."""
        cls_mock, instance_mock = _make_mock_runtime()
        event = {"event_id": "t010", "function_id": "fn-test"}

        with patch.object(lh, "SCAFADCanonicalRuntime", cls_mock):
            lh.lambda_handler(event, MockContext())

        cls_mock.assert_called_once()
        instance_mock.process_event.assert_called_once()
        # Event dict must be the first positional argument
        actual_event = instance_mock.process_event.call_args[0][0]
        self.assertEqual(actual_event, event)

    def test_legacy_app_main_not_called(self):
        """lambda_handler must NOT delegate to app_main.lambda_handler."""
        cls_mock, _ = _make_mock_runtime()
        legacy_spy = MagicMock()

        with patch.object(lh, "SCAFADCanonicalRuntime", cls_mock), \
             patch.dict(sys.modules, {"app_main": MagicMock(lambda_handler=legacy_spy)}):
            lh.lambda_handler({"event_id": "t010-legacy"}, MockContext())

        legacy_spy.assert_not_called()

    def test_response_contains_status_code_200(self):
        """Handler must return a dict with statusCode 200 on success."""
        cls_mock, _ = _make_mock_runtime()

        with patch.object(lh, "SCAFADCanonicalRuntime", cls_mock):
            response = lh.lambda_handler({"event_id": "t010-resp"}, MockContext())

        self.assertIsInstance(response, dict)
        self.assertIn("statusCode", response)
        self.assertEqual(response["statusCode"], 200)

    def test_analyst_label_is_forwarded_to_runtime(self):
        """Handler must thread analyst feedback through to the runtime."""
        cls_mock, instance_mock = _make_mock_runtime()
        event = {
            "event_id": "t010-layer6",
            "function_id": "fn-layer6",
            "analyst_label": "confirmed",
        }

        with patch.object(lh, "SCAFADCanonicalRuntime", cls_mock):
            lh.lambda_handler(event, MockContext())

        cls_mock.assert_called_once()
        instance_mock.process_event.assert_called_once_with(
            event,
            analyst_label="confirmed",
        )


if __name__ == "__main__":
    unittest.main()
