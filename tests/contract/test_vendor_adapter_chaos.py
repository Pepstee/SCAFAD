"""
T-017 -- Vendor Adapter Chaos Contract Tests (WP-5.3)
=====================================================

Permanent contract test enforcing the blueprint invariant from
SCAFAD_MASTER_BLUEPRINT.md § 4.6:

    "the 5% random-failure injector is monkey-patched off in tests;
     must be hit in a dedicated chaos test"

Invariants enforced
-------------------
I-A  Forcing the random-failure injector to fire (probability → 1.0) causes
     the adapter to retry up to max_retries times before returning failure.
I-B  Exponential backoff fires on each retry; each successive delay is
     strictly greater than the previous (jitter zeroed for determinism).
I-C  The idempotency key in RequestMetadata is identical across all retry
     attempts — only metadata.attempt is mutated between retries.
I-D  After max retries are exhausted, send_with_retry returns a structured
     (False, dict) response; failures are never silently swallowed.
I-E  metrics.requests_retried equals max_retries after full exhaustion.
I-F  Exceptions raised inside send_telemetry are captured by logger.error
     and surfaced as a structured error response, not propagated or lost.

Blueprint reference
-------------------
SCAFAD_MASTER_BLUEPRINT.md § 4.6 vendor adapters note.

Decision Log
------------
DL-050: T-017 enters permanent contract set (WP-5.3, 2026-04-24).

Chaos methodology
-----------------
``random.random`` inside ``layer0.layer0_vendor_adapters`` is replaced with
a MagicMock whose ``side_effect`` interleaves failure-trigger values (0.0,
which is always < the 5% / 3% threshold) with zero-jitter values (0.5,
giving ``0.1 * (2*0.5 - 1) == 0``).  ``asyncio.sleep`` is replaced so
tests run in microseconds rather than seconds.

Call sequence for max_retries=3 (4 total attempts, 3 sleeps):
  random.random call positions:
    0 → failure check attempt-0   (returns 0.0 → injector fires)
    1 → jitter for delay-1        (returns 0.5 → zero jitter)
    2 → failure check attempt-1   (returns 0.0 → injector fires)
    3 → jitter for delay-2        (returns 0.5 → zero jitter)
    4 → failure check attempt-2   (returns 0.0 → injector fires)
    5 → jitter for delay-3        (returns 0.5 → zero jitter)
    6 → failure check attempt-3   (returns 0.0 → injector fires)
"""
from __future__ import annotations

import asyncio
import time
import uuid
import unittest
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Side-effect sequence constants
# ---------------------------------------------------------------------------

# For max_retries=3: 4 failure checks interleaved with 3 jitter calls
_FAIL_3 = [0.0, 0.5, 0.0, 0.5, 0.0, 0.5, 0.0]

# For max_retries=2: 3 failure checks interleaved with 2 jitter calls
_FAIL_2 = [0.0, 0.5, 0.0, 0.5, 0.0]

# For max_retries=1: 2 failure checks interleaved with 1 jitter call
_FAIL_1 = [0.0, 0.5, 0.0]


def _fail_side_effects(max_retries: int) -> List[float]:
    """Build the interleaved failure/jitter side_effect list for max_retries N.

    Pattern: [fail, jitter] * N, then one final fail (no trailing jitter
    because the last attempt has no subsequent sleep).
    """
    result: List[float] = []
    for _ in range(max_retries):
        result.append(0.0)   # triggers injector
        result.append(0.5)   # zero jitter
    result.append(0.0)       # final attempt — injector fires, no sleep follows
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cloudwatch_adapter(max_retries: int = 3):
    """CloudWatch adapter with fast exponential backoff suitable for testing."""
    from layer0.layer0_vendor_adapters import (
        CloudWatchAdapter, VendorConfig, ProviderType, RetryStrategy,
    )
    cfg = VendorConfig(
        provider=ProviderType.CLOUDWATCH,
        max_retries=max_retries,
        retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retry_delay_base_ms=100,
        retry_delay_max_ms=30_000,
        jitter_factor=0.1,
        supports_idempotency=True,
    )
    return CloudWatchAdapter(cfg)


def _make_datadog_adapter(max_retries: int = 3):
    """DataDog adapter with fast exponential backoff suitable for testing."""
    from layer0.layer0_vendor_adapters import (
        DataDogAdapter, VendorConfig, ProviderType, RetryStrategy,
    )
    cfg = VendorConfig(
        provider=ProviderType.DATADOG,
        max_retries=max_retries,
        retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retry_delay_base_ms=100,
        retry_delay_max_ms=30_000,
        jitter_factor=0.1,
        supports_idempotency=True,
    )
    return DataDogAdapter(cfg)


def _make_metadata(idempotency_key: Optional[str] = None) -> Any:
    """Minimal RequestMetadata for testing."""
    from layer0.layer0_vendor_adapters import RequestMetadata
    return RequestMetadata(
        request_id=str(uuid.uuid4()),
        timestamp=time.time(),
        attempt=1,
        idempotency_key=idempotency_key or str(uuid.uuid4()),
        payload_size_bytes=256,
    )


def _make_payload() -> Dict[str, Any]:
    return {"metric": "cpu_utilization", "value": 42.0, "tags": ["env:chaos"]}


def _make_backoff_adapter(max_retries: int = 3):
    """CloudWatch adapter whose send_telemetry always returns a retryable failure
    WITHOUT a ``retry_after`` hint.

    The CloudWatch injector response includes ``retry_after: 1000`` which makes
    ``max(exponential_delay, 1000)`` collapse all backoff sleeps to 1.0 s.
    For tests that need to observe the pure exponential curve, we replace
    ``send_telemetry`` with a minimal stub that returns INTERNAL_ERROR only.

    The adapter's ``_calculate_retry_delay`` logic is unchanged — only the
    response dict is simplified.
    """
    from layer0.layer0_vendor_adapters import (
        CloudWatchAdapter, VendorConfig, ProviderType, RetryStrategy, ErrorType,
    )
    cfg = VendorConfig(
        provider=ProviderType.CLOUDWATCH,
        max_retries=max_retries,
        retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retry_delay_base_ms=100,
        retry_delay_max_ms=30_000,
        jitter_factor=0.1,
        supports_idempotency=True,
    )
    adapter = CloudWatchAdapter(cfg)

    async def _always_fail_no_hint(
        payload: Dict[str, Any],
        metadata: Any,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Return INTERNAL_ERROR with no retry_after — pure backoff path."""
        return False, {"error": ErrorType.INTERNAL_ERROR.value, "message": "chaos-injected"}

    adapter.send_telemetry = _always_fail_no_hint  # type: ignore[method-assign]
    return adapter


def _run(coro):
    """Run a coroutine to completion inside a fresh event loop."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestVendorAdapterChaos(unittest.TestCase):
    """Chaos tests for vendor adapter random-failure injector.

    Each test patches ``random`` inside ``layer0.layer0_vendor_adapters`` so
    the random-failure injector fires with probability 1.0.  ``asyncio.sleep``
    is replaced with an ``AsyncMock`` so tests run in microseconds.
    """

    # ------------------------------------------------------------------ #
    # I-A: the retry loop is exercised when the injector fires             #
    # ------------------------------------------------------------------ #

    def test_cloudwatch_chaos_exhausts_all_retries(self) -> None:
        """CloudWatch: all max_retries attempts are made when injector fires.

        Invariant I-A — with the 5% injector forced to probability 1.0,
        every attempt returns INTERNAL_ERROR.  The adapter must exhaust
        all max_retries+1 attempts before returning failure.
        """
        adapter = _make_cloudwatch_adapter(max_retries=3)
        payload = _make_payload()
        meta = _make_metadata()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.side_effect = _FAIL_3

            success, response = _run(adapter.send_with_retry(payload, meta))

        # Filter out simulated latency sleeps (0.01 s) — keep only backoff sleeps (≥ 0.05 s)
        backoff_calls = [c for c in mock_sleep.call_args_list if c.args[0] >= 0.05]
        self.assertFalse(success, "All retries exhausted — must return False")
        self.assertEqual(
            len(backoff_calls), 3,
            f"asyncio.sleep must be called once per retry (3 backoff calls); "
            f"all calls: {[c.args[0] for c in mock_sleep.call_args_list]}",
        )

    def test_datadog_chaos_exhausts_all_retries(self) -> None:
        """DataDog: 3% injector forced to 1.0 exhausts all retries.

        DataDog injector fires at ``random.random() < 0.03``; returning 0.0
        guarantees SERVICE_UNAVAILABLE on every attempt.
        """
        adapter = _make_datadog_adapter(max_retries=3)
        payload = _make_payload()
        meta = _make_metadata()

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.side_effect = _FAIL_3

            success, _ = _run(adapter.send_with_retry(payload, meta))

        backoff_calls = [c for c in mock_sleep.call_args_list if c.args[0] >= 0.05]
        self.assertFalse(success)
        self.assertEqual(len(backoff_calls), 3)

    # ------------------------------------------------------------------ #
    # I-B: exponential backoff with jitter fires on each retry             #
    # ------------------------------------------------------------------ #

    def test_cloudwatch_chaos_backoff_delays_are_strictly_increasing(self) -> None:
        """Sleep delays increase strictly with each retry (exponential backoff).

        With jitter_factor=0.1 and random returning 0.5 for jitter calls,
        jitter = base * 0.1 * (2*0.5 - 1) = 0.  Pure exponential:
          retry-1 → 100 ms, retry-2 → 200 ms, retry-3 → 400 ms.

        Invariant I-B: each successive delay must be strictly greater than
        the previous.
        """
        # Use backoff adapter: send_telemetry stub returns INTERNAL_ERROR with NO
        # retry_after hint.  The real CloudWatch injector includes retry_after=1000 ms,
        # which collapses max(exponential, 1000) to 1.0 s for all retries and
        # prevents us from observing the exponential curve.
        adapter = _make_backoff_adapter(max_retries=3)
        payload = _make_payload()
        meta = _make_metadata()
        captured: List[float] = []

        async def _record_sleep(delay: float) -> None:
            captured.append(delay)

        # send_telemetry stub has no random.random call; only _calculate_retry_delay
        # calls random.random (for jitter).  Return 0.5 → zero jitter.
        with patch("asyncio.sleep", new=_record_sleep), \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.return_value = 0.5  # zero jitter: 0.1*(2*0.5-1)=0

            _run(adapter.send_with_retry(payload, meta))

        self.assertEqual(len(captured), 3, "Expected exactly 3 backoff sleep calls for 3 retries")

        for i in range(1, len(captured)):
            self.assertLess(
                captured[i - 1], captured[i],
                f"Delay[{i-1}]={captured[i-1]:.4f}s must be < Delay[{i}]={captured[i]:.4f}s",
            )

    def test_cloudwatch_chaos_backoff_doubling_ratio(self) -> None:
        """Each retry delay is approximately double the previous (±20% tolerance).

        Uses the backoff adapter stub (no retry_after override) to observe the
        pure exponential curve.  With zero jitter (random=0.5):
          delay_1 = 0.1 s, delay_2 = 0.2 s, delay_3 = 0.4 s.
        The ratio between consecutive delays must be close to 2.0.
        """
        adapter = _make_backoff_adapter(max_retries=3)
        payload = _make_payload()
        meta = _make_metadata()
        captured: List[float] = []

        async def _record_sleep(delay: float) -> None:
            captured.append(delay)

        with patch("asyncio.sleep", new=_record_sleep), \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.return_value = 0.5  # zero jitter

            _run(adapter.send_with_retry(payload, meta))

        self.assertEqual(len(captured), 3)

        ratio_1 = captured[1] / captured[0]
        ratio_2 = captured[2] / captured[1]
        self.assertAlmostEqual(
            ratio_1, 2.0, delta=0.4,
            msg=f"Retry-2/Retry-1 ratio={ratio_1:.2f}; expected ≈2.0 (±0.4)",
        )
        self.assertAlmostEqual(
            ratio_2, 2.0, delta=0.4,
            msg=f"Retry-3/Retry-2 ratio={ratio_2:.2f}; expected ≈2.0 (±0.4)",
        )

    def test_cloudwatch_chaos_backoff_delays_are_positive(self) -> None:
        """All retry delays are positive (max(0, ...) guard prevents negative waits).

        Worst-case jitter: random=0.0 → jitter = base*0.1*(2*0.0-1) = -0.1*base.
        Delay = max(0, base - 0.1*base) = 0.9*base > 0.
        """
        adapter = _make_backoff_adapter(max_retries=3)
        payload = _make_payload()
        meta = _make_metadata()
        captured: List[float] = []

        async def _record_sleep(delay: float) -> None:
            captured.append(delay)

        with patch("asyncio.sleep", new=_record_sleep), \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.return_value = 0.0   # worst-case negative jitter

            _run(adapter.send_with_retry(payload, meta))

        self.assertEqual(len(captured), 3)
        for i, delay in enumerate(captured):
            self.assertGreater(delay, 0.0, f"Retry-{i+1} delay must be positive, got {delay}")

    # ------------------------------------------------------------------ #
    # I-C: idempotency key is identical across all retry attempts          #
    # ------------------------------------------------------------------ #

    def test_cloudwatch_chaos_idempotency_key_unchanged_across_retries(self) -> None:
        """Idempotency key in metadata is identical on every retry attempt.

        send_with_retry passes the same RequestMetadata object to every call
        of send_telemetry.  Only metadata.attempt is mutated; idempotency_key
        must remain constant.  Invariant I-C.
        """
        adapter = _make_cloudwatch_adapter(max_retries=3)
        payload = _make_payload()
        fixed_key = "chaos-idem-cw-" + str(uuid.uuid4())
        meta = _make_metadata(idempotency_key=fixed_key)

        observed_keys: List[Optional[str]] = []
        original_send = adapter.send_telemetry

        async def _spy_send(
            p: Dict[str, Any],
            m: Any,
        ) -> Tuple[bool, Dict[str, Any]]:
            observed_keys.append(m.idempotency_key)
            return await original_send(p, m)

        adapter.send_telemetry = _spy_send  # type: ignore[method-assign]

        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.side_effect = _FAIL_3

            _run(adapter.send_with_retry(payload, meta))

        # 4 total calls: initial + 3 retries
        self.assertEqual(len(observed_keys), 4,
                         "Expected 4 send_telemetry calls (1 + 3 retries)")
        for i, key in enumerate(observed_keys):
            self.assertEqual(
                key, fixed_key,
                f"Attempt {i}: idempotency_key={key!r}; expected {fixed_key!r}",
            )

    def test_datadog_chaos_idempotency_key_unchanged_across_retries(self) -> None:
        """DataDog adapter also preserves idempotency key across retries."""
        adapter = _make_datadog_adapter(max_retries=2)
        payload = _make_payload()
        fixed_key = "chaos-idem-dd-" + str(uuid.uuid4())
        meta = _make_metadata(idempotency_key=fixed_key)

        observed_keys: List[Optional[str]] = []
        original_send = adapter.send_telemetry

        async def _spy(p: Dict[str, Any], m: Any) -> Tuple[bool, Dict[str, Any]]:
            observed_keys.append(m.idempotency_key)
            return await original_send(p, m)

        adapter.send_telemetry = _spy  # type: ignore[method-assign]

        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.side_effect = _FAIL_2

            _run(adapter.send_with_retry(payload, meta))

        # 3 total calls: initial + 2 retries
        self.assertEqual(len(observed_keys), 3)
        for i, key in enumerate(observed_keys):
            self.assertEqual(
                key, fixed_key,
                f"Attempt {i}: idempotency_key changed to {key!r}; expected {fixed_key!r}",
            )

    # ------------------------------------------------------------------ #
    # I-D: failures are never silently swallowed                           #
    # ------------------------------------------------------------------ #

    def test_cloudwatch_chaos_returns_structured_error_after_exhaustion(self) -> None:
        """After max retries, send_with_retry returns (False, dict) — not None.

        Callers receive a structured error response so they can decide whether
        to log, queue for re-emission, or alert.  Invariant I-D.
        """
        adapter = _make_cloudwatch_adapter(max_retries=3)
        payload = _make_payload()
        meta = _make_metadata()

        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.side_effect = _FAIL_3

            success, response = _run(adapter.send_with_retry(payload, meta))

        self.assertFalse(success)
        self.assertIsNotNone(response, "Response must not be None")
        self.assertIsInstance(response, dict, "Response must be a dict")
        self.assertIn("error", response, "Response must contain 'error' key")
        self.assertIsNotNone(response["error"], "error value must not be None")

    def test_datadog_chaos_error_response_identifies_failure_type(self) -> None:
        """DataDog failure response identifies the failure type explicitly.

        The DataDog injector returns SERVICE_UNAVAILABLE; after exhaustion the
        final response must carry that error type so callers can classify it.
        """
        adapter = _make_datadog_adapter(max_retries=3)
        payload = _make_payload()
        meta = _make_metadata()

        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.side_effect = _FAIL_3

            success, response = _run(adapter.send_with_retry(payload, meta))

        self.assertFalse(success)
        self.assertIsNotNone(response)
        self.assertIn("error", response)
        self.assertEqual(
            response["error"], "service_unavailable",
            f"Expected service_unavailable from DataDog injector; got {response['error']!r}",
        )

    def test_cloudwatch_chaos_exception_logged_and_response_returned(self) -> None:
        """Exceptions from send_telemetry are logged via logger.error.

        When send_telemetry raises (e.g. network hard failure), the exception
        must be: (a) captured by logger.error — not propagated, (b) reflected
        in a structured (False, dict) response.  Invariant I-F.
        """
        adapter = _make_cloudwatch_adapter(max_retries=2)
        payload = _make_payload()
        meta = _make_metadata()
        exc_msg = "simulated hard network failure"

        async def _exploding_send(
            p: Dict[str, Any],
            m: Any,
        ) -> Tuple[bool, Dict[str, Any]]:
            raise RuntimeError(exc_msg)

        adapter.send_telemetry = _exploding_send  # type: ignore[method-assign]

        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("layer0.layer0_vendor_adapters.logger") as mock_log:

            success, response = _run(adapter.send_with_retry(payload, meta))

        # Must not propagate — returns structured failure
        self.assertFalse(success)
        self.assertIsNotNone(response)
        self.assertIn("error", response)
        self.assertIn("message", response)
        self.assertIn(exc_msg, response["message"],
                      "Exception message must appear in response['message']")

        # Failure must be logged, not silently dropped
        self.assertTrue(
            mock_log.error.called,
            "logger.error must be called so the failure is observable",
        )
        all_error_calls = " ".join(str(c) for c in mock_log.error.call_args_list)
        self.assertTrue(
            exc_msg in all_error_calls or "cloudwatch" in all_error_calls.lower(),
            f"logger.error call should reference the failure; calls: {all_error_calls!r}",
        )

    # ------------------------------------------------------------------ #
    # I-E: metrics.requests_retried tracks every retry                     #
    # ------------------------------------------------------------------ #

    def test_cloudwatch_chaos_retry_metric_equals_max_retries(self) -> None:
        """metrics.requests_retried == max_retries after full exhaustion.

        The counter is incremented once per asyncio.sleep call (one per
        inter-retry wait).  With max_retries=3 and all attempts failing,
        the counter must reach exactly 3.  Invariant I-E.
        """
        adapter = _make_cloudwatch_adapter(max_retries=3)
        payload = _make_payload()
        meta = _make_metadata()

        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.side_effect = _FAIL_3

            _run(adapter.send_with_retry(payload, meta))

        self.assertEqual(
            adapter.metrics.requests_retried, 3,
            "requests_retried must equal max_retries (3) after full exhaustion",
        )

    def test_retry_metric_scales_with_configured_max_retries(self) -> None:
        """requests_retried is proportional to max_retries, not hard-coded."""
        for max_retries in (1, 2, 4):
            with self.subTest(max_retries=max_retries):
                adapter = _make_cloudwatch_adapter(max_retries=max_retries)
                payload = _make_payload()
                meta = _make_metadata()
                side_effects = _fail_side_effects(max_retries)

                with patch("asyncio.sleep", new_callable=AsyncMock), \
                     patch("layer0.layer0_vendor_adapters.random") as mock_rand:
                    mock_rand.random.side_effect = side_effects

                    _run(adapter.send_with_retry(payload, meta))

                self.assertEqual(
                    adapter.metrics.requests_retried, max_retries,
                    f"max_retries={max_retries}: requests_retried should be {max_retries}",
                )

    # ------------------------------------------------------------------ #
    # Blueprint invariant: comprehensive gate test                         #
    # ------------------------------------------------------------------ #

    def test_blueprint_vendor_adapter_chaos_invariant_fully_enforced(self) -> None:
        """This test IS the enforcement gate for SCAFAD_MASTER_BLUEPRINT.md § 4.6.

        Blueprint note: 'the 5% random-failure injector is monkey-patched off
        in tests; must be hit in a dedicated chaos test'.

        This single test verifies the complete chaos path in one place:
          1. Injector fires (random forced to 0.0) — real CloudWatchAdapter
          2. Retries execute (sleep called N times) — real CloudWatchAdapter
          3. Backoff increases strictly — backoff adapter (no retry_after override)
          4. Idempotency key consistent — real CloudWatchAdapter with spy
          5. Failure not swallowed (structured error returned) — real adapter
          6. Retry metric correct (requests_retried == max_retries) — real adapter

        If any assertion fails, the blueprint invariant is violated.
        """
        max_retries = 3

        # ------------------------------------------------------------------
        # Parts 1, 2, 4, 5, 6: use real CloudWatchAdapter with injector
        # ------------------------------------------------------------------
        adapter = _make_cloudwatch_adapter(max_retries=max_retries)
        payload = _make_payload()
        fixed_key = "blueprint-chaos-gate-" + str(uuid.uuid4())
        meta = _make_metadata(idempotency_key=fixed_key)

        observed_keys: List[Optional[str]] = []
        original_send = adapter.send_telemetry

        async def _spy_send(p: Dict[str, Any], m: Any) -> Tuple[bool, Dict[str, Any]]:
            observed_keys.append(m.idempotency_key)
            return await original_send(p, m)

        all_sleeps_injector: List[float] = []

        async def _record_sleep_injector(delay: float) -> None:
            all_sleeps_injector.append(delay)

        adapter.send_telemetry = _spy_send  # type: ignore[method-assign]

        with patch("asyncio.sleep", new=_record_sleep_injector), \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand:
            mock_rand.random.side_effect = _FAIL_3
            success, response = _run(adapter.send_with_retry(payload, meta))

        # Filter latency sleeps (0.01 s in send_telemetry) — keep backoff (≥ 0.05 s)
        injector_backoff_sleeps = [d for d in all_sleeps_injector if d >= 0.05]

        # 1. Injector fired → final failure
        self.assertFalse(success, "Blueprint invariant: injector must cause failure")

        # 2. Retries executed
        self.assertEqual(
            len(injector_backoff_sleeps), max_retries,
            f"Blueprint invariant: retry loop must execute {max_retries} times; "
            f"got {injector_backoff_sleeps}",
        )

        # 4. Idempotency key consistent
        self.assertEqual(
            len(observed_keys), max_retries + 1,
            "Blueprint invariant: send_telemetry must be called max_retries+1 times",
        )
        for i, key in enumerate(observed_keys):
            self.assertEqual(
                key, fixed_key,
                f"Blueprint invariant: idempotency_key changed at attempt {i}",
            )

        # 5. Failure not swallowed
        self.assertIsNotNone(response, "Blueprint invariant: response must not be None")
        self.assertIn("error", response,
                      "Blueprint invariant: response must contain 'error' key")

        # 6. Retry metric
        self.assertEqual(
            adapter.metrics.requests_retried, max_retries,
            f"Blueprint invariant: requests_retried must be {max_retries}",
        )

        # ------------------------------------------------------------------
        # Part 3: verify backoff increases using the no-retry_after stub
        # ------------------------------------------------------------------
        backoff_adapter = _make_backoff_adapter(max_retries=max_retries)
        backoff_delays: List[float] = []

        async def _record_backoff(delay: float) -> None:
            backoff_delays.append(delay)

        with patch("asyncio.sleep", new=_record_backoff), \
             patch("layer0.layer0_vendor_adapters.random") as mock_rand2:
            mock_rand2.random.return_value = 0.5   # zero jitter
            _run(backoff_adapter.send_with_retry(_make_payload(), _make_metadata()))

        self.assertEqual(len(backoff_delays), max_retries,
                         "Blueprint invariant: backoff sleep must fire on each retry")
        for i in range(1, len(backoff_delays)):
            self.assertLess(
                backoff_delays[i - 1], backoff_delays[i],
                f"Blueprint invariant: backoff must increase; "
                f"delay[{i-1}]={backoff_delays[i-1]:.4f}s >= delay[{i}]={backoff_delays[i]:.4f}s",
            )

        # 6. Retry metric
        self.assertEqual(
            adapter.metrics.requests_retried, max_retries,
            f"Blueprint invariant: requests_retried must be {max_retries}",
        )
