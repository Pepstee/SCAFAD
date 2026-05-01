#!/usr/bin/env python3
"""
Ablated-only pass: SemanticDeviationCore zeroed out.

Uses all 50 held-out benign records + stratified 20 per anomaly class
(500 anomalous) = 550 records. All 50 benign are retained to maximise
ROC-AUC reliability (AUC is sensitive to the benign cohort).

Standard (oracle) results are read directly from the existing full-run
scafad_results.json so we do not re-run the expensive standard pass.
"""

from __future__ import annotations
import gzip, importlib, importlib.abc, importlib.machinery, json, random, sys, time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT   = _SCRIPT_DIR.parent
_SCAFAD_PKG  = _REPO_ROOT / "scafad"
for _p in (str(_REPO_ROOT), str(_SCAFAD_PKG)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

class _AliasLoader(importlib.abc.Loader):
    def __init__(self, m): self._module = m
    def create_module(self, spec): return self._module
    def exec_module(self, module): pass

class _ScafadNamespaceAlias(importlib.abc.MetaPathFinder):
    _PREFIX = "scafad."
    _LAYERS = frozenset(["layer0","layer1","layer2","layer3","layer4","layer5","layer6","runtime"])
    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(self._PREFIX): return None
        rest = fullname[len(self._PREFIX):]
        if rest.split(".")[0] not in self._LAYERS: return None
        if fullname in sys.modules: return None
        if rest not in sys.modules:
            try: importlib.import_module(rest)
            except ImportError: return None
        bare = sys.modules.get(rest)
        if bare is None: return None
        sys.modules[fullname] = bare
        spec = importlib.machinery.ModuleSpec(fullname, _AliasLoader(bare))
        spec.submodule_search_locations = getattr(bare, "__path__", None)
        return spec

if not any(isinstance(f, _ScafadNamespaceAlias) for f in sys.meta_path):
    sys.meta_path.insert(0, _ScafadNamespaceAlias())

from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score
from scafad.runtime import SCAFADCanonicalRuntime
import layer2.detection_matrix as _dm

DATASET_PATH    = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
BASELINE_PATH   = _REPO_ROOT / "evaluation" / "results" / "scafad_results.json"
OUTPUT_PATH     = _REPO_ROOT / "evaluation" / "results" / "ablation_semantic_deviation.json"

BENIGN = "benign"
SEED   = 42
ANOMALY_SAMPLE_PER_CLASS = 20   # 25 classes × 20 = 500 anomalous + 50 benign = 550 total

_DEC = {"observe":0,"review":1,"escalate":1,"benign":0,"alert":1,"error":1}

# ── Build stratified test subset ────────────────────────────────────────────
print("[ablation] Loading dataset...", flush=True)
with gzip.open(str(DATASET_PATH), "rt") as fh:
    all_records = json.load(fh)

rng = random.Random(SEED)
benign_all  = [r for r in all_records if r["anomaly_type"].lower() == BENIGN]
anomaly_all = [r for r in all_records if r["anomaly_type"].lower() != BENIGN]

# Hold out same 200 benign as the full pipeline evaluation
rng_b = random.Random(SEED)
rng_b.shuffle(benign_all)
test_benign  = benign_all[200:]   # 50 held-out benign records

# Stratified sample: 20 per anomaly class
by_class: Dict[str, List] = defaultdict(list)
for r in anomaly_all:
    by_class[r["anomaly_type"]].append(r)

test_anomaly = []
rng_a = random.Random(SEED)
for cls, recs in sorted(by_class.items()):
    rng_a.shuffle(recs)
    test_anomaly.extend(recs[:ANOMALY_SAMPLE_PER_CLASS])

test_records = test_benign + test_anomaly
rng.shuffle(test_records)   # mix benign and anomaly

n_benign  = sum(1 for r in test_records if r["anomaly_type"].lower() == BENIGN)
n_anomaly = sum(1 for r in test_records if r["anomaly_type"].lower() != BENIGN)
n_classes = len(by_class)
print(f"[ablation] Test subset: {len(test_records)} records | "
      f"benign={n_benign} anomalous={n_anomaly} classes={n_classes}", flush=True)

# ── Patch: replace SemanticDeviationCore with NullDetector ─────────────────
class _NullDetector:
    def evaluate(self, record: Dict[str, Any]) -> "_dm.DetectionSignal":
        return _dm.DetectionSignal(
            detector_name="semantic_deviation_ABLATED",
            score=0.0, confidence=0.0,
            rationale="SemanticDeviationCore ablated — oracle anomaly_type suppressed",
            evidence={"ablated": True},
        )

def _patched_init(self):
    from layer2.detection_matrix import RuleChainEngine, DriftTracker, GraphImmunizedDetector
    self.detectors = (RuleChainEngine(), DriftTracker(), GraphImmunizedDetector(), _NullDetector())

_dm.MultiVectorDetectionMatrix.__init__ = _patched_init

# ── Ablated evaluation pass ─────────────────────────────────────────────────
print("[ablation] Running ABLATED pass (SemanticDeviationCore → NullDetector)...", flush=True)
runtime   = SCAFADCanonicalRuntime()
y_true, y_pred, y_score = [], [], []
errors = 0
t0 = time.perf_counter()

for idx, record in enumerate(test_records):
    if idx > 0 and idx % 200 == 0:
        runtime = SCAFADCanonicalRuntime()

    gt = 0 if record["anomaly_type"].lower() == BENIGN else 1
    y_true.append(gt)
    try:
        res  = runtime.process_event(record, verbosity="terse")
        d    = res.multilayer_result.layer4.decision
        s    = float(res.multilayer_result.layer3.fused_score)
        pred = _DEC.get(d.lower(), 1)
    except Exception as e:
        d, pred, s = "error", 1, 1.0
        errors += 1
        if errors <= 3:
            print(f"  [warn] idx={idx}: {e}", flush=True)
    y_pred.append(pred); y_score.append(s)

elapsed = time.perf_counter() - t0

auc  = float(roc_auc_score(y_true, y_score))
prec = float(precision_score(y_true, y_pred, zero_division=0))
rec  = float(recall_score(y_true, y_pred, zero_division=0))
f1   = float(f1_score(y_true, y_pred, zero_division=0))

print(f"[ablation] Ablated ROC-AUC={auc:.4f}  F1={f1:.4f}  P={prec:.4f}  R={rec:.4f}  "
      f"errors={errors}  time={elapsed:.1f}s", flush=True)

# ── Load standard results ───────────────────────────────────────────────────
with open(str(BASELINE_PATH)) as fh:
    std_data = json.load(fh)
std = std_data["scafad"]

delta_auc = auc - std["roc_auc"]
delta_f1  = f1  - std["f1"]

print(f"\n{'='*60}")
print(f"ABLATION RESULT")
print(f"{'='*60}")
print(f"  Standard  (6300-record full run)")
print(f"    ROC-AUC = {std['roc_auc']:.4f}  F1 = {std['f1']:.4f}")
print(f"  Ablated   ({len(test_records)}-record stratified run, oracle-free)")
print(f"    ROC-AUC = {auc:.4f}  F1 = {f1:.4f}")
print(f"  Delta     ROC-AUC = {delta_auc:+.4f}  F1 = {delta_f1:+.4f}")
print(f"{'='*60}")

result = {
    "generated_at":      datetime.now(timezone.utc).isoformat(),
    "description": (
        "Oracle-leakage ablation: SemanticDeviationCore replaced with NullDetector "
        "(score=0.0, confidence=0.0). Standard results from full 6300-record run "
        "(scafad_results.json). Ablated run uses all 50 held-out benign records + "
        f"stratified {ANOMALY_SAMPLE_PER_CLASS} per anomaly class "
        f"({n_classes} classes = {n_anomaly} anomalous, {len(test_records)} total)."
    ),
    "semantic_deviation_core_behaviour": (
        "Reads ground-truth anomaly_type field. Adds 0.45 to score for any "
        "non-benign record, plus up to 0.35 for suspicious keyword tokens. "
        "Not available at inference time in production."
    ),
    "standard": {
        "source":       "scafad_results.json (full 6300-record run)",
        "test_records": std_data["test_records"],
        "roc_auc":      std["roc_auc"],
        "f1":           std["f1"],
        "precision":    std["precision"],
        "recall":       std["recall"],
    },
    "ablated": {
        "source":        "stratified subset, oracle label suppressed",
        "test_records":  len(test_records),
        "n_benign":      n_benign,
        "n_anomaly":     n_anomaly,
        "n_classes":     n_classes,
        "roc_auc":       round(auc,  6),
        "f1":            round(f1,   6),
        "precision":     round(prec, 6),
        "recall":        round(rec,  6),
        "errors":        errors,
        "elapsed_s":     round(elapsed, 2),
    },
    "delta": {
        "roc_auc": round(delta_auc, 6),
        "f1":      round(delta_f1,  6),
    },
}

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(str(OUTPUT_PATH), "w") as fh:
    json.dump(result, fh, indent=2)
print(f"\n[ablation] Written to {OUTPUT_PATH}", flush=True)
