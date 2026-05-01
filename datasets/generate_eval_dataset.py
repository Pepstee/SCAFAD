#!/usr/bin/env python3
"""
SCAFAD Synthetic Evaluation Dataset Generator
=============================================

Generates a labelled synthetic dataset covering all AnomalyType values
for evaluation purposes.  Produces:

  datasets/synthetic_eval_dataset.json.gz   — compressed list of dicts
  datasets/synthetic_eval_dataset_manifest.json — class counts + seed

Each record is a valid TelemetryRecord.to_dict()-compatible dict
(schema_version='v4.2') with realistic per-class metric profiles.

Reproducibility
---------------
Setting seed=42 (``SEED`` constant below) produces identical output on
every run.  To verify::

    python datasets/generate_eval_dataset.py   # run 1
    md5sum datasets/synthetic_eval_dataset.json.gz
    python datasets/generate_eval_dataset.py   # run 2 — same md5

Usage (from project/scafad-r-core/)
-------------------------------------
    python datasets/generate_eval_dataset.py [--seed N] [--records-per-class N]

References
----------
Uses scafad/layer0/app_telemetry.py for AnomalyType, ExecutionPhase,
and TelemetrySource enumerations.  Metric profiles are inspired by the
realistic patterns implemented in datasets/serverless_traces.py.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Path bootstrap — add scafad/ so that layer0 package is importable
# ---------------------------------------------------------------------------
_DATASETS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_DATASETS_DIR)  # project/scafad-r-core/
sys.path.insert(0, os.path.join(_ROOT, "scafad"))

from layer0.app_telemetry import AnomalyType, ExecutionPhase, TelemetrySource  # noqa: E402


# ---------------------------------------------------------------------------
# Reproducible UUID helper
# ---------------------------------------------------------------------------

def _rng_uuid(rng: np.random.Generator) -> str:
    """Generate a UUID4-format string using *rng* so output is reproducible.

    Standard ``uuid.uuid4()`` draws from the OS CSPRNG and therefore produces
    different values on every run even when the numpy seed is fixed.  This
    helper draws 16 bytes from *rng* and formats them as a UUID4 string.
    """
    raw: bytes = rng.integers(0, 256, size=16, dtype=np.uint8).tobytes()
    # Apply RFC 4122 version-4 / variant-2 bit masks
    b = bytearray(raw)
    b[6] = (b[6] & 0x0F) | 0x40  # version 4
    b[8] = (b[8] & 0x3F) | 0x80  # variant bits
    h = b.hex()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEED: int = 42
RECORDS_PER_CLASS: int = 250  # ≥ 200 required per acceptance criteria
SCHEMA_VERSION: str = "v4.2"
BASE_TIMESTAMP: float = 1_745_000_000.0  # Fixed epoch — do NOT change (reproducibility)

OUTPUT_DATASET: str = os.path.join(_DATASETS_DIR, "synthetic_eval_dataset.json.gz")
OUTPUT_MANIFEST: str = os.path.join(_DATASETS_DIR, "synthetic_eval_dataset_manifest.json")

_REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
_RUNTIMES = ["python3.9", "python3.10", "python3.11"]
_TRIGGERS = ["api_gateway", "s3", "dynamodb", "scheduled", "sqs", "eventbridge"]
_FUNCTIONS = [
    "fn-user-api",
    "fn-image-resize",
    "fn-data-etl",
    "fn-ml-predict",
    "fn-iot-processor",
    "fn-batch-analytics",
    "fn-file-transform",
    "fn-db-trigger",
]


# ---------------------------------------------------------------------------
# Per-class metric profiles
# ---------------------------------------------------------------------------

def _anomaly_profile(
    atype: AnomalyType,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Return realistic metric overrides for a given AnomalyType.

    The returned dict contains only the fields that differ from the BENIGN
    baseline; remaining fields are filled in by ``_generate_record``.
    """

    # ---- Defaults (BENIGN baseline) ----------------------------------------
    duration: float = float(rng.uniform(0.05, 0.5))
    memory_spike_kb: int = int(rng.uniform(64, 512))
    cpu_utilization: float = float(rng.uniform(5.0, 45.0))
    network_io_bytes: int = int(rng.uniform(500, 8_000))
    fallback_mode: bool = False
    adversarial_score: float = 0.0
    economic_risk_score: float = 0.0
    silent_failure_probability: float = 0.0
    execution_phase: ExecutionPhase = ExecutionPhase.INVOKE
    source: TelemetrySource = TelemetrySource.SCAFAD_LAYER0

    # ---- Anomaly-specific overrides ----------------------------------------
    if atype == AnomalyType.BENIGN:
        pass  # Already set to BENIGN defaults above

    elif atype == AnomalyType.COLD_START:
        duration = float(rng.uniform(0.5, 3.0))
        memory_spike_kb = int(rng.uniform(256, 768))
        cpu_utilization = float(rng.uniform(30.0, 70.0))
        network_io_bytes = int(rng.uniform(2_000, 15_000))
        execution_phase = ExecutionPhase.INIT

    elif atype == AnomalyType.CPU_BURST:
        duration = float(rng.uniform(1.0, 8.0))
        memory_spike_kb = int(rng.uniform(256, 1_024))
        cpu_utilization = float(rng.uniform(75.0, 95.0))
        network_io_bytes = int(rng.uniform(1_000, 5_000))

    elif atype == AnomalyType.CPU_SPIKE:
        duration = float(rng.uniform(0.1, 1.0))
        memory_spike_kb = int(rng.uniform(128, 512))
        cpu_utilization = float(rng.uniform(88.0, 100.0))
        network_io_bytes = int(rng.uniform(500, 3_000))

    elif atype == AnomalyType.MEMORY_SPIKE:
        duration = float(rng.uniform(0.2, 2.0))
        memory_spike_kb = int(rng.uniform(2_048, 6_144))
        cpu_utilization = float(rng.uniform(20.0, 60.0))
        network_io_bytes = int(rng.uniform(1_000, 10_000))

    elif atype == AnomalyType.MEMORY_LEAK:
        duration = float(rng.uniform(5.0, 30.0))
        memory_spike_kb = int(rng.uniform(4_096, 8_192))
        cpu_utilization = float(rng.uniform(30.0, 70.0))
        network_io_bytes = int(rng.uniform(1_000, 8_000))

    elif atype == AnomalyType.LATENCY_SPIKE:
        duration = float(rng.uniform(5.0, 25.0))
        memory_spike_kb = int(rng.uniform(128, 512))
        cpu_utilization = float(rng.uniform(10.0, 35.0))
        network_io_bytes = int(rng.uniform(1_000, 8_000))

    elif atype == AnomalyType.IO_INTENSIVE:
        duration = float(rng.uniform(1.0, 10.0))
        memory_spike_kb = int(rng.uniform(256, 1_024))
        cpu_utilization = float(rng.uniform(15.0, 50.0))
        network_io_bytes = int(rng.uniform(50_000, 500_000))

    elif atype == AnomalyType.NETWORK_ANOMALY:
        duration = float(rng.uniform(0.5, 5.0))
        memory_spike_kb = int(rng.uniform(128, 512))
        cpu_utilization = float(rng.uniform(10.0, 40.0))
        network_io_bytes = int(rng.uniform(100_000, 1_000_000))

    elif atype == AnomalyType.TIMEOUT_ANOMALY:
        duration = float(rng.uniform(10.0, 30.0))
        memory_spike_kb = int(rng.uniform(512, 2_048))
        cpu_utilization = float(rng.uniform(40.0, 80.0))
        network_io_bytes = int(rng.uniform(1_000, 20_000))
        execution_phase = ExecutionPhase.TIMEOUT

    elif atype == AnomalyType.EXECUTION_FAILURE:
        duration = float(rng.uniform(0.001, 0.5))
        memory_spike_kb = int(rng.uniform(64, 256))
        cpu_utilization = float(rng.uniform(5.0, 30.0))
        network_io_bytes = int(rng.uniform(100, 2_000))
        fallback_mode = True
        execution_phase = ExecutionPhase.ERROR
        source = TelemetrySource.FALLBACK_GENERATOR

    elif atype == AnomalyType.ERROR_RATE_INCREASE:
        duration = float(rng.uniform(0.05, 0.5))
        memory_spike_kb = int(rng.uniform(64, 256))
        cpu_utilization = float(rng.uniform(10.0, 40.0))
        network_io_bytes = int(rng.uniform(500, 5_000))
        # ~60 % of records trigger fallback
        fallback_mode = bool(rng.integers(0, 5) < 3)
        if fallback_mode:
            execution_phase = ExecutionPhase.ERROR
            source = TelemetrySource.FALLBACK_GENERATOR

    elif atype == AnomalyType.STARVATION_FALLBACK:
        duration = float(rng.uniform(15.0, 30.0))
        memory_spike_kb = int(rng.uniform(1_024, 3_072))
        cpu_utilization = float(rng.uniform(50.0, 90.0))
        network_io_bytes = int(rng.uniform(1_000, 10_000))
        fallback_mode = True
        execution_phase = ExecutionPhase.TIMEOUT
        source = TelemetrySource.FALLBACK_GENERATOR

    elif atype == AnomalyType.TIMEOUT_FALLBACK:
        duration = float(rng.uniform(14.5, 29.9))
        memory_spike_kb = int(rng.uniform(512, 2_048))
        cpu_utilization = float(rng.uniform(30.0, 70.0))
        network_io_bytes = int(rng.uniform(1_000, 10_000))
        fallback_mode = True
        execution_phase = ExecutionPhase.TIMEOUT
        source = TelemetrySource.FALLBACK_GENERATOR

    elif atype == AnomalyType.SCHEMA_VIOLATION:
        duration = float(rng.uniform(0.05, 0.5))
        memory_spike_kb = int(rng.uniform(64, 256))
        cpu_utilization = float(rng.uniform(5.0, 25.0))
        network_io_bytes = int(rng.uniform(100, 2_000))

    elif atype == AnomalyType.ADVERSARIAL_INJECTION:
        duration = float(rng.uniform(0.5, 5.0))
        memory_spike_kb = int(rng.uniform(256, 1_024))
        cpu_utilization = float(rng.uniform(60.0, 95.0))
        network_io_bytes = int(rng.uniform(5_000, 100_000))
        adversarial_score = float(rng.uniform(0.70, 1.0))
        economic_risk_score = float(rng.uniform(0.50, 0.90))
        source = TelemetrySource.ADVERSARIAL_SIMULATOR

    elif atype == AnomalyType.BILLING_ABUSE:
        duration = float(rng.uniform(20.0, 30.0))
        memory_spike_kb = int(rng.uniform(2_048, 4_096))
        cpu_utilization = float(rng.uniform(70.0, 99.0))
        network_io_bytes = int(rng.uniform(10_000, 100_000))
        adversarial_score = float(rng.uniform(0.60, 0.90))
        economic_risk_score = float(rng.uniform(0.70, 1.0))
        source = TelemetrySource.ECONOMIC_DETECTOR

    elif atype == AnomalyType.ECONOMIC_ABUSE:
        duration = float(rng.uniform(10.0, 30.0))
        memory_spike_kb = int(rng.uniform(1_024, 3_072))
        cpu_utilization = float(rng.uniform(60.0, 100.0))
        network_io_bytes = int(rng.uniform(5_000, 50_000))
        adversarial_score = float(rng.uniform(0.50, 0.85))
        economic_risk_score = float(rng.uniform(0.70, 1.0))
        source = TelemetrySource.ECONOMIC_DETECTOR

    elif atype == AnomalyType.DOS_AMPLIFICATION:
        duration = float(rng.uniform(0.1, 2.0))
        memory_spike_kb = int(rng.uniform(128, 512))
        cpu_utilization = float(rng.uniform(70.0, 100.0))
        network_io_bytes = int(rng.uniform(500_000, 5_000_000))
        adversarial_score = float(rng.uniform(0.70, 1.0))
        economic_risk_score = float(rng.uniform(0.50, 0.90))
        source = TelemetrySource.ADVERSARIAL_SIMULATOR

    elif atype == AnomalyType.CRYPTOMINING:
        # Characteristic: near-maxed CPU, very consistent ~14–15 s duration
        raw = float(rng.normal(14.5, 0.4))
        duration = max(13.0, min(15.0, raw))
        memory_spike_kb = int(rng.uniform(256, 512))
        cpu_utilization = float(rng.uniform(95.0, 100.0))
        network_io_bytes = int(rng.uniform(1_000, 5_000))
        adversarial_score = float(rng.uniform(0.60, 0.90))
        economic_risk_score = float(rng.uniform(0.50, 0.80))
        source = TelemetrySource.ADVERSARIAL_SIMULATOR

    elif atype == AnomalyType.DATA_EXFILTRATION:
        duration = float(rng.uniform(0.5, 5.0))
        memory_spike_kb = int(rng.uniform(128, 512))
        cpu_utilization = float(rng.uniform(10.0, 40.0))
        network_io_bytes = int(rng.uniform(1_000_000, 10_000_000))
        adversarial_score = float(rng.uniform(0.70, 1.0))
        economic_risk_score = float(rng.uniform(0.40, 0.80))
        source = TelemetrySource.ADVERSARIAL_SIMULATOR

    elif atype == AnomalyType.PRIVILEGE_ESCALATION:
        duration = float(rng.uniform(0.1, 1.0))
        memory_spike_kb = int(rng.uniform(128, 512))
        cpu_utilization = float(rng.uniform(20.0, 60.0))
        network_io_bytes = int(rng.uniform(1_000, 20_000))
        adversarial_score = float(rng.uniform(0.80, 1.0))
        economic_risk_score = float(rng.uniform(0.30, 0.70))
        source = TelemetrySource.ADVERSARIAL_SIMULATOR

    elif atype == AnomalyType.SILENT_CORRUPTION:
        # Externally normal metrics — corruption is silent
        duration = float(rng.uniform(0.05, 0.5))
        memory_spike_kb = int(rng.uniform(128, 512))
        cpu_utilization = float(rng.uniform(10.0, 45.0))
        network_io_bytes = int(rng.uniform(500, 8_000))
        silent_failure_probability = float(rng.uniform(0.70, 1.0))
        source = TelemetrySource.SILENT_FAILURE_DETECTOR

    elif atype == AnomalyType.SEMANTIC_FAILURE:
        duration = float(rng.uniform(0.05, 0.5))
        memory_spike_kb = int(rng.uniform(128, 512))
        cpu_utilization = float(rng.uniform(10.0, 45.0))
        network_io_bytes = int(rng.uniform(500, 8_000))
        silent_failure_probability = float(rng.uniform(0.60, 0.95))
        source = TelemetrySource.SILENT_FAILURE_DETECTOR

    elif atype == AnomalyType.OUTPUT_CORRUPTION:
        duration = float(rng.uniform(0.05, 1.0))
        memory_spike_kb = int(rng.uniform(128, 768))
        cpu_utilization = float(rng.uniform(10.0, 50.0))
        network_io_bytes = int(rng.uniform(500, 10_000))
        silent_failure_probability = float(rng.uniform(0.50, 0.90))
        source = TelemetrySource.SILENT_FAILURE_DETECTOR

    elif atype == AnomalyType.INVARIANT_VIOLATION:
        duration = float(rng.uniform(0.05, 0.5))
        memory_spike_kb = int(rng.uniform(128, 512))
        cpu_utilization = float(rng.uniform(10.0, 45.0))
        network_io_bytes = int(rng.uniform(500, 8_000))
        silent_failure_probability = float(rng.uniform(0.50, 0.85))
        source = TelemetrySource.FORMAL_VERIFIER

    return {
        "duration": duration,
        "memory_spike_kb": memory_spike_kb,
        "cpu_utilization": min(100.0, max(0.0, cpu_utilization)),
        "network_io_bytes": network_io_bytes,
        "fallback_mode": fallback_mode,
        "adversarial_score": min(1.0, max(0.0, adversarial_score)),
        "economic_risk_score": min(1.0, max(0.0, economic_risk_score)),
        "silent_failure_probability": min(1.0, max(0.0, silent_failure_probability)),
        "execution_phase": execution_phase,
        "source": source,
    }


def _generate_record(
    atype: AnomalyType,
    record_idx: int,
    rng: np.random.Generator,
    base_timestamp: float,
) -> dict[str, Any]:
    """Generate a single TelemetryRecord-compatible dict.

    Parameters
    ----------
    atype:
        The anomaly class for this record.
    record_idx:
        Sequential index within the class (used to space timestamps).
    rng:
        Seeded NumPy default_rng instance — must be passed in to preserve
        the global random stream for reproducibility.
    base_timestamp:
        Starting POSIX timestamp (seconds).

    Returns
    -------
    dict
        Keys and value types match TelemetryRecord.to_dict() output.
    """
    profile = _anomaly_profile(atype, rng)

    function_id: str = _FUNCTIONS[int(rng.integers(0, len(_FUNCTIONS)))]
    region: str = _REGIONS[int(rng.integers(0, len(_REGIONS)))]
    runtime: str = _RUNTIMES[int(rng.integers(0, len(_RUNTIMES)))]
    trigger: str = _TRIGGERS[int(rng.integers(0, len(_TRIGGERS)))]

    # Space records 0.1 s apart with a small random jitter
    timestamp: float = base_timestamp + record_idx * 0.1 + float(rng.uniform(0, 0.05))

    return {
        # --- Required core fields ---
        "event_id": _rng_uuid(rng),
        "timestamp": timestamp,
        "function_id": function_id,
        "execution_phase": profile["execution_phase"].value,
        "anomaly_type": atype.value,
        # --- Execution metrics ---
        "duration": profile["duration"],
        "memory_spike_kb": profile["memory_spike_kb"],
        "cpu_utilization": profile["cpu_utilization"],
        "network_io_bytes": profile["network_io_bytes"],
        # --- Operational metadata ---
        "fallback_mode": profile["fallback_mode"],
        "source": profile["source"].value,
        "concurrency_id": f"concurrency-{int(rng.integers(1, 1000))}",
        # --- Advanced metadata ---
        "container_id": f"container-{int(rng.integers(1000, 9999))}",
        "region": region,
        "runtime_version": runtime,
        # --- Contextual information ---
        "trigger_type": trigger,
        "payload_size_bytes": int(rng.uniform(0, 10_000)),
        "payload_hash": None,
        # --- Analysis results ---
        "provenance_id": _rng_uuid(rng),
        "graph_node_id": None,
        "parent_chain": [],
        "causal_depth": 0,
        # --- Risk assessment scores ---
        "adversarial_score": profile["adversarial_score"],
        "economic_risk_score": profile["economic_risk_score"],
        "silent_failure_probability": profile["silent_failure_probability"],
        "completeness_score": float(rng.uniform(0.85, 1.0)),
        # --- Quality metrics ---
        "confidence_level": float(rng.uniform(0.80, 1.0)),
        "data_quality_score": float(rng.uniform(0.85, 1.0)),
        "schema_version": SCHEMA_VERSION,
        # --- Emission metadata ---
        "emission_timestamp": timestamp + 0.001,
        "emission_channels": ["primary"],
        "emission_attempts": 1,
        # --- Extensibility ---
        "custom_fields": {},
        "tags": {
            "class": atype.value,
            "category": atype.category,
            "generator": "synthetic_eval",
        },
        # --- Cryptographic integrity ---
        "signature": None,
        "signature_algorithm": "HMAC-SHA256",
        "content_hash": None,
    }


def generate_dataset(
    seed: int = SEED,
    records_per_class: int = RECORDS_PER_CLASS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generate the full synthetic evaluation dataset.

    Parameters
    ----------
    seed:
        Random seed for reproducibility.
    records_per_class:
        Number of records to generate per AnomalyType value.

    Returns
    -------
    records:
        Shuffled list of TelemetryRecord-compatible dicts.
    manifest:
        Manifest dict with class counts, seed, and generation metadata.
    """
    rng = np.random.default_rng(seed)
    all_types = list(AnomalyType)

    records: list[dict[str, Any]] = []
    class_counts: dict[str, int] = {}

    for atype in all_types:
        for i in range(records_per_class):
            rec = _generate_record(atype, i, rng, BASE_TIMESTAMP)
            records.append(rec)
        class_counts[atype.value] = records_per_class

    # Shuffle the combined dataset while preserving reproducibility
    perm = rng.permutation(len(records))
    records = [records[int(i)] for i in perm]

    non_benign = [t for t in all_types if t != AnomalyType.BENIGN]
    manifest: dict[str, Any] = {
        "task_id": "2b6574ed-5975-4243-993c-28107e948730",
        "seed": seed,
        "schema_version": SCHEMA_VERSION,
        "records_per_class": records_per_class,
        "total_records": len(records),
        "num_classes": len(all_types),
        "num_anomaly_types": len(non_benign),
        "class_counts": class_counts,
        "anomaly_types": [t.value for t in all_types],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "datasets/generate_eval_dataset.py",
        "notes": (
            f"Covers all {len(all_types)} AnomalyType values "
            f"({len(non_benign)} anomaly types + BENIGN baseline). "
            f"Reproducible with seed={seed}. "
            f"Each record is TelemetryRecord.to_dict()-compatible (schema {SCHEMA_VERSION})."
        ),
    }

    return records, manifest


def write_outputs(
    records: list[dict[str, Any]],
    manifest: dict[str, Any],
    dataset_path: str = OUTPUT_DATASET,
    manifest_path: str = OUTPUT_MANIFEST,
) -> None:
    """Write the dataset (compressed) and manifest to disk."""
    os.makedirs(os.path.dirname(dataset_path), exist_ok=True)

    print(f"Writing {len(records)} records to {dataset_path}")
    with gzip.open(dataset_path, "wt", encoding="utf-8") as fgz:
        json.dump(records, fgz, separators=(",", ":"))

    print(f"Writing manifest to {manifest_path}")
    with open(manifest_path, "w", encoding="utf-8") as fm:
        json.dump(manifest, fm, indent=2)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=SEED, help=f"Random seed (default: {SEED})")
    parser.add_argument(
        "--records-per-class",
        type=int,
        default=RECORDS_PER_CLASS,
        help=f"Records per AnomalyType class (default: {RECORDS_PER_CLASS})",
    )
    parser.add_argument("--dataset-path", default=OUTPUT_DATASET, help="Output .json.gz path")
    parser.add_argument("--manifest-path", default=OUTPUT_MANIFEST, help="Output manifest .json path")
    args = parser.parse_args(argv)

    print(f"Generating synthetic evaluation dataset (seed={args.seed}, {args.records_per_class} records/class)...")
    records, manifest = generate_dataset(seed=args.seed, records_per_class=args.records_per_class)

    all_types = list(AnomalyType)
    for atype in all_types:
        count = manifest["class_counts"].get(atype.value, 0)
        print(f"  {atype.value:30s}  {count:4d} records  [{atype.category}]")

    write_outputs(records, manifest, dataset_path=args.dataset_path, manifest_path=args.manifest_path)

    print(
        f"\nDone: {manifest['total_records']} records across "
        f"{manifest['num_classes']} classes "
        f"({manifest['num_anomaly_types']} anomaly types + BENIGN)."
    )


if __name__ == "__main__":
    main()
