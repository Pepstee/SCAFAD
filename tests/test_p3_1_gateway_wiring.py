"""
Tests — P3.1 — Wire Layer 1 gateways into Layer1CanonicalPipeline
=================================================================

Tester task: 0017dfb1-c6dc-4e17-8531-5c5a7d4d843d
Source task: fe5c9004-8085-4f32-a908-503d36451e5a

Acceptance criteria:
  - _sanitize_record delegates to SanitisationProcessor (no inline logic)
  - _apply_privacy delegates to PrivacyComplianceFilter (no inline regex)
  - _apply_hashing delegates to DeferredHashingManager w/ configurable field list
  - _measure_preservation delegates to assess_preservation(original, processed)
  - Layer1CanonicalPipelineConfig accepted by pipeline + consumed by runtime
  - Layer1QualityReport and Layer1AuditRecord populated from real gateway outputs
  - Tests verify each gateway is invoked and its output is reflected in quality/audit
  - Existing layer1 tests remain green

These tests are written so they FAIL if the implementation is missing or broken —
all assertions target real gateway-delegated behaviour, not stub placeholders.
"""
from __future__ import annotations

import copy
from typing import Any, Dict
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _adapted_record(**overrides: Any) -> Dict[str, Any]:
    """Return a minimal but fully-valid already-adapted L1 record."""
    base: Dict[str, Any] = {
        "record_id": "p3-test-record-001",
        "timestamp": 1_714_000_000.0,
        "function_name": "test-lambda",
        "execution_phase": "execution",
        "anomaly_type": "benign",
        "schema_version": "v2.1",
        "telemetry_data": {
            "l0_duration_ms": 55.0,
            "l0_memory_spike_kb": 256,
            "l0_cpu_utilization": 18.5,
            "l0_network_io_bytes": 512,
            "l0_fallback_mode": False,
        },
        "context_metadata": {
            "adversarial_score": 0.0,
            "economic_risk_score": 0.0,
            "confidence_level": 0.95,
            "trigger_type": "http",
        },
        "provenance_chain": {
            "source_layer": "layer_0",
            "concurrency_id": "conc-p3-test-001",
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Layer1CanonicalPipelineConfig — public surface
# ---------------------------------------------------------------------------

class TestLayer1CanonicalPipelineConfig:
    """Config dataclass is the only injection surface; defaults must match the
    architecture contract in SCAFAD_MASTER_BLUEPRINT §3.1."""

    def test_config_imports_cleanly(self):
        from layer1.pipeline import Layer1CanonicalPipelineConfig  # noqa: F401

    def test_default_privacy_regime_is_gdpr(self):
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        cfg = Layer1CanonicalPipelineConfig()
        assert cfg.privacy_regime == "GDPR"

    def test_default_hash_algorithm_is_sha256(self):
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        cfg = Layer1CanonicalPipelineConfig()
        assert cfg.hash_algorithm == "sha256"

    def test_default_fail_on_validation_error_is_true(self):
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        cfg = Layer1CanonicalPipelineConfig()
        assert cfg.fail_on_validation_error is True

    def test_default_hash_fields_include_trigger_type(self):
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        cfg = Layer1CanonicalPipelineConfig()
        assert "context_metadata.trigger_type" in cfg.hash_fields

    def test_default_hash_fields_include_concurrency_id(self):
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        cfg = Layer1CanonicalPipelineConfig()
        assert "provenance_chain.concurrency_id" in cfg.hash_fields

    def test_custom_regime_is_accepted(self):
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        cfg = Layer1CanonicalPipelineConfig(privacy_regime="HIPAA")
        assert cfg.privacy_regime == "HIPAA"

    def test_to_dict_contains_all_required_keys(self):
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        d = Layer1CanonicalPipelineConfig().to_dict()
        for key in ("privacy_regime", "hash_fields", "hash_algorithm",
                    "sanitisers", "fail_on_validation_error",
                    "preservation_epsilon", "completeness_target"):
            assert key in d, f"to_dict() is missing key: {key!r}"

    def test_to_dict_regime_reflects_custom_value(self):
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        d = Layer1CanonicalPipelineConfig(privacy_regime="CCPA").to_dict()
        assert d["privacy_regime"] == "CCPA"

    def test_empty_hash_fields_tuple_accepted(self):
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        cfg = Layer1CanonicalPipelineConfig(hash_fields=())
        assert cfg.hash_fields == ()


# ---------------------------------------------------------------------------
# 2. Layer1CanonicalPipeline — constructor and config wiring
# ---------------------------------------------------------------------------

class TestPipelineConstructor:
    """Pipeline constructor must fail-fast on bad config and carry its config."""

    def test_pipeline_imports_cleanly(self):
        from layer1.pipeline import Layer1CanonicalPipeline  # noqa: F401

    def test_pipeline_accepts_config_and_stores_it(self):
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        cfg = Layer1CanonicalPipelineConfig(privacy_regime="CCPA")
        pipe = Layer1CanonicalPipeline(config=cfg)
        assert pipe.config is cfg

    def test_default_config_created_when_none_passed(self):
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        pipe = Layer1CanonicalPipeline()
        assert isinstance(pipe.config, Layer1CanonicalPipelineConfig)

    def test_invalid_privacy_regime_raises_value_error_at_construction(self):
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        with pytest.raises(ValueError, match="regime"):
            Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
                privacy_regime="INVALID-REGIME"
            ))

    def test_all_regime_variants_accepted(self):
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        for regime in ("GDPR", "CCPA", "HIPAA"):
            pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
                privacy_regime=regime
            ))
            assert pipe.config.privacy_regime == regime


# ---------------------------------------------------------------------------
# 3. Validation gateway delegation
# ---------------------------------------------------------------------------

class TestValidationGatewayDelegation:
    """_validate_shape must call InputValidationGateway.validate(), not inline logic."""

    def test_validation_gateway_is_called_exactly_once(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        pipe = Layer1CanonicalPipeline()
        with mock.patch.object(
            pipe._validator, "validate", wraps=pipe._validator.validate
        ) as spy:
            pipe.process_adapted_record(_adapted_record())
        assert spy.call_count == 1

    def test_missing_required_field_raises_by_default(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        del rec["record_id"]
        pipe = Layer1CanonicalPipeline()
        with pytest.raises(ValueError):
            pipe.process_adapted_record(rec)

    def test_missing_required_field_soft_lands_when_configured(self):
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        rec = _adapted_record()
        del rec["function_name"]
        pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
            fail_on_validation_error=False
        ))
        result = pipe.process_adapted_record(rec)
        assert result.audit_record.validation_errors  # gateway's error strings attached

    def test_valid_record_has_empty_validation_errors(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert result.audit_record.validation_errors == []

    def test_validation_phase_is_listed_in_phases_completed(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert "validation" in result.audit_record.phases_completed


# ---------------------------------------------------------------------------
# 4. Sanitisation gateway delegation
# ---------------------------------------------------------------------------

class TestSanitisationGatewayDelegation:
    """_sanitize_record must call SanitisationProcessor.sanitise(), not inline logic."""

    def test_sanitisation_gateway_is_called_exactly_once(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        pipe = Layer1CanonicalPipeline()
        with mock.patch.object(
            pipe._sanitiser, "sanitise", wraps=pipe._sanitiser.sanitise
        ) as spy:
            pipe.process_adapted_record(_adapted_record())
        assert spy.call_count == 1

    def test_shell_metacharacters_produce_command_flag_in_audit(self):
        """SanitisationProcessor detects shell injection; flag must surface in audit."""
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        rec["context_metadata"]["user_cmd"] = "rm -rf /; echo pwned"
        result = Layer1CanonicalPipeline().process_adapted_record(rec)
        flag_sanitisers = {f["sanitiser"] for f in result.audit_record.sanitiser_flags}
        assert "command" in flag_sanitisers, (
            "Shell metacharacters must trigger the 'command' sanitiser; "
            f"got flags: {flag_sanitisers}"
        )

    def test_sanitisation_phase_listed_in_phases_completed(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert "sanitisation" in result.audit_record.phases_completed

    def test_sanitiser_flags_are_dicts_with_expected_keys(self):
        """sanitiser_flags are projected from gateway dataclasses via to_dict()."""
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        rec["context_metadata"]["dirty"] = "rm -rf /"
        result = Layer1CanonicalPipeline().process_adapted_record(rec)
        for flag in result.audit_record.sanitiser_flags:
            assert isinstance(flag, dict)
            # Gateway SanitisationFlag.to_dict() must emit at least these keys
            assert "field_path" in flag
            assert "sanitiser" in flag


# ---------------------------------------------------------------------------
# 5. Privacy gateway delegation
# ---------------------------------------------------------------------------

class TestPrivacyGatewayDelegation:
    """_apply_privacy must call PrivacyComplianceFilter.apply(), not inline regex."""

    def test_privacy_gateway_is_called_exactly_once(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        pipe = Layer1CanonicalPipeline()
        with mock.patch.object(
            pipe._privacy, "apply", wraps=pipe._privacy.apply
        ) as spy:
            pipe.process_adapted_record(_adapted_record())
        assert spy.call_count == 1

    def test_email_in_record_surfaces_in_pii_fields_redacted(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        rec["context_metadata"]["user_email"] = "tester@example.com"
        result = Layer1CanonicalPipeline().process_adapted_record(rec)
        assert result.quality_report.pii_fields_redacted >= 1

    def test_ssn_and_email_both_redacted(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        rec["context_metadata"]["email"] = "user@example.com"
        rec["context_metadata"]["ssn"] = "123-45-6789"
        result = Layer1CanonicalPipeline().process_adapted_record(rec)
        assert result.quality_report.pii_fields_redacted >= 2

    def test_email_value_not_present_in_processed_record(self):
        """After privacy filtering, raw PII must not survive in output."""
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        raw_email = "victim@example.com"
        rec["context_metadata"]["user_email"] = raw_email
        result = Layer1CanonicalPipeline().process_adapted_record(rec)
        # The value must have been redacted
        assert result.context_metadata.get("user_email") != raw_email

    def test_redacted_fields_in_audit_contain_field_path_info(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        rec["context_metadata"]["user_email"] = "test@test.com"
        result = Layer1CanonicalPipeline().process_adapted_record(rec)
        assert result.audit_record.redacted_fields  # non-empty

    def test_privacy_actions_contain_required_gateway_keys(self):
        """privacy_actions are projected from RedactionAction.to_dict()."""
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        rec["context_metadata"]["email"] = "pii@example.com"
        result = Layer1CanonicalPipeline().process_adapted_record(rec)
        assert result.audit_record.privacy_actions
        action = result.audit_record.privacy_actions[0]
        assert "field_path" in action
        assert "pattern_matched" in action
        assert "regime" in action

    def test_hipaa_regime_passed_to_privacy_gateway(self):
        """Configured regime must flow verbatim to PrivacyComplianceFilter.apply()."""
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        from layer1.privacy import PrivacyRegime
        pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
            privacy_regime="HIPAA"
        ))
        with mock.patch.object(
            pipe._privacy, "apply", wraps=pipe._privacy.apply
        ) as spy:
            pipe.process_adapted_record(_adapted_record())
        assert spy.call_args.kwargs["regime"] == PrivacyRegime.HIPAA

    def test_ccpa_regime_passed_to_privacy_gateway(self):
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        from layer1.privacy import PrivacyRegime
        pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
            privacy_regime="CCPA"
        ))
        with mock.patch.object(
            pipe._privacy, "apply", wraps=pipe._privacy.apply
        ) as spy:
            pipe.process_adapted_record(_adapted_record())
        assert spy.call_args.kwargs["regime"] == PrivacyRegime.CCPA

    def test_privacy_phase_listed_in_phases_completed(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert "privacy" in result.audit_record.phases_completed


# ---------------------------------------------------------------------------
# 6. Hashing gateway delegation
# ---------------------------------------------------------------------------

class TestHashingGatewayDelegation:
    """_apply_hashing must call DeferredHashingManager.hash_fields(), not inline hashlib."""

    def test_hashing_gateway_is_called_exactly_once(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        pipe = Layer1CanonicalPipeline()
        with mock.patch.object(
            pipe._hasher, "hash_fields", wraps=pipe._hasher.hash_fields
        ) as spy:
            pipe.process_adapted_record(_adapted_record())
        assert spy.call_count == 1

    def test_configured_hash_fields_appear_in_audit_record(self):
        """Custom hash_fields list — not hardcoded defaults — must drive the gateway."""
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        custom = ("context_metadata.trigger_type",)
        pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
            hash_fields=custom
        ))
        result = pipe.process_adapted_record(_adapted_record())
        assert result.audit_record.hashed_fields == list(custom)

    def test_empty_hash_fields_disables_hashing_entirely(self):
        """Empty hash_fields must produce zero hashing_actions (fail-open)."""
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(hash_fields=()))
        result = pipe.process_adapted_record(_adapted_record())
        assert result.audit_record.hashed_fields == []
        assert result.audit_record.hashing_actions == []
        # Original value must be intact when hashing is disabled
        assert result.context_metadata["trigger_type"] == "http"

    def test_hashed_field_value_is_not_original(self):
        """After hashing, the field value must differ from the original."""
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
            hash_fields=("context_metadata.trigger_type",)
        ))
        result = pipe.process_adapted_record(_adapted_record())
        assert result.context_metadata["trigger_type"] != "http"

    def test_blake2b_algorithm_flows_to_hashing_actions(self):
        """hash_algorithm config must flow through to each HashingAction.algorithm."""
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
            hash_algorithm="blake2b"
        ))
        result = pipe.process_adapted_record(_adapted_record())
        assert result.audit_record.hashing_actions, "Expected non-empty hashing_actions"
        for action in result.audit_record.hashing_actions:
            assert action["algorithm"] == "blake2b"

    def test_sha256_algorithm_flows_to_hashing_actions(self):
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
            hash_algorithm="sha256"
        ))
        result = pipe.process_adapted_record(_adapted_record())
        for action in result.audit_record.hashing_actions:
            assert action["algorithm"] == "sha256"

    def test_hashing_actions_are_dicts_with_required_keys(self):
        """hashing_actions are projected from HashingAction.to_dict()."""
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        for action in result.audit_record.hashing_actions:
            assert "field_path" in action
            assert "algorithm" in action

    def test_hashing_phase_listed_in_phases_completed(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert "hashing" in result.audit_record.phases_completed


# ---------------------------------------------------------------------------
# 7. Preservation gateway delegation
# ---------------------------------------------------------------------------

class TestPreservationGatewayDelegation:
    """_measure_preservation must call assess_preservation(original, processed)."""

    def test_assess_preservation_is_called_exactly_once(self):
        import layer1.pipeline as pipeline_mod
        from layer1.pipeline import Layer1CanonicalPipeline
        pipe = Layer1CanonicalPipeline()
        with mock.patch.object(
            pipeline_mod, "assess_preservation", wraps=pipeline_mod.assess_preservation
        ) as spy:
            pipe.process_adapted_record(_adapted_record())
        assert spy.call_count == 1

    def test_preservation_score_matches_real_gateway_call(self):
        """anomaly_signal_preservation must equal assess_preservation's score, not a stub."""
        from layer1.pipeline import Layer1CanonicalPipeline
        from layer1.preservation import assess_preservation
        rec = _adapted_record()
        pipe = Layer1CanonicalPipeline()
        result = pipe.process_adapted_record(copy.deepcopy(rec))
        # Reproduce the gateway call: feed it the original and the processed critical fields
        expected = assess_preservation(
            copy.deepcopy(rec),
            {
                **rec,
                "telemetry_data": result.telemetry_data,
                "context_metadata": result.context_metadata,
                "provenance_chain": result.provenance_chain,
            },
        )
        assert abs(
            result.quality_report.anomaly_signal_preservation - expected.preservation_score
        ) < 1e-6

    def test_clean_record_has_zero_preservation_at_risk(self):
        """A clean benign record should not mark any critical field at risk."""
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert result.audit_record.preservation_at_risk == []

    def test_preservation_phase_listed_in_phases_completed(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert "preservation" in result.audit_record.phases_completed


# ---------------------------------------------------------------------------
# 8. Layer1QualityReport — sourced from real gateway outputs
# ---------------------------------------------------------------------------

class TestLayer1QualityReport:
    """Quality report fields must come from gateway outputs, not stub constants."""

    def test_completeness_score_is_1_for_fully_populated_record(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert result.quality_report.completeness_score == 1.0

    def test_completeness_score_less_than_1_when_fields_missing(self):
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        rec = _adapted_record()
        del rec["schema_version"]  # remove one required field
        pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
            fail_on_validation_error=False
        ))
        result = pipe.process_adapted_record(rec)
        assert result.quality_report.completeness_score < 1.0

    def test_pii_fields_redacted_is_zero_for_clean_record(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert result.quality_report.pii_fields_redacted == 0

    def test_pii_fields_redacted_counts_real_redaction_actions(self):
        """pii_fields_redacted must equal len(RedactionResult.actions_taken)."""
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        rec["context_metadata"]["email1"] = "a@example.com"
        rec["context_metadata"]["email2"] = "b@example.com"
        result = Layer1CanonicalPipeline().process_adapted_record(rec)
        # Each email should be a separate redaction action
        assert result.quality_report.pii_fields_redacted == len(
            result.audit_record.privacy_actions
        )

    def test_anomaly_signal_preservation_is_float_in_0_to_1(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        score = result.quality_report.anomaly_signal_preservation
        assert 0.0 <= score <= 1.0

    def test_issues_is_empty_for_clean_record_with_high_preservation(self):
        """Clean record with all required fields and no PII should produce no issues."""
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert result.quality_report.issues == []


# ---------------------------------------------------------------------------
# 9. Layer1AuditRecord — all phases and no stubs
# ---------------------------------------------------------------------------

class TestLayer1AuditRecord:
    """Audit record must name every gateway stage and contain no stub values."""

    def test_all_seven_phases_listed(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        expected = {
            "validation", "sanitisation", "privacy",
            "hashing", "preservation", "quality", "audit",
        }
        assert expected.issubset(set(result.audit_record.phases_completed))

    def test_processing_time_ms_is_positive(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert result.audit_record.processing_time_ms > 0.0

    def test_audit_record_to_dict_round_trips(self):
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        d = result.to_dict()
        ar = d["audit_record"]
        assert "phases_completed" in ar
        assert "redacted_fields" in ar
        assert "hashed_fields" in ar
        assert "sanitiser_flags" in ar
        assert "privacy_actions" in ar
        assert "hashing_actions" in ar
        assert "preservation_at_risk" in ar
        assert "preservation_recommendations" in ar
        assert "warnings" in ar
        assert "validation_errors" in ar
        assert "processing_time_ms" in ar


# ---------------------------------------------------------------------------
# 10. Runtime config injection (ADR-002)
# ---------------------------------------------------------------------------

class TestRuntimeConfigInjection:
    """SCAFADCanonicalRuntime is the one place that owns config construction."""

    def test_runtime_accepts_layer1_config_kwarg(self):
        from runtime.runtime import SCAFADCanonicalRuntime
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        cfg = Layer1CanonicalPipelineConfig(privacy_regime="CCPA")
        rt = SCAFADCanonicalRuntime(layer1_config=cfg)
        assert rt.layer1_config is cfg

    def test_runtime_forwards_config_to_pipeline(self):
        """The pipeline constructed by the runtime must carry the same config object."""
        from runtime.runtime import SCAFADCanonicalRuntime
        from layer1.pipeline import Layer1CanonicalPipelineConfig
        cfg = Layer1CanonicalPipelineConfig(
            privacy_regime="HIPAA",
            hash_algorithm="blake2b",
        )
        rt = SCAFADCanonicalRuntime(layer1_config=cfg)
        # The pipeline's config must be the exact same instance
        assert rt.layer1_pipeline.config is cfg

    def test_runtime_default_uses_gdpr_regime(self):
        from runtime.runtime import SCAFADCanonicalRuntime
        rt = SCAFADCanonicalRuntime()
        assert rt.layer1_pipeline.config.privacy_regime == "GDPR"

    def test_runtime_default_uses_sha256_algorithm(self):
        from runtime.runtime import SCAFADCanonicalRuntime
        rt = SCAFADCanonicalRuntime()
        assert rt.layer1_pipeline.config.hash_algorithm == "sha256"

    def test_explicit_pipeline_wins_over_config(self):
        """If caller provides layer1_pipeline= it must not be overwritten by config."""
        from runtime.runtime import SCAFADCanonicalRuntime
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        explicit_cfg = Layer1CanonicalPipelineConfig(privacy_regime="CCPA")
        explicit_pipe = Layer1CanonicalPipeline(config=explicit_cfg)
        rt = SCAFADCanonicalRuntime(
            layer1_pipeline=explicit_pipe,
            layer1_config=Layer1CanonicalPipelineConfig(privacy_regime="HIPAA"),
        )
        # The explicit pipeline (CCPA) must win over the config kwarg (HIPAA)
        assert rt.layer1_pipeline.config.privacy_regime == "CCPA"


# ---------------------------------------------------------------------------
# 11. Layer1Config on Layer0Config
# ---------------------------------------------------------------------------

class TestLayer1ConfigOnLayer0Config:
    """Layer0Config.layer1 exposes the deployment-facing surface (ADR-002)."""

    def test_layer0_config_has_layer1_attribute(self):
        from layer0.app_config import Layer0Config
        cfg = Layer0Config()
        assert hasattr(cfg, "layer1")

    def test_layer1_config_default_regime_is_gdpr(self):
        from layer0.app_config import Layer0Config
        cfg = Layer0Config()
        assert cfg.layer1.privacy_regime == "GDPR"

    def test_layer1_config_validate_returns_empty_for_defaults(self):
        from layer0.app_config import Layer1Config
        issues = Layer1Config().validate()
        assert issues == [], f"Unexpected issues on default config: {issues}"

    def test_layer1_config_validate_catches_bad_regime(self):
        from layer0.app_config import Layer1Config
        issues = Layer1Config(privacy_regime="INVALID").validate()
        assert issues, "Validator should report invalid regime"

    def test_layer1_config_validate_catches_bad_algorithm(self):
        from layer0.app_config import Layer1Config
        issues = Layer1Config(hash_algorithm="md5").validate()
        assert issues, "Validator should report invalid hash algorithm"

    def test_layer1_config_validate_catches_out_of_range_completeness(self):
        from layer0.app_config import Layer1Config
        issues = Layer1Config(completeness_target=2.5).validate()
        assert issues, "Validator should report completeness_target > 1.0"

    def test_layer1_config_to_dict_returns_dict(self):
        from layer0.app_config import Layer1Config
        d = Layer1Config().to_dict()
        assert isinstance(d, dict)
        assert "privacy_regime" in d


# ---------------------------------------------------------------------------
# 12. End-to-end — no stub placeholders
# ---------------------------------------------------------------------------

class TestEndToEndNoStubs:
    """The pipeline's outputs must trace back to real gateway calls, not stubs."""

    def test_hashing_actions_algorithm_key_exists_per_action(self):
        """Hashing actions must carry the algorithm field — stub would omit this."""
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        # Non-empty hash_fields config → at least one action expected
        assert result.audit_record.hashing_actions, (
            "Expected hashing_actions from default hash_fields config"
        )
        for action in result.audit_record.hashing_actions:
            assert "algorithm" in action

    def test_complete_pipeline_produces_valid_processed_record(self):
        """Full pipeline run returns a Layer1ProcessedRecord with all key attributes."""
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1ProcessedRecord
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        assert isinstance(result, Layer1ProcessedRecord)
        assert result.record_id == "p3-test-record-001"
        assert result.trace_id  # non-empty hash
        assert result.schema_version == "v2.1"
        assert result.trust_context["source_layer"] == "layer_1"

    def test_to_dict_quality_report_fields_are_real_values(self):
        """quality_report in to_dict() must contain real scored values."""
        from layer1.pipeline import Layer1CanonicalPipeline
        result = Layer1CanonicalPipeline().process_adapted_record(_adapted_record())
        d = result.to_dict()
        qr = d["quality_report"]
        assert 0.0 <= qr["completeness_score"] <= 1.0
        assert 0.0 <= qr["anomaly_signal_preservation"] <= 1.0
        assert isinstance(qr["pii_fields_redacted"], int)
        assert isinstance(qr["issues"], list)

    def test_pipeline_is_idempotent_on_same_record(self):
        """Processing the same record twice must produce the same trace_id."""
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        pipe = Layer1CanonicalPipeline()
        r1 = pipe.process_adapted_record(copy.deepcopy(rec))
        r2 = pipe.process_adapted_record(copy.deepcopy(rec))
        assert r1.trace_id == r2.trace_id

    def test_pii_fields_redacted_equals_privacy_actions_count(self):
        """pii_fields_redacted is len(privacy_actions) — not a fixed stub integer."""
        from layer1.pipeline import Layer1CanonicalPipeline
        rec = _adapted_record()
        rec["context_metadata"]["email"] = "check@example.com"
        rec["context_metadata"]["phone"] = "+1-555-867-5309"
        result = Layer1CanonicalPipeline().process_adapted_record(rec)
        assert result.quality_report.pii_fields_redacted == len(
            result.audit_record.privacy_actions
        )

    def test_preservation_below_target_issue_raised_when_score_is_low(self):
        """When preservation score < completeness_target, issue 'preservation_below_target'
        must appear. We force this by setting completeness_target=1.0 + patching the gateway."""
        from layer1.pipeline import Layer1CanonicalPipeline, Layer1CanonicalPipelineConfig
        from layer1.preservation import PreservationAssessment
        pipe = Layer1CanonicalPipeline(config=Layer1CanonicalPipelineConfig(
            completeness_target=1.0  # require perfect preservation
        ))
        # Simulate a gateway that reports imperfect preservation
        low_score = PreservationAssessment(
            preservation_score=0.9,
            at_risk_fields=["telemetry_data.l0_cpu_utilization"],
            recommendations=["cpu_signal_degraded"],
        )
        with mock.patch.object(pipe, "_measure_preservation", return_value=low_score):
            result = pipe.process_adapted_record(_adapted_record())
        assert "preservation_below_target" in result.quality_report.issues
        assert "cpu_signal_degraded" in result.quality_report.issues
