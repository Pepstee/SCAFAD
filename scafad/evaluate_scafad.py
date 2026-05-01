#!/usr/bin/env python3
"""
evaluate_scafad.py — C-5 Reproducible Evaluation Harness for SCAFAD-R
======================================================================

Runs the canonical permanent test suite (T-013..T-027) and writes a
machine-readable JSON results artefact to evaluation/results/.

Usage:
    python3 scafad/evaluate_scafad.py [--output-dir PATH] [--seed SEED]

Exit codes:
    0 — all tests passed
    1 — one or more tests failed (details in the artefact)

C-5 Contribution: Reproducible evaluation harness.
    - Deterministic seed for any randomised sub-components
    - JSON artefact includes per-suite counts, pass/fail, timing, metadata
    - Human-readable summary printed to stdout
    - Designed to run inside or outside Docker (no container dependency)

WP: Day-7 (7-day sprint)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import subprocess
import sys
import time
import unittest


# ---------------------------------------------------------------------------
# Canonical test suite manifest (T-013..T-025)
# ---------------------------------------------------------------------------

SCAFAD_PKG = os.path.dirname(os.path.abspath(__file__))

TEST_SUITES = [
    {
        "id": "T-013",
        "label": "Layer-1 Input Validation (InputValidationGateway)",
        "path": "layer1/tests/test_layer1_validation.py",
    },
    {
        "id": "T-014",
        "label": "Layer-1 Preservation Assessment (PreservationAssessment)",
        "path": "layer1/tests/test_layer1_preservation.py",
    },
    {
        "id": "T-015",
        "label": "Layer-1 Privacy Compliance (PrivacyComplianceFilter)",
        "path": "layer1/tests/test_layer1_privacy.py",
    },
    {
        "id": "T-016",
        "label": "Layer-1 Sanitisation (SanitisationProcessor)",
        "path": "layer1/tests/test_layer1_sanitisation.py",
    },
    {
        "id": "T-017",
        "label": "Layer-1 Deferred Hashing (DeferredHashingManager + HMAC)",
        "path": "layer1/tests/test_layer1_hashing.py",
    },
    {
        "id": "T-018",
        "label": "Layer-2 Multi-Vector Detection (MultiVectorDetectionMatrix)",
        "path": "layer2/tests/test_layer2_detection.py",
    },
    {
        "id": "T-019",
        "label": "Layer-0 Adapter (RCoreToLayer1Adapter)",
        "path": "layer0/tests/test_layer0_adapter.py",
    },
    {
        "id": "T-020",
        "label": "Layer-1 Extended Modules (scafad-delta reconciliation)",
        "path": "layer1/tests/test_layer1_extended.py",
    },
    {
        "id": "T-021",
        "label": "Layer-3 Trust-Weighted Fusion (C-2 TrustWeightedFusionEngine)",
        "path": "layer3/tests/test_layer3_fusion.py",
    },
    {
        "id": "T-022",
        "label": "Layer-4 Tiered Explainability (C-4 ExplainabilityDecisionEngine)",
        "path": "layer4/tests/test_layer4_explainability.py",
    },
    {
        "id": "T-023",
        "label": "Layer-5 MITRE Threat Alignment (ThreatAlignmentEngine)",
        "path": "layer5/tests/test_layer5_threat.py",
    },
    {
        "id": "T-024",
        "label": "Layer-6 Feedback Learning (FeedbackLearningEngine)",
        "path": "layer6/tests/test_layer6_feedback.py",
    },
    {
        "id": "T-025",
        "label": "Runtime E2E Integration (SCAFADCanonicalRuntime L0->L6)",
        "path": "runtime/tests/test_runtime_e2e.py",
    },
    {
        "id": "T-026",
        "label": "Layer-0 Core Tests (TelemetryRecord, AnomalyDetectionEngine, imports)",
        "path": "layer0/tests/test_layer0_core.py",
    },
    {
        "id": "T-027",
        "label": "Layer-0 Detector Registry (per-detector unit tests, WP-3.7)",
        "path": "layer0/tests/test_layer0_detectors.py",
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_suite(suite: dict, pkg_dir: str) -> dict:
    """Run one test suite via subprocess and return a result record."""
    abs_path = os.path.join(pkg_dir, suite["path"])
    if not os.path.exists(abs_path):
        return {
            "id": suite["id"],
            "label": suite["label"],
            "path": suite["path"],
            "status": "error",
            "error": f"File not found: {abs_path}",
            "tests_run": 0,
            "failures": 0,
            "errors": 1,
            "duration_s": 0.0,
        }

    t0 = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-m", "unittest", suite["path"], "-v"],
        capture_output=True,
        text=True,
        cwd=pkg_dir,
    )
    elapsed = time.monotonic() - t0

    # Parse unittest output: "Ran N tests in X.Xs"
    tests_run = 0
    failures = 0
    errors = 0
    for line in result.stderr.splitlines():
        if line.startswith("Ran "):
            try:
                tests_run = int(line.split()[1])
            except (IndexError, ValueError):
                pass
        if line.startswith("FAILED"):
            import re
            m = re.search(r"failures=(\d+)", line)
            if m:
                failures = int(m.group(1))
            m = re.search(r"errors=(\d+)", line)
            if m:
                errors = int(m.group(1))

    status = "pass" if result.returncode == 0 else "fail"
    return {
        "id": suite["id"],
        "label": suite["label"],
        "path": suite["path"],
        "status": status,
        "tests_run": tests_run,
        "failures": failures,
        "errors": errors,
        "duration_s": round(elapsed, 4),
        "returncode": result.returncode,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SCAFAD-R C-5 Reproducible Evaluation Harness"
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(os.path.dirname(SCAFAD_PKG), "evaluation", "results"),
        help="Directory for JSON artefact (default: ../evaluation/results/)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--suite-filter",
        default=None,
        help="Run only suites whose ID matches this substring (e.g. T-02)",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Override the output filename (e.g. eval_wp4.1.json). Written inside --output-dir.",
    )
    args = parser.parse_args()

    # Seed any randomised sub-components
    import random
    random.seed(args.seed)
    try:
        import numpy as np  # type: ignore[import]
        np.random.seed(args.seed)
    except ImportError:
        pass

    run_id = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    print(f"\nSCAFAD-R Evaluation Harness — run {run_id}")
    print(f"Package directory : {SCAFAD_PKG}")
    print(f"Python            : {sys.version.split()[0]}")
    print(f"Platform          : {platform.system()} {platform.release()}")
    print(f"Seed              : {args.seed}")
    print("=" * 60)

    suites_to_run = [
        s for s in TEST_SUITES
        if args.suite_filter is None or args.suite_filter in s["id"]
    ]

    suite_results = []
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_time = 0.0

    for suite in suites_to_run:
        print(f"  {suite['id']}  {suite['label']} ... ", end="", flush=True)
        res = run_suite(suite, SCAFAD_PKG)
        suite_results.append(res)
        total_tests += res["tests_run"]
        total_failures += res["failures"]
        total_errors += res["errors"]
        total_time += res["duration_s"]
        mark = "PASS" if res["status"] == "pass" else f"FAIL (f={res['failures']},e={res['errors']})"
        print(f"{mark}  [{res['tests_run']} tests, {res['duration_s']:.3f}s]")

    all_passed = total_failures == 0 and total_errors == 0
    status_str = "ALL_PASS" if all_passed else "FAILURES_PRESENT"

    print("=" * 60)
    print(f"Total tests  : {total_tests}")
    print(f"Failures     : {total_failures}")
    print(f"Errors       : {total_errors}")
    print(f"Total time   : {total_time:.3f}s")
    print(f"Status       : {status_str}")
    print()

    # Build artefact
    artefact = {
        "scafad_evaluation": {
            "run_id": run_id,
            "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
            "seed": args.seed,
            "python_version": sys.version.split()[0],
            "platform": f"{platform.system()} {platform.release()}",
            "scafad_package_dir": SCAFAD_PKG,
            "status": status_str,
            "summary": {
                "suites_run": len(suites_to_run),
                "total_tests": total_tests,
                "total_failures": total_failures,
                "total_errors": total_errors,
                "total_duration_s": round(total_time, 4),
            },
            "suite_results": suite_results,
        }
    }

    os.makedirs(args.output_dir, exist_ok=True)
    filename = args.output_file if args.output_file else f"evaluation_{run_id}.json"
    out_path = os.path.join(args.output_dir, filename)
    with open(out_path, "w") as f:
        json.dump(artefact, f, indent=2)
    print(f"Artefact written: {out_path}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
