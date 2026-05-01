#!/usr/bin/env python3
"""Dry-run: ablation on first 100 records to verify correctness."""

from __future__ import annotations
import gzip, importlib, importlib.abc, importlib.machinery, json, random, sys, time
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

from sklearn.metrics import roc_auc_score, f1_score
from scafad.runtime import SCAFADCanonicalRuntime
import layer2.detection_matrix as _dm

DATASET_PATH = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
BENIGN = "benign"
SEED = 42
N = 100  # dry run size

_DEC = {"observe":0,"review":1,"escalate":1,"benign":0,"alert":1,"error":1}

def load_subset():
    with gzip.open(str(DATASET_PATH), "rt") as fh:
        records = json.load(fh)
    benign  = [r for r in records if r["anomaly_type"].lower() == BENIGN]
    anomaly = [r for r in records if r["anomaly_type"].lower() != BENIGN]
    rng = random.Random(SEED)
    rng.shuffle(benign)
    test = benign[200:] + anomaly
    return test[:N]

def run(test, label):
    rt = SCAFADCanonicalRuntime()
    yt, yp, ys = [], [], []
    for i, rec in enumerate(test):
        yt.append(0 if rec["anomaly_type"].lower()==BENIGN else 1)
        try:
            res = rt.process_event(rec, verbosity="terse")
            d = res.multilayer_result.layer4.decision
            s = float(res.multilayer_result.layer3.fused_score)
            yt_pred = _DEC.get(d.lower(), 1)
        except Exception as e:
            d, yt_pred, s = "error", 1, 1.0
            print(f"  ERR {i}: {e}")
        yp.append(yt_pred); ys.append(s)
    auc = roc_auc_score(yt, ys) if len(set(yt)) > 1 else float("nan")
    f1  = f1_score(yt, yp, zero_division=0)
    print(f"  {label}: ROC-AUC={auc:.4f}  F1={f1:.4f}")
    return auc, f1

print("[dryrun] Loading 100-record subset...", flush=True)
test = load_subset()
print(f"[dryrun] Benign={sum(1 for r in test if r['anomaly_type'].lower()==BENIGN)}  Anomaly={sum(1 for r in test if r['anomaly_type'].lower()!=BENIGN)}", flush=True)

print("[dryrun] Pass 1: STANDARD", flush=True)
auc1, f11 = run(test, "STANDARD")

print("[dryrun] Patching SemanticDeviationCore...", flush=True)
class _Null:
    def evaluate(self, record):
        return _dm.DetectionSignal(
            detector_name="semantic_deviation_ABLATED",
            score=0.0, confidence=0.0,
            rationale="ablated", evidence={}
        )

orig_init = _dm.MultiVectorDetectionMatrix.__init__
def patched_init(self):
    from layer2.detection_matrix import RuleChainEngine, DriftTracker, GraphImmunizedDetector
    self.detectors = (RuleChainEngine(), DriftTracker(), GraphImmunizedDetector(), _Null())
_dm.MultiVectorDetectionMatrix.__init__ = patched_init

print("[dryrun] Pass 2: ABLATED", flush=True)
auc2, f12 = run(test, "ABLATED")

print(f"\n[dryrun] RESULT: delta_AUC={auc2-auc1:+.4f}  delta_F1={f12-f11:+.4f}")
print("[dryrun] DONE — full run will use 6300 records.")
