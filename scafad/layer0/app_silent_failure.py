# app_silent_failure.py
from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .app_config import SilentFailureConfig  # assumed to exist
from .app_telemetry import TelemetryRecord   # assumed to exist

# --- Add near top (after imports) ---
from dataclasses import replace

@dataclass(frozen=True)
class SilentFailureTuning:
    w_consistency: float = 0.22
    w_function:   float = 0.22
    w_invariant:  float = 0.18
    w_corruption: float = 0.18
    w_trace:      float = 0.10
    w_sanity:     float = 0.10
    alert_threshold: float = 0.60
    prob_sensitivity: float = 1.0

    def bounded(self) -> "SilentFailureTuning":
        clamp = lambda x: max(0.0, min(1.0, x))
        return replace(
            self,
            w_consistency=clamp(self.w_consistency),
            w_function=clamp(self.w_function),
            w_invariant=clamp(self.w_invariant),
            w_corruption=clamp(self.w_corruption),
            w_trace=clamp(self.w_trace),
            w_sanity=clamp(self.w_sanity),
            alert_threshold=clamp(self.alert_threshold),
            prob_sensitivity=max(0.1, min(5.0, self.prob_sensitivity)),
        )

def load_tuning(config: SilentFailureConfig) -> SilentFailureTuning:
    base = SilentFailureTuning()
    # Optional: read stage, e.g. config.deployment_stage in {"DEV","TEST","RESEARCH","PROD"}
    stage = str(getattr(config, "deployment_stage", "PROD")).upper()
    if stage == "RESEARCH":
        base = replace(base, prob_sensitivity=1.4, alert_threshold=0.55)
    elif stage == "DEV":
        base = replace(base, prob_sensitivity=1.2, alert_threshold=0.50)
    elif stage == "TEST":
        base = replace(base, prob_sensitivity=1.0, alert_threshold=0.60)
    else:  # PROD
        base = replace(base, prob_sensitivity=0.9, alert_threshold=0.65)
    # Apply optional overrides from config
    for fld in base.__dataclass_fields__.keys():
        if hasattr(config, fld):
            base = replace(base, **{fld: getattr(config, fld)})
    return base.bounded()



# -------------------------- Data types --------------------------

@dataclass
class SemanticCheckResult:
    is_consistent: bool
    reason: Optional[str] = None
    confidence: float = 0.5


@dataclass
class InvariantResult:
    passed: bool
    reasons: List[str]
    score: float  # 0..1, where 1 means all invariants passed


@dataclass
class CorruptionResult:
    corrupted: bool
    reasons: List[str]
    score: float  # 0..1, where 1 means clean


@dataclass
class SemanticAnalysisReport:
    """
    Comprehensive analysis artefact for silent failure assessment.
    """
    consistency: SemanticCheckResult
    invariants: InvariantResult
    corruption: CorruptionResult
    function_semantics: SemanticCheckResult
    trace_semantics: SemanticCheckResult
    basic_sanity_score: float  # 0..1
    final_probability: float   # 0..1 likelihood of a silent failure
    rationale: List[str]

# -------------------------- Rule registry --------------------------

class SemanticRulesRegistry:
    """
    Holds lightweight, extensible, per-function semantic rules and invariants.

    Rules are intentionally simple and self-contained to avoid heavy dependencies.
    You can extend at runtime by passing a mapping in SilentFailureConfig
    (e.g., config.semantic_rules) with function_id → rule spec.
    """

    def __init__(self, config: SilentFailureConfig):
        self.config = config
        # Pull user-provided rules, fall back to defaults
        external_rules = getattr(config, "semantic_rules", {}) or {}
        self.rules = {**self._default_rules(), **external_rules}

    def _default_rules(self) -> Dict[str, Dict[str, Any]]:
        # A few pragmatic defaults; adjust as needed.
        return {
            "ml_inference": {
                "required_output_keys": ["prediction", "confidence"],
                "confidence_range": (0.0, 1.0),
                "forbid_nans": True,
            },
            "auth_service": {
                "required_output_keys": ["status", "user_id"],
                "allowed_status": {"ok", "denied", "error"},
            },
            "billing_service": {
                "required_output_keys": ["amount", "currency"],
                "currency_set": {"USD", "EUR", "GBP"},
                "amount_min": 0.0,
            },
        }

    def for_function(self, function_id: str) -> Dict[str, Any]:
        return self.rules.get(function_id, {})

InvariantFn = Tuple[str, float]  # (name, weight)

class InvariantRegistry:
    """
    Register per-function invariant callables:
    signature f(inp, out, telemetry, cfg) -> Optional[str] (reason if fails)
    """
    def __init__(self):
        self._fns: Dict[str, List[Tuple[InvariantFn, Any]]] = {"*": []}

    def register(self, function_id: str, name: str, weight: float, fn):
        self._fns.setdefault(function_id, []).append(((name, max(0.0, min(1.0, weight))), fn))

    def get(self, function_id: str) -> List[Tuple[InvariantFn, Any]]:
        return self._fns.get(function_id, []) + self._fns.get("*", [])

invariants = InvariantRegistry()

# Default invariants (global)
def inv_echo_correlation(inp, out, telemetry, cfg):
    a = inp.get("correlation_id")
    b = out.get("correlation_id") or out.get("corr_id") or out.get("request_id")
    return None if (a is not None and b is not None and str(a) == str(b)) else "Correlation ID not echoed"
invariants.register("*", "echo_correlation", 0.35, inv_echo_correlation)

def inv_input_hash(inp, out, telemetry, cfg):
    claimed = out.get("input_hash")
    if not claimed and cfg.get("require_input_hash_echo", False):
        return "input_hash missing"
    if claimed:
        actual = hashlib.sha256(json.dumps(inp, sort_keys=True, default=str).encode()).hexdigest()
        if not SilentFailureAnalyzer.constant_time_equal(claimed, actual):  # requires @staticmethod in class
            return "input_hash mismatch"
    return None
invariants.register("*", "input_hash", 0.30, inv_input_hash)



# -------------------------- Consistency checker --------------------------

class SemanticConsistencyChecker:
    """
    Semantic validator: input/output invariants, schema sanity, metamorphic hints.
    """

    def __init__(self, rules: SemanticRulesRegistry):
        self.rules = rules

    # --- Basic structure checks ---

    def _is_dict(self, x: Any) -> bool:
        return isinstance(x, dict)

    def _has_nans_or_infs(self, obj: Any) -> bool:
        """
        Recursively scan for NaN/Inf values in numerics.
        """
        try:
            if isinstance(obj, dict):
                return any(self._has_nans_or_infs(v) for v in obj.values())
            if isinstance(obj, (list, tuple)):
                return any(self._has_nans_or_infs(v) for v in obj)
            if isinstance(obj, (int, float)):
                return math.isnan(float(obj)) or math.isinf(float(obj))
        except Exception:
            return False
        return False

    def _keys_present(self, d: Dict[str, Any], keys: List[str]) -> bool:
        return all(k in d for k in keys)

    # --- Public API ---

    def check_input_output_consistency(
        self, input_data: Dict[str, Any], output_data: Dict[str, Any]
    ) -> SemanticCheckResult:
        if output_data is None:
            return SemanticCheckResult(False, "Output is None", 0.05)
        if not self._is_dict(output_data):
            return SemanticCheckResult(False, "Output must be a dict", 0.1)
        if self._has_nans_or_infs(output_data):
            return SemanticCheckResult(False, "Output contains NaN/Inf", 0.2)

        # Lightweight size sanity: output should not be absurdly small/large for typical functions
        out_len = len(json.dumps(output_data, default=str)) if output_data else 0
        if out_len == 0:
            return SemanticCheckResult(False, "Empty output", 0.25)
        if out_len > 2_000_000:  # ~2MB
            return SemanticCheckResult(False, "Output excessively large", 0.4)

        return SemanticCheckResult(True, "Basic IO consistency OK", 0.7)

    def validate_function_semantics(
        self,
        function_id: str,
        io_pair: Tuple[Dict[str, Any], Dict[str, Any]],
    ) -> SemanticCheckResult:
        rules = self.rules.for_function(function_id)
        _, outp = io_pair

        # Required keys
        req = rules.get("required_output_keys", [])
        if req and not self._keys_present(outp, req):
            return SemanticCheckResult(False, f"Missing required keys: {req}", 0.3)

        # Confidence range for inference-like services
        if "confidence_range" in rules and "confidence" in outp:
            lo, hi = rules["confidence_range"]
            try:
                c = float(outp["confidence"])
                if not (lo <= c <= hi):
                    return SemanticCheckResult(False, f"Confidence out of range [{lo}, {hi}]", 0.35)
            except Exception:
                return SemanticCheckResult(False, "Confidence not numeric", 0.35)

        # Allowed status set
        if "allowed_status" in rules and "status" in outp:
            allowed = set(rules["allowed_status"])
            if outp["status"] not in allowed:
                return SemanticCheckResult(False, "Status not allowed", 0.4)

        # Currency & amount checks for billing-like services
        if "currency_set" in rules and "currency" in outp:
            if outp["currency"] not in set(rules["currency_set"]):
                return SemanticCheckResult(False, "Unsupported currency", 0.4)
        if "amount_min" in rules and "amount" in outp:
            try:
                if float(outp["amount"]) < float(rules["amount_min"]):
                    return SemanticCheckResult(False, "Negative/invalid amount", 0.4)
            except Exception:
                return SemanticCheckResult(False, "Amount not numeric", 0.4)

        # Forbid NaNs if requested
        if rules.get("forbid_nans") and self._has_nans_or_infs(outp):
            return SemanticCheckResult(False, "NaN/Inf prohibited by rule", 0.45)

        return SemanticCheckResult(True, "Function semantics OK", 0.75)

    def detect_semantic_anomalies(self, execution_trace: Dict[str, Any], telemetry: Optional[TelemetryRecord] = None) -> SemanticCheckResult:
        """
        Validate coarse-grained execution semantics in a trace:
        - Monotonic timestamps
        - Phase ordering INIT -> INVOKE -> TEARDOWN (if present)
        - Duration sanity (if telemetry provided)
        """
        phases = execution_trace.get("phases", [])
        timestamps = execution_trace.get("timestamps", [])
        if timestamps and any(timestamps[i] > timestamps[i + 1] for i in range(len(timestamps) - 1)):
            return SemanticCheckResult(False, "Non-monotonic timestamps", 0.4)

        if phases:
            ordering = {"INIT": 0, "INVOKE": 1, "TEARDOWN": 2}
            codes = [ordering.get(p, 99) for p in phases]
            if any(codes[i] > codes[i + 1] for i in range(len(codes) - 1)):
                return SemanticCheckResult(False, "Phase misordering", 0.45)

        if telemetry is not None:
            dur = float(getattr(telemetry, "duration", 0.0))
            if dur < 0:
                return SemanticCheckResult(False, "Negative duration", 0.4)
            # very gentle upper bound, overridable via config on rules.config
            max_dur = float(getattr(self.rules.config, "max_duration_s", 60.0))
            if dur > max_dur:
                return SemanticCheckResult(False, "Excessive duration", 0.45)

        return SemanticCheckResult(True, "Trace semantics OK", 0.65)



# -------------------------- Silent failure analysis --------------------------

class SilentFailureAnalyzer:
    """
    Detects silent corruption / semantic failures absent overt errors by fusing:
    - IO consistency checks
    - Per-function semantic rules
    - Invariant checks (metamorphic & structural)
    - Data corruption heuristics
    - Trace-level semantic constraints
    - Basic statistical sanity signals

    All weights/thresholds read from SilentFailureConfig if available;
    safe defaults applied otherwise to avoid tight coupling to config schema.
    """

    def __init__(self, config: SilentFailureConfig):
        self.config = config
        self.rules = SemanticRulesRegistry(config)
        self.checker = SemanticConsistencyChecker(self.rules)

        # Scoring weights (fallback to defaults if not provided in config)
        self.tuning = load_tuning(config)
        self.w_consistency = self.tuning.w_consistency
        self.w_function    = self.tuning.w_function
        self.w_invariant   = self.tuning.w_invariant
        self.w_corruption  = self.tuning.w_corruption
        self.w_trace       = self.tuning.w_trace
        self.w_sanity      = self.tuning.w_sanity
        self.alert_threshold = float(getattr(config, "alert_threshold", self.tuning.alert_threshold))

    # -------- Public API --------

    def detect_silent_failure(self, execution_record: Dict[str, Any]) -> float:
        """
        Return calibrated probability (0..1) that a silent failure occurred.
        """
        report = self.analyze(execution_record)
        return report.final_probability

    def analyze(self, execution_record: Dict[str, Any]) -> SemanticAnalysisReport:
        """
        Full analysis with rationale. `execution_record` is expected to contain:
            input:  Dict
            output: Dict
            function_id: str
            telemetry: Optional[TelemetryRecord]
            trace: Optional[Dict] (phases, timestamps, etc.)
        """
        function_id = str(execution_record.get("function_id", "unknown"))
        inp = execution_record.get("input", {}) or {}
        out = execution_record.get("output", {}) or {}
        trace = execution_record.get("trace", {}) or {}
        telemetry: Optional[TelemetryRecord] = execution_record.get("telemetry")

        # 1) IO consistency
        consistency = self.checker.check_input_output_consistency(inp, out)

        # 2) Function-specific semantics
        func_sem = self.checker.validate_function_semantics(function_id, (inp, out))

        # 3) Invariants (metamorphic & structural)
        inv_res = self._check_invariants(function_id, inp, out, telemetry)

        # 4) Data corruption heuristics
        corr_res = self._detect_data_corruption(inp, out, telemetry)

        # 5) Trace-level semantics
        trace_res = self.checker.detect_semantic_anomalies(trace, telemetry)

        # 6) Basic statistical sanity (quick-and-dirty)
        sanity_score = self._basic_sanity_checks(out)

        # Fuse into probability of failure
        failure_prob = self._fuse_probability(
            consistency=consistency,
            function_semantics=func_sem,
            invariants=inv_res,
            corruption=corr_res,
            trace_semantics=trace_res,
            sanity_score=sanity_score,
        )

        rationale = []
        if not consistency.is_consistent:
            rationale.append(f"IO: {consistency.reason}")
        if not func_sem.is_consistent:
            rationale.append(f"FUNC({function_id}): {func_sem.reason}")
        if inv_res.score < 1.0:
            rationale.extend([f"INV: {r}" for r in inv_res.reasons])
        if corr_res.corrupted:
            rationale.extend([f"CORRUPTION: {r}" for r in corr_res.reasons])
        if not trace_res.is_consistent:
            rationale.append(f"TRACE: {trace_res.reason}")
        if sanity_score < 0.7:
            rationale.append("SANITY: low output sanity score")

        return SemanticAnalysisReport(
            consistency=consistency,
            invariants=inv_res,
            corruption=corr_res,
            function_semantics=func_sem,
            trace_semantics=trace_res,
            basic_sanity_score=sanity_score,
            final_probability=failure_prob,
            rationale=rationale,
        )

    # -------- Fusion & scoring --------

    def _fuse_probability(
        self,
        *,
        consistency: SemanticCheckResult,
        function_semantics: SemanticCheckResult,
        invariants: InvariantResult,
        corruption: CorruptionResult,
        trace_semantics: SemanticCheckResult,
        sanity_score: float,
    ) -> float:
        """
        Convert heterogeneous signals into a 0..1 probability.
        We invert “scores” to represent risk and combine with weights.
        """
        risk_consistency = 1.0 - float(consistency.confidence if consistency.is_consistent else 0.0)
        risk_function    = 1.0 - float(function_semantics.confidence if function_semantics.is_consistent else 0.0)
        risk_invariant   = 1.0 - float(invariants.score)
        risk_corruption  = 1.0 - float(corruption.score)
        risk_trace       = 1.0 - float(trace_semantics.confidence if trace_semantics.is_consistent else 0.0)
        risk_sanity      = 1.0 - float(sanity_score)

        raw = (
            self.w_consistency * risk_consistency
            + self.w_function   * risk_function
            + self.w_invariant  * risk_invariant
            + self.w_corruption * risk_corruption
            + self.w_trace      * risk_trace
            + self.w_sanity     * risk_sanity
        )

        # Calibrate gently (squash slightly to avoid extremal overconfidence)
        calibrated = max(0.0, min(1.0, 0.15 + 0.85 * raw))
        return calibrated

    # -------- Invariants --------

    def _check_invariants(
        self,
        function_id: str,
        inp: Dict[str, Any],
        out: Dict[str, Any],
        telemetry: Optional[TelemetryRecord],
    ) -> InvariantResult:
        reasons: List[str] = []
        passed_w = 0.0
        total_w = 0.0

        # 1) Registry-driven invariants (weighted)
        func_rules = invariants.get(function_id)
        func_cfg = (getattr(self.config, "invariants", {}) or {}).get(function_id, {})
        for (name, weight), fn in func_rules:
            total_w += weight
            reason = fn(inp, out, telemetry, func_cfg)
            if reason is None:
                passed_w += weight
            else:
                reasons.append(f"{name}: {reason}")

        # 2) Config-driven extras (unweighted but counted)
        extras_total = 0
        extras_passed = 0

        # Monotonic key check (if required/present)
        monotonic_key = func_cfg.get("monotonic_key")
        if monotonic_key:
            extras_total += 1
            if monotonic_key in out:
                try:
                    if float(out[monotonic_key]) >= 0.0:
                        extras_passed += 1
                    else:
                        reasons.append(f"{monotonic_key}: negative")
                except Exception:
                    reasons.append(f"{monotonic_key}: not numeric")
            elif func_cfg.get("require_monotonic_key"):
                reasons.append("monotonic_key missing in output")

        # Preserve-keys requirement
        must_preserve: List[str] = func_cfg.get("preserve_keys", [])
        if must_preserve:
            extras_total += 1
            missing = [k for k in must_preserve if out.get(k) != inp.get(k)]
            if not missing:
                extras_passed += 1
            else:
                reasons.append(f"preserve_keys mismatch: {missing}")

        # Merge weighted (registry) and unweighted (extras) scores
        # Convert extras into a pseudo-weight equal to the average invariant weight or 1.0 fallback
        avg_w = (total_w / len(func_rules)) if func_rules else 1.0
        total_w += extras_total * avg_w
        passed_w += extras_passed * avg_w

        score = 1.0 if total_w == 0 else max(0.0, min(1.0, passed_w / total_w))
        return InvariantResult(passed=(score == 1.0), reasons=reasons, score=score)


    # -------- Corruption detection --------

    def _detect_data_corruption(
        self,
        inp: Dict[str, Any],
        out: Dict[str, Any],
        telemetry: Optional[TelemetryRecord],
    ) -> CorruptionResult:
        reasons: List[str] = []
        score = 1.0  # start clean; ratchet down as evidence accumulates

        # 1) Integrity fields (output_hash over output payload, if provided)
        declared_output_hash = out.get("output_hash")
        if declared_output_hash:
            actual_output_hash = self._hash_json(out.get("data", out))
            if not self.constant_time_equal(declared_output_hash, actual_output_hash):
                reasons.append("output_hash mismatch")
                score = min(score, 0.40)  # strong indicator

        # 2) Nesting depth threshold to avoid extreme structures
        if self._max_nesting_depth(out) > int(getattr(self.config, "max_output_nesting", 25)):
            reasons.append("excessive output nesting depth")
            score = min(score, 0.60)  # moderate indicator

        # 3) Robust magnitude shift using MAD-based z-score
        in_nums = self._collect_numerics(inp)
        out_nums = self._collect_numerics(out)
        if len(in_nums) >= 5 and len(out_nums) >= 5:
            out_med = statistics.median(out_nums)
            z = self._robust_z(in_nums, out_med)
            z_thresh = float(getattr(self.config, "robust_magnitude_z", 6.0))
            if z > z_thresh:
                reasons.append(f"robust magnitude shift z={z:.2f}")
                # Map z to a capped penalty: z>=10 → at most 0.5 reduction
                severity = min(1.0, z / 10.0)
                score = min(score, max(0.25, 1.0 - 0.5 * severity))

        corrupted = len(reasons) > 0
        # If multiple reasons, ensure we never “recover” above the smallest score
        return CorruptionResult(corrupted=corrupted, reasons=reasons, score=score)


    def _robust_z(self, values: List[float], x: float) -> float:
        if not values:
            return 0.0
        med = statistics.median(values)
        mad = statistics.median([abs(v - med) for v in values]) or 1e-9
        return abs(x - med) / (1.4826 * mad)  # 1.4826 ≈ normalising constant


    # -------- Sanity checks --------

    def _basic_sanity_checks(self, out: Dict[str, Any]) -> float:
        """
        Produce a coarse 0..1 sanity score based on:
        - Size within plausible bounds
        - No NaN/Inf
        - Limited key explosion
        """
        try:
            s = json.dumps(out, default=str)
        except Exception:
            return 0.2

        if len(s) == 0:
            return 0.2
        if len(s) > 5_000_000:  # 5MB
            return 0.3

        if self.checker._has_nans_or_infs(out):
            return 0.3

        if isinstance(out, dict) and len(out.keys()) > int(getattr(self.config, "max_output_keys", 5000)):
            return 0.4

        return 0.85  # default healthy value

    # -------- Utilities --------

    def _hash_json(self, obj: Any, algo: str = "sha256") -> str:
        h = hashlib.new(algo)
        h.update(json.dumps(obj, sort_keys=True, default=str).encode("utf-8"))
        return h.hexdigest()

    @staticmethod
    def constant_time_equal(a: str, b: str) -> bool:
        if not isinstance(a, str) or not isinstance(b, str):
            return False
        if len(a) != len(b):
            return False
        result = 0
        for x, y in zip(a.encode("utf-8"), b.encode("utf-8")):
            result |= x ^ y
        return result == 0

    def _max_nesting_depth(self, obj: Any, depth: int = 0) -> int:
        if isinstance(obj, dict):
            if not obj:
                return depth + 1
            return max(self._max_nesting_depth(v, depth + 1) for v in obj.values())
        if isinstance(obj, list):
            if not obj:
                return depth + 1
            return max(self._max_nesting_depth(v, depth + 1) for v in obj)
        return depth + 1

    def _collect_numerics(self, obj: Any, acc: Optional[List[float]] = None) -> List[float]:
        if acc is None:
            acc = []
        if isinstance(obj, dict):
            for v in obj.values():
                self._collect_numerics(v, acc)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                self._collect_numerics(v, acc)
        else:
            try:
                if isinstance(obj, (int, float)) and math.isfinite(float(obj)):
                    acc.append(float(obj))
            except Exception:
                pass
        return acc

# -------------------------- Calibration & Serialisation --------------------------

def _calibrate_probability(p: float, sensitivity: float = 1.0) -> float:
    """
    Optional extra calibration layer (e.g., temperature scaling).
    sensitivity > 1.0 → more sensitive (higher probabilities).
    """
    p = max(0.0, min(1.0, p))
    # Smoothstep-like shaping for nicer behaviour near extremes
    shaped = p * p * (3 - 2 * p)
    out = 1 - math.exp(-sensitivity * shaped)
    return max(0.0, min(1.0, out))


def report_to_dict(report: SemanticAnalysisReport) -> Dict[str, Any]:
    """
    JSON-safe serialisation of the full analysis artefact.
    """
    return {
        "consistency": {
            "is_consistent": report.consistency.is_consistent,
            "reason": report.consistency.reason,
            "confidence": report.consistency.confidence,
        },
        "invariants": {
            "passed": report.invariants.passed,
            "reasons": list(report.invariants.reasons),
            "score": report.invariants.score,
        },
        "corruption": {
            "corrupted": report.corruption.corrupted,
            "reasons": list(report.corruption.reasons),
            "score": report.corruption.score,
        },
        "function_semantics": {
            "is_consistent": report.function_semantics.is_consistent,
            "reason": report.function_semantics.reason,
            "confidence": report.function_semantics.confidence,
        },
        "trace_semantics": {
            "is_consistent": report.trace_semantics.is_consistent,
            "reason": report.trace_semantics.reason,
            "confidence": report.trace_semantics.confidence,
        },
        "basic_sanity_score": report.basic_sanity_score,
        "final_probability": report.final_probability,
        "rationale": list(report.rationale),
    }


# -------------------------- Public convenience API --------------------------

def assess_silent_failure(
    execution_record: Dict[str, Any],
    config: SilentFailureConfig,
    *,
    return_report: bool = False,
    sensitivity: Optional[float] = None,
) -> Any:
    """
    High-level entrypoint:
      - Builds the analyzer
      - Runs full analysis
      - Applies final probability calibration (optional)
      - Returns probability or full JSON-safe report
    """
    analyzer = SilentFailureAnalyzer(config)
    report = analyzer.analyze(execution_record)

    # Optional global calibration knob (e.g., environment/stage specific)
    sens = float(analyzer.tuning.prob_sensitivity if sensitivity is None else sensitivity)

    calibrated = _calibrate_probability(report.final_probability, sensitivity=sens)

    # Stitch calibrated probability back into artefact
    report.final_probability = calibrated

    if return_report:
        return report_to_dict(report)
    return calibrated


# -------------------------- Module exports --------------------------

__all__ = [
    "SemanticCheckResult",
    "InvariantResult",
    "CorruptionResult",
    "SemanticAnalysisReport",
    "SemanticRulesRegistry",
    "SemanticConsistencyChecker",
    "SilentFailureAnalyzer",
    "assess_silent_failure",
    "report_to_dict",
]
