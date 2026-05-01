"""Demo seeder — populate the GUI store with detections from the real runtime.

Running this script (``python -m scafad.gui.backend.seed``) ingests roughly
``settings.seed_event_count`` synthetic events through
:class:`SCAFADCanonicalRuntime` and persists each result via
:class:`DetectionStore`.  A fresh checkout therefore renders a populated
Operations Dashboard immediately.

Phase 2 extends the seeder so a fresh ``make gui-dev`` also shows ~10 cases
across all four lifecycle states with attached detections, comments, and
lifecycle audit events.

The event mix is deliberately diverse:

* benign baseline traffic so trust fusion has reference points
* eight named anomaly archetypes (memory_spike, cpu_burst, network_anomaly,
  cold_start, economic_abuse, cascade_failure, security_anomaly,
  silent_failure)
* a small share of edge cases (oversized payloads, fallback mode, custom
  fields with PII to exercise L1 sanitisation)
"""

from __future__ import annotations

import argparse
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .config import GUISettings, get_settings
from .runtime_adapter import GUIRuntimeAdapter
from .store import (
    AlreadyAttached,
    DetectionStore,
    StoreError,
)
from .users import PRIMARY_ANALYST, SECONDARY_ANALYST


logger = logging.getLogger("scafad.gui.seed")


_FUNCTIONS = [
    "image_processor", "checkout_api", "auth_service", "data_etl",
    "billing_aggregator", "graphql_resolver", "notification_dispatch",
    "log_collector", "model_inference", "user_search",
]
_REGIONS = ["eu-west-1", "us-east-1", "us-west-2", "ap-southeast-1"]
_RUNTIMES = ["python3.11", "python3.10", "nodejs20.x", "go1.21"]


def _benign_event(seed_idx: int, rng: random.Random) -> Dict[str, Any]:
    return {
        "event_id": f"seed-benign-{seed_idx:05d}",
        "function_id": rng.choice(_FUNCTIONS),
        "anomaly": "benign",
        "execution_phase": "invoke",
        "duration": rng.uniform(0.05, 0.5),
        "memory_spike_kb": rng.randint(8_000, 32_000),
        "cpu_utilization": rng.uniform(15.0, 45.0),
        "network_io_bytes": rng.randint(1_024, 16_384),
        "region": rng.choice(_REGIONS),
        "runtime_version": rng.choice(_RUNTIMES),
    }


def _memory_spike(seed_idx: int, rng: random.Random) -> Dict[str, Any]:
    return {
        "event_id": f"seed-mem-{seed_idx:05d}",
        "function_id": rng.choice(_FUNCTIONS),
        "anomaly": "memory_spike",
        "execution_phase": "invoke",
        "duration": rng.uniform(0.6, 2.0),
        "memory_spike_kb": rng.randint(220_000, 320_000),
        "cpu_utilization": rng.uniform(70.0, 95.0),
        "network_io_bytes": rng.randint(2_048, 8_192),
        "region": rng.choice(_REGIONS),
        "runtime_version": rng.choice(_RUNTIMES),
        "custom_fields": {"memory_pages": 16, "swap_used": True},
    }


def _cpu_burst(seed_idx: int, rng: random.Random) -> Dict[str, Any]:
    return {
        "event_id": f"seed-cpu-{seed_idx:05d}",
        "function_id": rng.choice(_FUNCTIONS),
        "anomaly": "cpu_burst",
        "execution_phase": "invoke",
        "duration": rng.uniform(1.5, 4.0),
        "memory_spike_kb": rng.randint(20_000, 60_000),
        "cpu_utilization": rng.uniform(92.0, 99.5),
        "network_io_bytes": rng.randint(2_048, 8_192),
        "region": rng.choice(_REGIONS),
        "runtime_version": rng.choice(_RUNTIMES),
    }


def _network_anomaly(seed_idx: int, rng: random.Random) -> Dict[str, Any]:
    return {
        "event_id": f"seed-net-{seed_idx:05d}",
        "function_id": rng.choice(_FUNCTIONS),
        "anomaly": "network_anomaly",
        "execution_phase": "invoke",
        "duration": rng.uniform(0.8, 2.5),
        "memory_spike_kb": rng.randint(10_000, 50_000),
        "cpu_utilization": rng.uniform(40.0, 70.0),
        "network_io_bytes": rng.randint(2_000_000, 8_000_000),
        "region": rng.choice(_REGIONS),
        "runtime_version": rng.choice(_RUNTIMES),
    }


def _cold_start(seed_idx: int, rng: random.Random) -> Dict[str, Any]:
    return {
        "event_id": f"seed-cold-{seed_idx:05d}",
        "function_id": rng.choice(_FUNCTIONS),
        "anomaly": "cold_start",
        "execution_phase": "init",
        "duration": rng.uniform(2.5, 6.0),
        "memory_spike_kb": rng.randint(40_000, 90_000),
        "cpu_utilization": rng.uniform(55.0, 85.0),
        "network_io_bytes": rng.randint(1_024, 8_192),
        "region": rng.choice(_REGIONS),
        "runtime_version": rng.choice(_RUNTIMES),
    }


def _economic_abuse(seed_idx: int, rng: random.Random) -> Dict[str, Any]:
    return {
        "event_id": f"seed-econ-{seed_idx:05d}",
        "function_id": rng.choice(_FUNCTIONS),
        "anomaly": "economic_abuse",
        "execution_phase": "invoke",
        "duration": rng.uniform(8.0, 14.5),
        "memory_spike_kb": rng.randint(100_000, 200_000),
        "cpu_utilization": rng.uniform(85.0, 99.0),
        "network_io_bytes": rng.randint(500_000, 2_000_000),
        "region": rng.choice(_REGIONS),
        "runtime_version": rng.choice(_RUNTIMES),
        "economic_risk_score": rng.uniform(0.7, 0.95),
        "custom_fields": {"loop_iterations": rng.randint(5_000, 50_000)},
    }


def _cascade_failure(seed_idx: int, rng: random.Random) -> Dict[str, Any]:
    return {
        "event_id": f"seed-cascade-{seed_idx:05d}",
        "function_id": rng.choice(_FUNCTIONS),
        "anomaly": "cascade_failure",
        "execution_phase": "error",
        "duration": rng.uniform(0.1, 1.0),
        "memory_spike_kb": rng.randint(15_000, 60_000),
        "cpu_utilization": rng.uniform(40.0, 70.0),
        "network_io_bytes": rng.randint(8_192, 32_768),
        "region": rng.choice(_REGIONS),
        "runtime_version": rng.choice(_RUNTIMES),
        "fallback_mode": True,
        "silent_failure_probability": rng.uniform(0.6, 0.9),
    }


def _security_anomaly(seed_idx: int, rng: random.Random) -> Dict[str, Any]:
    return {
        "event_id": f"seed-sec-{seed_idx:05d}",
        "function_id": rng.choice(_FUNCTIONS),
        "anomaly": "security_anomaly",
        "execution_phase": "invoke",
        "duration": rng.uniform(0.4, 1.6),
        "memory_spike_kb": rng.randint(30_000, 80_000),
        "cpu_utilization": rng.uniform(60.0, 85.0),
        "network_io_bytes": rng.randint(64_000, 256_000),
        "region": rng.choice(_REGIONS),
        "runtime_version": rng.choice(_RUNTIMES),
        "adversarial_score": rng.uniform(0.6, 0.9),
        "custom_fields": {"email": "alert@example.com", "user_agent": "evilbot/1.0"},
    }


def _silent_failure(seed_idx: int, rng: random.Random) -> Dict[str, Any]:
    return {
        "event_id": f"seed-silent-{seed_idx:05d}",
        "function_id": rng.choice(_FUNCTIONS),
        "anomaly": "silent_failure",
        "execution_phase": "shutdown",
        "duration": rng.uniform(0.2, 0.6),
        "memory_spike_kb": rng.randint(8_000, 24_000),
        "cpu_utilization": rng.uniform(20.0, 35.0),
        "network_io_bytes": rng.randint(0, 256),
        "region": rng.choice(_REGIONS),
        "runtime_version": rng.choice(_RUNTIMES),
        "completeness_score": rng.uniform(0.2, 0.5),
        "data_quality_score": rng.uniform(0.3, 0.6),
    }


_GENERATORS = [
    (_benign_event, 0.55),
    (_memory_spike, 0.07),
    (_cpu_burst, 0.06),
    (_network_anomaly, 0.05),
    (_cold_start, 0.05),
    (_economic_abuse, 0.06),
    (_cascade_failure, 0.05),
    (_security_anomaly, 0.07),
    (_silent_failure, 0.04),
]


def _pick_generator(rng: random.Random):
    weights = [w for _, w in _GENERATORS]
    return rng.choices(_GENERATORS, weights=weights, k=1)[0][0]


def generate_event(seed_idx: int, rng: random.Random) -> Dict[str, Any]:
    """Return one synthetic event whose anomaly distribution matches the demo mix."""

    return _pick_generator(rng)(seed_idx, rng)


_CASE_PRESETS: List[Dict[str, Any]] = [
    {
        "title": "Memory leak in image_processor",
        "status": "open",
        "assignee": PRIMARY_ANALYST.id,
        "anomaly_filter": "memory_spike",
        "max_attached": 4,
        "comments": [
            "Triaging — looking at last 6h of memory_spike events.",
            "RSS growth correlates with batch jobs > 200 KB; opening jira-1234.",
        ],
    },
    {
        "title": "CPU burst regression in checkout_api",
        "status": "triage",
        "assignee": SECONDARY_ANALYST.id,
        "anomaly_filter": "cpu_burst",
        "max_attached": 3,
        "comments": ["Pinned to commit 9af2; deploying revert."],
    },
    {
        "title": "Suspicious outbound traffic in notification_dispatch",
        "status": "triage",
        "assignee": PRIMARY_ANALYST.id,
        "anomaly_filter": "network_anomaly",
        "max_attached": 5,
        "comments": [
            "L5 flagged T1071.001; correlating with WAF logs.",
            "False positive cluster — internal egress to S3.",
        ],
    },
    {
        "title": "Cold-start regression on auth_service",
        "status": "contained",
        "assignee": SECONDARY_ANALYST.id,
        "anomaly_filter": "cold_start",
        "max_attached": 3,
        "comments": ["Provisioned concurrency restored to baseline."],
    },
    {
        "title": "Economic abuse — graphql_resolver",
        "status": "open",
        "assignee": None,  # Unassigned to demo the picker.
        "anomaly_filter": "economic_abuse",
        "max_attached": 4,
        "comments": [],
    },
    {
        "title": "Cascade failure post-deploy",
        "status": "contained",
        "assignee": PRIMARY_ANALYST.id,
        "anomaly_filter": "cascade_failure",
        "max_attached": 3,
        "comments": ["Rollback completed; monitoring."],
    },
    {
        "title": "Security anomaly — model_inference",
        "status": "open",
        "assignee": PRIMARY_ANALYST.id,
        "anomaly_filter": "security_anomaly",
        "max_attached": 3,
        "comments": ["Adversarial-score elevated; triggering retrain."],
    },
    {
        "title": "Silent failure in log_collector",
        "status": "closed",
        "assignee": SECONDARY_ANALYST.id,
        "anomaly_filter": "silent_failure",
        "max_attached": 2,
        "comments": [
            "Verified completeness drop is benign (DST shift).",
            "Closing — no action required.",
        ],
    },
    {
        "title": "Multi-vector anomaly across user_search",
        "status": "triage",
        "assignee": PRIMARY_ANALYST.id,
        "anomaly_filter": None,  # any
        "max_attached": 4,
        "comments": [],
    },
    {
        "title": "Historical close — billing_aggregator",
        "status": "closed",
        "assignee": SECONDARY_ANALYST.id,
        "anomaly_filter": None,
        "max_attached": 2,
        "comments": ["Resolved last sprint."],
    },
]


def seed_cases(
    store: DetectionStore,
    *,
    rng: Optional[random.Random] = None,
) -> int:
    """Materialise demo cases on top of an already-seeded detections table.

    Returns the number of cases written.  Each case picks a small number of
    matching detections (by ``anomaly_type``), attaches them, transitions
    state to its preset status, and posts demo comments.
    """

    rng = rng or random.Random(123)
    rows, _ = store.list_detections(limit=10_000, offset=0)
    by_type: Dict[str, List[str]] = {}
    for row in rows:
        by_type.setdefault(row.anomaly_type, []).append(row.id)

    written = 0
    for preset in _CASE_PRESETS:
        # Pick a small slice of matching detections.
        if preset["anomaly_filter"] is not None:
            pool = list(by_type.get(preset["anomaly_filter"], []))
        else:
            pool = [r.id for r in rows]
        rng.shuffle(pool)
        attach_n = min(int(preset["max_attached"]), len(pool))
        attached: List[str] = []
        for did in pool[:attach_n]:
            # Skip already-attached detections from earlier presets.
            if store.case_for_detection(did) is None:
                attached.append(did)
        if not attached:
            # Always create the case even with zero attached so the UI
            # demo shows the full state matrix.
            attached = []

        try:
            case = store.create_case(
                title=preset["title"],
                created_by=PRIMARY_ANALYST.id,
                detection_ids=attached,
                assignee_id=preset["assignee"],
            )
        except (AlreadyAttached, StoreError):
            logger.warning("seeder: skipped case '%s' (attachment conflict)", preset["title"])
            continue

        # Transition to the preset state.  open is the default; any other
        # state requires a separate update.
        target = preset["status"]
        if target != "open":
            try:
                case = store.update_case(
                    case.id,
                    expected_version=case.version,
                    actor_id=PRIMARY_ANALYST.id,
                    status=target,
                    reason="seeder",
                )
            except StoreError:
                logger.exception("seeder: failed to transition case '%s'", preset["title"])

        for body in preset["comments"]:
            try:
                store.add_comment(case.id, PRIMARY_ANALYST.id, body)
            except StoreError:
                logger.warning("seeder: skipped comment for '%s'", preset["title"])

        written += 1
    logger.info("seeder: %s cases written", written)
    return written


def seed_database(
    *,
    settings: Optional[GUISettings] = None,
    count: Optional[int] = None,
    seed: int = 42,
    spread_hours: int = 24,
    truncate: bool = True,
    progress_every: int = 25,
    with_cases: bool = True,
) -> int:
    """Run ``count`` events through the runtime and persist each detection.

    Returns the number of detections written.  If ``with_cases`` is true the
    Phase-2 demo cases are seeded on top.
    """

    settings = settings or get_settings()
    n = int(count if count is not None else settings.seed_event_count)
    rng = random.Random(seed)

    store = DetectionStore(settings.db_path)
    if truncate:
        store.truncate()
    adapter = GUIRuntimeAdapter()

    now = datetime.now(timezone.utc)
    spread = timedelta(hours=max(1, spread_hours))
    written = 0
    started = time.perf_counter()

    for idx in range(n):
        event = generate_event(idx, rng)
        try:
            outcome = adapter.ingest(event)
        except Exception:  # noqa: BLE001 — keep seeding even if one event fails
            logger.exception("seeder: ingest failed for event %s", idx)
            continue
        ts = now - spread * (1.0 - (idx + 1) / max(1, n))
        store.insert_detection(
            event_id=outcome.event_id,
            function_id=outcome.function_id,
            anomaly_type=outcome.anomaly_type,
            severity=outcome.severity,
            trust_score=outcome.trust_score,
            mitre_techniques=outcome.mitre_techniques,
            layer_payload=outcome.layer_payload,
            decision=outcome.decision,
            risk_band=outcome.risk_band,
            duration_ms=outcome.duration_ms,
            correlation_id=outcome.correlation_id,
            ingested_at=ts,
        )
        written += 1
        if progress_every and (idx + 1) % progress_every == 0:
            logger.info("seeder: %s / %s events ingested", idx + 1, n)

    if with_cases:
        seed_cases(store, rng=random.Random(seed + 1))

    elapsed = time.perf_counter() - started
    logger.info(
        "seeder: %s detections written in %.2fs (db=%s)", written, elapsed, settings.db_path
    )
    return written


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the SCAFAD GUI database")
    parser.add_argument("--count", type=int, default=None, help="number of events to seed")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    parser.add_argument(
        "--spread-hours", type=int, default=24, help="spread events across the last N hours"
    )
    parser.add_argument(
        "--no-truncate", action="store_true", help="append rather than wipe existing data"
    )
    parser.add_argument(
        "--no-cases",
        action="store_true",
        help="skip the Phase-2 demo case seeding step",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args(argv)
    written = seed_database(
        count=args.count,
        seed=args.seed,
        spread_hours=args.spread_hours,
        truncate=not args.no_truncate,
        with_cases=not args.no_cases,
    )
    print(f"seeded {written} detections")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
