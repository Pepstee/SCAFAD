"""
T-011 — _emit_with_queue is a method of MultiChannelTelemetry
=============================================================

Permanent test. Asserts:
1. AST: _emit_with_queue is defined inside MultiChannelTelemetry class.
2. Behavioural: a normal-priority emission (priority < 8) calls _emit_with_queue,
   not _emit_immediate directly.

WP-1.3 / DL-022
"""

import ast
import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

RCORE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(RCORE_ROOT))
APP_TELEMETRY_PATH = RCORE_ROOT / "app_telemetry.py"


class TestEmitWithQueueAST(unittest.TestCase):
    """AST-level assertion: _emit_with_queue belongs to MultiChannelTelemetry."""

    def test_emit_with_queue_is_method_of_multichanneltelemetry(self):
        """_emit_with_queue must be defined inside MultiChannelTelemetry, not elsewhere."""
        with open(APP_TELEMETRY_PATH, encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)

        found_in_class = False
        wrong_class = None

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in ast.walk(node):
                    if (
                        isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and child.name == "_emit_with_queue"
                    ):
                        if node.name == "MultiChannelTelemetry":
                            found_in_class = True
                        else:
                            wrong_class = node.name

        self.assertIsNone(
            wrong_class,
            f"_emit_with_queue found in wrong class: {wrong_class}. "
            "It must be in MultiChannelTelemetry.",
        )
        self.assertTrue(
            found_in_class,
            "_emit_with_queue not found in MultiChannelTelemetry. "
            "It must be a method of that class.",
        )


class TestEmitWithQueueBehaviour(unittest.TestCase):
    """Behavioural assertion: normal-priority emissions go through _emit_with_queue."""

    def _make_telemetry(self, high_priority: bool):
        """Return a mock TelemetryRecord with get_emission_priority stubbed."""
        rec = MagicMock()
        rec.get_emission_priority.return_value = 9 if high_priority else 3
        rec.mark_emission_attempt = MagicMock()
        return rec

    def test_normal_priority_calls_emit_with_queue_not_emit_immediate(self):
        """For priority < 8, emit_telemetry must route through _emit_with_queue."""
        from app_config import get_default_config
        from app_telemetry import MultiChannelTelemetry

        config = get_default_config()
        mct = MultiChannelTelemetry(config)

        queue_spy = AsyncMock(return_value={})
        immediate_spy = AsyncMock(return_value={})

        async def run():
            with patch.object(mct, "_emit_with_queue", queue_spy), \
                 patch.object(mct, "_emit_immediate", immediate_spy):
                await mct.emit_telemetry(self._make_telemetry(high_priority=False))

        asyncio.run(run())

        queue_spy.assert_called_once()
        immediate_spy.assert_not_called()

    def test_high_priority_calls_emit_immediate_not_queue(self):
        """For priority >= 8, emit_telemetry must route through _emit_immediate."""
        from app_config import get_default_config
        from app_telemetry import MultiChannelTelemetry

        config = get_default_config()
        mct = MultiChannelTelemetry(config)

        queue_spy = AsyncMock(return_value={})
        immediate_spy = AsyncMock(return_value={})

        async def run():
            with patch.object(mct, "_emit_with_queue", queue_spy), \
                 patch.object(mct, "_emit_immediate", immediate_spy):
                await mct.emit_telemetry(self._make_telemetry(high_priority=True))

        asyncio.run(run())

        immediate_spy.assert_called_once()
        queue_spy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
