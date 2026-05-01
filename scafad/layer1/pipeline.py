"""Canonical Layer 1 intake pipeline for the module-split SCAFAD architecture.

P3.1 — Wire Layer 1 gateways into ``Layer1CanonicalPipeline``.

The pipeline is a *thin orchestrator* over the independently-tested Layer 1
gateway modules.  It adds no algorithmic logic of its own; every stage
delegates to its gateway:

    validate  → :class:`layer1.validation.InputValidationGateway`
    sanitise  → :class:`layer1.sanitisation.SanitisationProcessor`
    privacy   → :class:`layer1.privacy.PrivacyComplianceFilter`
    hashing   → :class:`layer1.hashing.DeferredHashingManager`
    preserve  → :func:`layer1.preservation.assess_preservation`

``Layer1CanonicalPipelineConfig`` is the single injection surface for
configuration — privacy regime, hash field list, hash algorithm, salt
handling, sanitiser toggles, and preservation epsilon.  The runtime owns
the config instance; the pipeline module ships sensible defaults and no
globals.
"""

from __future__ import annotations

import copy
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from layer0.app_telemetry import TelemetryRecord
from layer0.adapter import RCoreToLayer1Adapter

from .validation import InputValidationGateway
from .sanitisation import SanitisationFlag, SanitisationProcessor, SanitisationResult
from .privacy import (
    PrivacyComplianceFilter,
    PrivacyRegime,
    RedactionAction,
    RedactionResult,
)
from .hashing import DeferredHashingManager, HashingAction, HashingResult
from .preservation import PreservationAssessment, assess_preservation


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


# ---------------------------------------------------------------------------
# Public configuration surface
# ---------------------------------------------------------------------------

# Default dotted field paths the :class:`DeferredHashingManager` replaces
# with a keyed digest.  These paths match the exact layout produced by
# :class:`RCoreToLayer1Adapter`: ``concurrency_id`` is forwarded into the
# provenance chain, ``trigger_type`` into context metadata.  Absent paths
# are silently skipped by the gateway (fail-open).
_DEFAULT_HASH_FIELDS: Tuple[str, ...] = (
    "provenance_chain.concurrency_id",
    "context_metadata.trigger_type",
)

_DEFAULT_SANITISERS: Tuple[str, ...] = (
    "path",
    "url",
    "html",
    "sql",
    "command",
    "unicode",
)


@dataclass
class Layer1CanonicalPipelineConfig:
    """Injected configuration for :class:`Layer1CanonicalPipeline`.

    Attributes
    ----------
    privacy_regime:
        ``"GDPR"``, ``"CCPA"`` or ``"HIPAA"`` (case-insensitive).  Drives the
        pattern bank used by :class:`PrivacyComplianceFilter`.
    hash_fields:
        Dotted field paths to hash via
        :class:`DeferredHashingManager`.  Absent paths and anomaly-critical
        paths are silently skipped by the gateway; an empty tuple disables
        deferred hashing entirely.
    hash_algorithm:
        ``"sha256"`` (HMAC-SHA256) or ``"blake2b"`` (keyed BLAKE2b).
    salt:
        Optional explicit salt.  If ``None`` the gateway resolves from the
        environment variable named by *salt_env_var*.
    salt_env_var:
        Environment variable consulted by :class:`DeferredHashingManager`
        when *salt* is ``None``.  Documented only; the gateway reads
        ``SCAFAD_HASH_SALT`` directly.
    sanitisers:
        Sanitiser identifiers the processor may apply.  The canonical
        :class:`SanitisationProcessor` runs the full chain today; this
        tuple is retained for forward compatibility / auditability (a
        toggle list appears in the Layer 1 audit record).
    fail_on_validation_error:
        When ``True`` (default), a failing validation raises
        ``ValueError`` — preserving the existing raise-on-failure contract
        for callers such as ``SCAFADCanonicalRuntime``.  When ``False``
        the pipeline attaches the error list to the audit record and
        continues; useful for bulk re-ingest pipelines.
    preservation_epsilon:
        Numeric epsilon for critical-field comparisons in
        :func:`assess_preservation`.  Retained on the config for
        observability; the gateway currently uses its internal default.
    completeness_target:
        Threshold at which the quality report flags
        ``"preservation_below_target"``.
    """

    privacy_regime: str = "GDPR"
    hash_fields: Tuple[str, ...] = _DEFAULT_HASH_FIELDS
    hash_algorithm: str = "sha256"
    salt: Optional[str] = None
    salt_env_var: str = "SCAFAD_HASH_SALT"
    sanitisers: Tuple[str, ...] = _DEFAULT_SANITISERS
    fail_on_validation_error: bool = True
    preservation_epsilon: float = 1e-9
    completeness_target: float = 0.9995

    def to_dict(self) -> Dict[str, Any]:
        return {
            "privacy_regime": self.privacy_regime,
            "hash_fields": list(self.hash_fields),
            "hash_algorithm": self.hash_algorithm,
            "salt_env_var": self.salt_env_var,
            "sanitisers": list(self.sanitisers),
            "fail_on_validation_error": self.fail_on_validation_error,
            "preservation_epsilon": self.preservation_epsilon,
            "completeness_target": self.completeness_target,
        }


# ---------------------------------------------------------------------------
# Canonical dataclasses — returned to the runtime
# ---------------------------------------------------------------------------

@dataclass
class Layer1AuditRecord:
    """Structured record of every Layer 1 phase that ran for one event."""

    phases_completed: List[str] = field(default_factory=list)
    redacted_fields: List[str] = field(default_factory=list)
    hashed_fields: List[str] = field(default_factory=list)
    sanitiser_flags: List[Dict[str, Any]] = field(default_factory=list)
    privacy_actions: List[Dict[str, Any]] = field(default_factory=list)
    hashing_actions: List[Dict[str, Any]] = field(default_factory=list)
    preservation_at_risk: List[str] = field(default_factory=list)
    preservation_recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


@dataclass
class Layer1QualityReport:
    """Downstream-consumed quality assessment for a processed record."""

    completeness_score: float
    anomaly_signal_preservation: float
    pii_fields_redacted: int
    issues: List[str] = field(default_factory=list)


@dataclass
class Layer1ProcessedRecord:
    record_id: str
    function_name: str
    timestamp: float
    anomaly_type: str
    execution_phase: str
    schema_version: str
    telemetry_data: Dict[str, Any]
    context_metadata: Dict[str, Any]
    provenance_chain: Dict[str, Any]
    quality_report: Layer1QualityReport
    audit_record: Layer1AuditRecord
    trace_id: str
    trust_context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "function_name": self.function_name,
            "timestamp": self.timestamp,
            "anomaly_type": self.anomaly_type,
            "execution_phase": self.execution_phase,
            "schema_version": self.schema_version,
            "telemetry_data": copy.deepcopy(self.telemetry_data),
            "context_metadata": copy.deepcopy(self.context_metadata),
            "provenance_chain": copy.deepcopy(self.provenance_chain),
            "quality_report": {
                "completeness_score": self.quality_report.completeness_score,
                "anomaly_signal_preservation": self.quality_report.anomaly_signal_preservation,
                "pii_fields_redacted": self.quality_report.pii_fields_redacted,
                "issues": list(self.quality_report.issues),
            },
            "audit_record": {
                "phases_completed": list(self.audit_record.phases_completed),
                "redacted_fields": list(self.audit_record.redacted_fields),
                "hashed_fields": list(self.audit_record.hashed_fields),
                "sanitiser_flags": copy.deepcopy(self.audit_record.sanitiser_flags),
                "privacy_actions": copy.deepcopy(self.audit_record.privacy_actions),
                "hashing_actions": copy.deepcopy(self.audit_record.hashing_actions),
                "preservation_at_risk": list(self.audit_record.preservation_at_risk),
                "preservation_recommendations": list(
                    self.audit_record.preservation_recommendations
                ),
                "warnings": list(self.audit_record.warnings),
                "validation_errors": list(self.audit_record.validation_errors),
                "processing_time_ms": self.audit_record.processing_time_ms,
            },
            "trace_id": self.trace_id,
            "trust_context": copy.deepcopy(self.trust_context),
        }


# ---------------------------------------------------------------------------
# Regime resolution
# ---------------------------------------------------------------------------

_REGIME_BY_NAME: Dict[str, PrivacyRegime] = {
    "gdpr": PrivacyRegime.GDPR,
    "ccpa": PrivacyRegime.CCPA,
    "hipaa": PrivacyRegime.HIPAA,
}


def _resolve_regime(name: str) -> PrivacyRegime:
    """Map a case-insensitive string to a :class:`PrivacyRegime` member."""
    try:
        return _REGIME_BY_NAME[str(name).strip().lower()]
    except KeyError:
        raise ValueError(
            f"Unknown privacy regime {name!r}; expected one of "
            f"{sorted(_REGIME_BY_NAME)}"
        )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Layer1CanonicalPipeline:
    """Thin, deterministic orchestrator over the five Layer 1 gateways.

    Construct with an optional :class:`RCoreToLayer1Adapter` and an optional
    :class:`Layer1CanonicalPipelineConfig`.  ``process_l0_record`` runs the
    adapter; ``process_adapted_record`` runs the gateway chain on an already-
    adapted dict.  Both return a fully-populated :class:`Layer1ProcessedRecord`.
    """

    REQUIRED_FIELDS = (
        "record_id",
        "timestamp",
        "function_name",
        "execution_phase",
        "anomaly_type",
        "telemetry_data",
        "schema_version",
    )

    def __init__(
        self,
        adapter: Optional[RCoreToLayer1Adapter] = None,
        config: Optional[Layer1CanonicalPipelineConfig] = None,
    ) -> None:
        self.adapter = adapter or RCoreToLayer1Adapter()
        self.config = config or Layer1CanonicalPipelineConfig()

        # Real gateway instances — unit-tested independently.  Never
        # re-implemented here.
        self._validator = InputValidationGateway()
        self._sanitiser = SanitisationProcessor()
        self._privacy = PrivacyComplianceFilter()
        self._hasher = DeferredHashingManager(salt=self.config.salt)

        # Pre-resolve the regime so we fail fast on bad configuration rather
        # than silently falling back to GDPR on every invocation.
        self._regime: PrivacyRegime = _resolve_regime(self.config.privacy_regime)

    # ------------------------------------------------------------------
    # Public entrypoints
    # ------------------------------------------------------------------

    def process_l0_record(self, record: TelemetryRecord) -> Layer1ProcessedRecord:
        return self.process_adapted_record(self.adapter.adapt(record))

    def process_adapted_record(self, adapted: Dict[str, Any]) -> Layer1ProcessedRecord:
        """Run validate → sanitise → privacy → hashing → preservation.

        Populates :class:`Layer1QualityReport` and :class:`Layer1AuditRecord`
        directly from the gateway outputs — no stub placeholder values.
        """
        started = _now_ms()
        original = copy.deepcopy(adapted)
        working: Dict[str, Any] = copy.deepcopy(adapted)
        warnings: List[str] = []
        phases: List[str] = []
        validation_errors: List[str] = []

        # 1. Validation ------------------------------------------------------
        validation_errors = self._validate_shape(working)
        phases.append("validation")

        # 2. Sanitisation ----------------------------------------------------
        working, sanit_flags = self._sanitize_record(working)
        phases.append("sanitisation")

        # 3. Privacy ---------------------------------------------------------
        working, privacy_actions = self._apply_privacy(working)
        redacted_fields = sorted({a.field_path for a in privacy_actions})
        phases.append("privacy")

        # 4. Deferred hashing ------------------------------------------------
        working, hashing_actions = self._apply_hashing(working)
        hashed_fields = [a.field_path for a in hashing_actions]
        phases.append("hashing")

        # 5. Preservation assessment ----------------------------------------
        preservation = self._measure_preservation(original, working)
        phases.append("preservation")

        # 6. Quality + audit emission ---------------------------------------
        quality = self._assess_quality(working, preservation, len(privacy_actions))
        phases.append("quality")

        trace_id = self._build_trace_id(working)
        trust_context = self._build_trust_context(working, preservation.preservation_score)

        # Warnings: gateway diagnostics that did not block processing.
        warnings.extend(
            f"sanitisation:{f.field_path}:{f.sanitiser}" for f in sanit_flags
        )
        warnings.extend(preservation.recommendations)
        if validation_errors and not self.config.fail_on_validation_error:
            warnings.extend(f"validation:{msg}" for msg in validation_errors)

        audit = Layer1AuditRecord(
            phases_completed=phases + ["audit"],
            redacted_fields=redacted_fields,
            hashed_fields=hashed_fields,
            sanitiser_flags=[f.to_dict() for f in sanit_flags],
            privacy_actions=[a.to_dict() for a in privacy_actions],
            hashing_actions=[a.to_dict() for a in hashing_actions],
            preservation_at_risk=list(preservation.at_risk_fields),
            preservation_recommendations=list(preservation.recommendations),
            warnings=warnings,
            validation_errors=list(validation_errors),
            processing_time_ms=round(_now_ms() - started, 3),
        )

        return Layer1ProcessedRecord(
            record_id=str(working.get("record_id", "")),
            function_name=str(working.get("function_name", "")),
            timestamp=float(working.get("timestamp", 0.0) or 0.0),
            anomaly_type=str(working.get("anomaly_type", "")),
            execution_phase=str(working.get("execution_phase", "")),
            schema_version=str(working.get("schema_version", "")),
            telemetry_data=working.get("telemetry_data", {}) or {},
            context_metadata=working.get("context_metadata", {}) or {},
            provenance_chain=working.get("provenance_chain", {}) or {},
            quality_report=quality,
            audit_record=audit,
            trace_id=trace_id,
            trust_context=trust_context,
        )

    # ------------------------------------------------------------------
    # Gateway delegations — each stage is a one-liner onto a real module
    # ------------------------------------------------------------------

    def _validate_shape(self, record: Dict[str, Any]) -> List[str]:
        """Delegate to :class:`InputValidationGateway`.

        Accumulates every validation error into a list.  By default raises
        ``ValueError`` on failure (preserving the existing contract); if
        ``config.fail_on_validation_error`` is ``False`` the list is
        returned to the caller for soft-landing paths.
        """
        result = self._validator.validate(record)
        if result.valid:
            return []
        messages = [str(e) for e in result.errors]
        if self.config.fail_on_validation_error:
            raise ValueError(f"L1 validation failed: {'; '.join(messages)}")
        return messages

    def _sanitize_record(
        self, record: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[SanitisationFlag]]:
        """Delegate to :class:`SanitisationProcessor`.

        Returns a new record (sanitiser never mutates its input) plus the
        list of flags raised during the pass.
        """
        result: SanitisationResult = self._sanitiser.sanitise(record)
        return result.sanitised_record, list(result.flags)

    def _apply_privacy(
        self, record: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[RedactionAction]]:
        """Delegate to :class:`PrivacyComplianceFilter` under the configured regime."""
        result: RedactionResult = self._privacy.apply(record, regime=self._regime)
        return result.filtered_record, list(result.actions_taken)

    def _apply_hashing(
        self, record: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[HashingAction]]:
        """Delegate to :class:`DeferredHashingManager` with the configured field list.

        An empty ``config.hash_fields`` disables deferred hashing — the
        record is passed through untouched and no actions are emitted.
        """
        if not self.config.hash_fields:
            return record, []
        result: HashingResult = self._hasher.hash_fields(
            record,
            hash_fields=list(self.config.hash_fields),
            algorithm=self.config.hash_algorithm,
        )
        return result.hashed_record, list(result.actions)

    def _measure_preservation(
        self, original: Dict[str, Any], processed: Dict[str, Any]
    ) -> PreservationAssessment:
        """Delegate to :func:`assess_preservation`.

        Returns the full assessment (score + at-risk fields + recommendations)
        so the audit record can carry each piece verbatim.
        """
        return assess_preservation(original, processed)

    # ------------------------------------------------------------------
    # Quality / trust / trace — local assembly from gateway outputs
    # ------------------------------------------------------------------

    def _assess_quality(
        self,
        record: Dict[str, Any],
        preservation: PreservationAssessment,
        pii_fields_redacted: int,
    ) -> Layer1QualityReport:
        present = 0
        for field_name in self.REQUIRED_FIELDS:
            value = record.get(field_name)
            if value not in (None, "", {}):
                present += 1
        completeness = round(present / len(self.REQUIRED_FIELDS), 4)

        issues: List[str] = []
        if completeness < 1.0:
            issues.append("incomplete_required_fields")
        if preservation.preservation_score < self.config.completeness_target:
            issues.append("preservation_below_target")
        # Forward the gateway's own semantic recommendations verbatim so the
        # quality report is a faithful projection of real gateway output
        # rather than a stub summary.
        issues.extend(preservation.recommendations)

        return Layer1QualityReport(
            completeness_score=completeness,
            anomaly_signal_preservation=preservation.preservation_score,
            pii_fields_redacted=pii_fields_redacted,
            issues=issues,
        )

    def _build_trace_id(self, record: Dict[str, Any]) -> str:
        raw = (
            f"{record.get('record_id', '')}|"
            f"{record.get('function_name', '')}|"
            f"{record.get('timestamp', '')}"
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _build_trust_context(
        self, record: Dict[str, Any], preservation_score: float
    ) -> Dict[str, Any]:
        context = record.get("context_metadata", {}) or {}
        base_confidence = float(context.get("confidence_level", 0.8) or 0.8)
        trust_score = round(
            max(0.1, min(1.0, base_confidence * preservation_score)), 4
        )
        return {
            "confidence_level": base_confidence,
            "preservation_score": preservation_score,
            "trust_score": trust_score,
            "source_layer": "layer_1",
        }


__all__ = [
    "Layer1AuditRecord",
    "Layer1QualityReport",
    "Layer1ProcessedRecord",
    "Layer1CanonicalPipeline",
    "Layer1CanonicalPipelineConfig",
]
