#!/usr/bin/env python3
"""
Ablation study: SemanticDeviationCore removed from Layer 2.

Runs the full SCAFAD pipeline twice on the same 6,300-record test corpus:
  (1) Baseline  — standard pipeline (SemanticDeviationCore active)
  (2) Ablated   — SemanticDeviationCore zeroed out (score=0, confidence=0)

SemanticDeviationCore (layer2/detection_matrix.py) reads the ground-truth
`anomaly_type` field and adds 0.45 to its detection score for any non-benign
record. This oracle label is present in the synthetic evaluation corpus but
would NOT be available at inference time in production. The ablation isolates
the ROC-AUC contribution of the remaining three L2 detectors
(RuleChainEngine, DriftTracker, GraphImmunizedDetector) plus the L0
enrichment scores.

Outputs
-------
  evaluation/results/ablation_semantic_deviation.json
"""

from __future__ import annotations

import gzip
import importlib
import importlib.abc
import importlib.machinery
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Path bootstrap (mirrors run_scafad_pipeline.py)
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT   = _SCRIPT_DIR.parent
_SCAFAD_PKG  = _REPO_ROOT / "scafad"

for _p in (str(_REPO_ROOT), str(_SCAFAD_PKG)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Namespace alias hook (mirrors run_scafad_pipeline.py — DL-040)
# ---------------------------------------------------------------------------
class _AliasLoader(importlib.abc.Loader):
    def __init__(self, module: object) -> None:
        self._module = module
    def create_module(self, spec: importlib.machinery.ModuleSpec) -> object:
        return self._module
    def exec_module(self, module: object) -> None:
        pass

class _ScafadNamespaceAlias(importlib.abc.MetaPathFinder):
    _PREFIX = "scafad."
    _LAYERS = frozenset(["layer0","layer1","layer2","layer3","layer4","layer5","layer6","runtime"])
    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(self._PREFIX):
            return None
        rest = fullname[len(self._PREFIX):]
        top_layer = rest.split(".")[0]
        if top_layer not in self._LAYERS:
            return None
        if fullname in sys.modules:
            return None
        if rest not in sys.modules:
            try:
                importlib.import_module(rest)
            except ImportError:
                return None
        bare_mod = sys.modules.get(rest)
        if bare_mod is None:
            return None
        sys.modules[fullname] = bare_mod
        spec = importlib.machinery.ModuleSpec(fullname, _AliasLoader(bare_mod))
        spec.submodule_search_locations = getattr(bare_mod, "__path__", None)
        return spec

if not any(isinstance(f, _ScafadNamespaceAlias) for f in sys.meta_path):
    sys.meta_path.insert(0, _ScafadNamespaceAlias())

# ---------------------------------------------------------------------------
# Imports (after path bootstrap)
# ---------------------------------------------------------------------------
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score

from scafad.runtime import SCAFADCanonicalRuntime
import layer2.detection_matrix as _dm

# ---------------------------------------------------------------------------
# Constants (identical to run_scafad_pipeline.py)
# ---------------------------------------------------------------------------
DATASET_PATH   = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
OUTPUT_PATH    = _REPO_ROOT / "evaluation" / "results" / "ablation_semantic_deviation.json"

BENIGN_CLASS       = "benign"
RANDOM_SEED        = 42
TRAIN_BENIGN_COUNT = 200
RESET_EVERY        = 200

_DECISION_TO_LABEL: Dict[str, int] = {
    "observe": 0, "review": 1, "escalate": 1,
    "benign": 0, "alert": 1, "error": 1,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_dataset() -> List[Dict[str, Any]]:
    with gzip.open(str(DATASET_PATH), "rt", encoding="utf-8") as fh:
        return json.load(fh)

def build_test_set(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    benign  = [r for r in records if r["anomaly_type"].lower() == BENIGN_CLASS]
    anomaly = [r for r in records if r["anomaly_type"].lower() != BENIGN_CLASS]
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(benign)
    return benign[TRAIN_BENIGN_COUNT:] + anomaly

def gt(record: Dict[str, Any]) -> int:
    return 0 if record["anomaly_type"].lower() == BENIGN_CLASS else 1

def decision_label(d: str) -> int:
    return _DECISION_TO_LABEL.get(d.lower(), 1)

# ---------------------------------------------------------------------------
# Single evaluation pass
# ---------------------------------------------------------------------------
def run_pass(test_records: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
    print(f"\n[ablation] Running: {label}", flush=True)
    runtime = SCAFADCanonicalRuntime()
    y_true, y_pred, y_score = [], [], []
    errors = 0
    t0 = time.perf_counter()
    print_every = max(1, len(test_records) // 10)

    for idx, record in enumerate(test_records):
        if idx > 0 and idx % RESET_EVERY == 0:
            runtime = SCAFADCanonicalRuntime()

        y_true.append(gt(record))
        try:
            result   = runtime.process_event(record, verbosity="terse")
            l4       = result.multilayer_result.layer4
            l3       = result.multilayer_result.layer3
            decision = l4.decision
            pred     = decision_label(decision)
            score    = float(l3.fused_score)
        except Exception as exc:
            decision, pred, score = "error", 1, 1.0
            errors += 1
            if errors <= 3:
                print(f"  [warn] idx={idx}: {exc}", flush=True)

        y_pred.append(pred)
        y_score.append(score)

        if (idx + 1) % print_every == 0 or idx == len(test_records) - 1:
            elapsed = time.perf_counter() - t0
            print(f"  {idx+1:5d}/{len(test_records)}  {(idx+1)/len(test_records)*100:.0f}%"
                  f"  {elapsed:.1f}s", flush=True)

    elapsed = time.perf_counter() - t0
    roc_auc   = float(roc_auc_score(y_true, y_score))
    precision = float(precision_score(y_true, y_pred, zero_division=0))
    recall    = float(recall_score(y_true, y_pred, zero_division=0))
    f1        = float(f1_score(y_true, y_pred, zero_division=0))

    print(f"  => ROC-AUC={roc_auc:.4f}  F1={f1:.4f}  P={precision:.4f}  R={recall:.4f}"
          f"  errors={errors}  time={elapsed:.1f}s", flush=True)

    return {
        "label":     label,
        "roc_auc":   round(roc_auc,   6),
        "precision": round(precision, 6),
        "recall":    round(recall,    6),
        "f1":        round(f1,        6),
        "errors":    errors,
        "elapsed_s": round(elapsed, 2),
    }

# ---------------------------------------------------------------------------
# Null detector (ablation patch)
# ---------------------------------------------------------------------------
class _NullDetector:
    """Drop-in for SemanticDeviationCore that always returns a zero signal."""
    def evaluate(self, record: Dict[str, Any]) -> "_dm.DetectionSignal":
        return _dm.DetectionSignal(
            detector_name="semantic_deviation_ABLATED",
            score=0.0,
            confidence=0.0,
            rationale="SemanticDeviationCore ablated for oracle-leakage study",
            evidence={"ablated": True},
        )

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("[ablation] Loading dataset...", flush=True)
    records = load_dataset()
    test_records = build_test_set(records)
    print(f"[ablation] Test set: {len(test_records):,} records.", flush=True)

    # ── Pass 1: standard (baseline) ──────────────────────────────────────────
    result_baseline = run_pass(test_records, "STANDARD (SemanticDeviationCore active)")

    # ── Patch Layer 2: replace SemanticDeviationCore with null detector ──────
    print("\n[ablation] Patching SemanticDeviationCore → NullDetector...", flush=True)
    _dm.SemanticDeviationCore = _NullDetector  # type: ignore[attr-defined]

    # Force re-import of pipeline module so MultiVectorDetectionMatrix
    # picks up the patched class on its next instantiation.
    import layer2.detection_matrix as _dm2
    _dm2.SemanticDeviationCore = _NullDetector  # type: ignore[attr-defined]

    # Also patch the class inside the already-imported MultiVectorDetectionMatrix
    # by replacing detector references in any cached instances.
    # The safest route: monkey-patch __init__ so new instances use NullDetector.
    _orig_init = _dm.MultiVectorDetectionMatrix.__init__

    def _patched_init(self) -> None:  # type: ignore[override]
        from layer2.detection_matrix import (
            RuleChainEngine, DriftTracker, GraphImmunizedDetector
        )
        self.detectors = (
            RuleChainEngine(),
            DriftTracker(),
            GraphImmunizedDetector(),
            _NullDetector(),          # ← oracle-free replacement
        )

    _dm.MultiVectorDetectionMatrix.__init__ = _patched_init  # type: ignore[method-assign]

    # ── Pass 2: ablated ───────────────────────────────────────────────────────
    result_ablated = run_pass(test_records, "ABLATED (SemanticDeviationCore zeroed)")

    # ── Summary ───────────────────────────────────────────────────────────────
    delta_auc = result_ablated["roc_auc"] - result_baseline["roc_auc"]
    delta_f1  = result_ablated["f1"]      - result_baseline["f1"]

    print("\n" + "=" * 60)
    print("ABLATION SUMMARY")
    print("=" * 60)
    print(f"  Standard  ROC-AUC = {result_baseline['roc_auc']:.4f}  F1 = {result_baseline['f1']:.4f}")
    print(f"  Ablated   ROC-AUC = {result_ablated['roc_auc']:.4f}  F1 = {result_ablated['f1']:.4f}")
    print(f"  Delta     ROC-AUC = {delta_auc:+.4f}  F1 = {delta_f1:+.4f}")
    print("=" * 60)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "description": (
            "Oracle-leakage ablation study. SemanticDeviationCore reads the ground-truth "
            "anomaly_type field and adds 0.45 to its score for every non-benign record. "
            "In the ablated pass it is replaced with a NullDetector (score=0, confidence=0). "
            "The remaining L2 detectors (RuleChainEngine, DriftTracker, "
            "GraphImmunizedDetector) plus L0 enrichment scores are unchanged."
        ),
        "test_records":      len(test_records),
        "seed":              RANDOM_SEED,
        "reset_every":       RESET_EVERY,
        "standard":          result_baseline,
        "ablated":           result_ablated,
        "delta": {
            "roc_auc": round(delta_auc, 6),
            "f1":      round(delta_f1,  6),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(str(OUTPUT_PATH), "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)
    print(f"\n[ablation] Results written to {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
