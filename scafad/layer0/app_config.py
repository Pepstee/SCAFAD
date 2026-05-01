"""
SCAFAD Layer 0: Configuration Management Module
==============================================

Centralized configuration management for all Layer 0 components.
Handles environment variables, validation, feature flags, and deployment settings.

Academic Reference: Configuration-driven system design enables reproducible
research and systematic evaluation across different experimental conditions.
"""

import os
import sys
import json
import logging
import warnings
import time
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

# Version and build information
SCAFAD_VERSION = {
    "version": "v4.2-modular",
    "stage": "research",
    "build_date": "2025-01-01",
    "features": [
        "modular_architecture",
        "advanced_graph_analysis", 
        "adversarial_gan_simulation",
        "economic_abuse_detection",
        "silent_failure_analysis",
        "formal_verification",
        "multi_channel_telemetry",
        "provenance_tracking"
    ],
    "academic_references": [
        "ALASTOR (Datta et al.) - Provenance tracking",
        "LogGD/GLAD (Xie et al., Li et al.) - Graph construction", 
        "Ares/PatchGuard (Ahmed et al., Nafez et al.) - Adversarial simulation",
        "FaaSRCA (Huang et al.) - Lifecycle tracking",
        "Warmonger/DoWNet (Xiong et al., Kelly et al.) - Economic abuse detection"
    ]
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VerbosityLevel(Enum):
    """Telemetry verbosity levels"""
    SILENT = "SILENT"
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    DEBUG = "DEBUG"


class AdversarialMode(Enum):
    """Adversarial simulation modes"""
    DISABLED = "DISABLED"
    TEST = "TEST"
    PRODUCTION = "PRODUCTION"
    RESEARCH = "RESEARCH"


class DeploymentEnvironment(Enum):
    """Deployment environment types"""
    DEVELOPMENT = "DEVELOPMENT"
    TESTING = "TESTING"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"
    RESEARCH = "RESEARCH"


@dataclass
class TelemetryConfig:
    """Configuration for telemetry generation and emission"""
    
    # Core telemetry settings
    temporal_window_seconds: int = 300
    timeout_threshold_seconds: float = 0.6
    max_memory_spike_mb: int = 50
    
    # Multi-channel settings
    enable_primary_channel: bool = True
    enable_cloudwatch_fallback: bool = True
    enable_side_trace: bool = True
    enable_metrics_channel: bool = True
    
    # Emission controls
    emission_batch_size: int = 10
    emission_timeout_ms: int = 5000
    retry_attempts: int = 3
    retry_backoff_ms: int = 1000
    
    # Quality controls
    require_completeness_verification: bool = True
    min_completeness_score: float = 0.85
    enable_schema_validation: bool = True
    
    def validate(self) -> List[str]:
        """Validate telemetry configuration"""
        issues = []
        
        if self.temporal_window_seconds < 60:
            issues.append("Temporal window too small (minimum 60 seconds)")
        
        if self.timeout_threshold_seconds > 900:
            issues.append("Timeout threshold too large (maximum 15 minutes)")
            
        if self.max_memory_spike_mb < 1:
            issues.append("Maximum memory spike too small (minimum 1MB)")
            
        if not (0.0 <= self.min_completeness_score <= 1.0):
            issues.append("Completeness score must be between 0.0 and 1.0")
            
        if self.emission_batch_size < 1:
            issues.append("Emission batch size must be at least 1")
            
        return issues


@dataclass
class GraphConfig:
    """Configuration for invocation graph analysis"""
    
    # Graph construction
    enable_graph_analysis: bool = True
    max_nodes: int = 10000
    max_edges: int = 50000
    node_ttl_seconds: int = 3600
    
    # Edge creation thresholds
    temporal_correlation_threshold: float = 0.2
    semantic_similarity_threshold: float = 0.3
    behavioral_correlation_threshold: float = 0.25
    causal_correlation_threshold: float = 0.15
    
    # Centrality analysis
    enable_centrality_metrics: bool = True
    centrality_update_interval: int = 300
    max_centrality_iterations: int = 100
    
    # Flow detection
    enable_flow_detection: bool = True
    flow_time_window_seconds: int = 600
    min_flow_score: float = 0.5
    
    # Clustering
    enable_anomaly_clustering: bool = True
    clustering_algorithm: str = "DBSCAN"
    clustering_eps: float = 0.5
    clustering_min_samples: int = 3
    
    def validate(self) -> List[str]:
        """Validate graph configuration"""
        issues = []
        
        if self.max_nodes < 100:
            issues.append("Maximum nodes too small (minimum 100)")
            
        if self.max_edges < self.max_nodes:
            issues.append("Maximum edges should be at least equal to maximum nodes")
            
        if not (0.0 <= self.temporal_correlation_threshold <= 1.0):
            issues.append("Temporal correlation threshold must be between 0.0 and 1.0")
            
        if self.clustering_algorithm not in ["DBSCAN", "KMeans", "AgglomerativeClustering"]:
            issues.append(f"Unsupported clustering algorithm: {self.clustering_algorithm}")
            
        return issues


@dataclass
class SchemaConfig:
    """Configuration for schema evolution and validation"""

    enable_schema_evolution: bool = True
    default_version: str = "v1"
    max_version_history: int = 50
    compatibility_policy: str = "BACKWARD"  # STRICT, BACKWARD, FORWARD, FLEXIBLE
    validation_strictness: str = "STRICT"  # RELAXED, BALANCED, STRICT
    allow_auto_migration: bool = True
    validation_timeout_seconds: int = 5
    schema_registry_path: Optional[Path] = None
    custom_validators: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Validate schema configuration"""
        issues: List[str] = []

        if self.max_version_history <= 0:
            issues.append("Maximum version history must be positive")

        if self.compatibility_policy not in {"STRICT", "BACKWARD", "FORWARD", "FLEXIBLE"}:
            issues.append(f"Invalid compatibility policy: {self.compatibility_policy}")

        if self.validation_strictness not in {"RELAXED", "BALANCED", "STRICT"}:
            issues.append(f"Invalid validation strictness: {self.validation_strictness}")

        if self.validation_timeout_seconds <= 0:
            issues.append("Validation timeout must be positive")

        return issues

    def to_dict(self) -> Dict[str, Any]:
        """Dictionary representation used by schema management modules"""
        return {
            "enable_schema_evolution": self.enable_schema_evolution,
            "default_version": self.default_version,
            "max_version_history": self.max_version_history,
            "compatibility_policy": self.compatibility_policy,
            "validation_strictness": self.validation_strictness,
            "allow_auto_migration": self.allow_auto_migration,
            "validation_timeout_seconds": self.validation_timeout_seconds,
            "schema_registry_path": str(self.schema_registry_path) if self.schema_registry_path else None,
            "custom_validators": list(self.custom_validators.keys()),
        }


@dataclass
class Layer1Config:
    """Layer 1 Behavioural Intake Zone configuration (P3.1 / ADR-002).

    This is the deployment-facing configuration surface for the canonical
    Layer 1 pipeline.  The runtime converts an instance of this dataclass
    into a :class:`Layer1CanonicalPipelineConfig` before handing it to
    :class:`Layer1CanonicalPipeline`.

    Defaults mirror :class:`Layer1CanonicalPipelineConfig` so an unset
    ``Layer1Config`` produces the same behaviour as the zero-arg
    pipeline constructor.
    """

    # Privacy regime — one of {"GDPR", "CCPA", "HIPAA"}.
    privacy_regime: str = "GDPR"

    # Dotted field paths to hash via DeferredHashingManager.  Keep the
    # tuple immutable at config-surface level; the pipeline converts to a
    # list before handing it to the gateway.
    hash_fields: tuple = (
        "provenance_chain.concurrency_id",
        "context_metadata.trigger_type",
    )
    hash_algorithm: str = "sha256"  # "sha256" (HMAC-SHA256) or "blake2b"
    salt: Optional[str] = None
    salt_env_var: str = "SCAFAD_HASH_SALT"

    # Sanitiser chain identifiers.  Present for audit/toggle parity with the
    # canonical pipeline config; the SanitisationProcessor runs the full
    # chain today.
    sanitisers: tuple = ("path", "url", "html", "sql", "command", "unicode")

    # Pipeline behaviour toggles.
    fail_on_validation_error: bool = True
    preservation_epsilon: float = 1e-9
    completeness_target: float = 0.9995

    def validate(self) -> List[str]:
        """Return a list of configuration issues (empty on a clean config)."""
        issues: List[str] = []
        regime = str(self.privacy_regime or "").strip().upper()
        if regime not in {"GDPR", "CCPA", "HIPAA"}:
            issues.append(f"Invalid privacy regime: {self.privacy_regime!r}")
        if self.hash_algorithm not in {"sha256", "blake2b"}:
            issues.append(f"Invalid hash algorithm: {self.hash_algorithm!r}")
        if not (0.0 <= self.completeness_target <= 1.0):
            issues.append("completeness_target must be in [0.0, 1.0]")
        if self.preservation_epsilon < 0:
            issues.append("preservation_epsilon must be non-negative")
        if not isinstance(self.hash_fields, (tuple, list)):
            issues.append("hash_fields must be a tuple or list of dotted paths")
        if not isinstance(self.sanitisers, (tuple, list)):
            issues.append("sanitisers must be a tuple or list of identifiers")
        return issues

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


@dataclass
class AdversarialConfig:
    """Configuration for adversarial simulation and testing"""
    
    # Core adversarial settings
    adversarial_mode: AdversarialMode = AdversarialMode.DISABLED
    enable_gan_generation: bool = True
    enable_statistical_generation: bool = True
    enable_evasion_techniques: bool = True
    
    # GAN settings
    gan_latent_dim: int = 100
    gan_feature_dim: int = 20
    gan_learning_rate: float = 0.0002
    gan_batch_size: int = 32
    gan_epochs: int = 100
    
    # Evasion settings
    max_evasion_budget: float = 0.1
    evasion_strategies: List[str] = field(default_factory=lambda: [
        "noise_injection",
        "gradient_masking", 
        "input_transformation",
        "adaptive_perturbation"
    ])
    
    # Attack patterns
    enable_dos_patterns: bool = True
    enable_mining_patterns: bool = True
    enable_exfiltration_patterns: bool = True
    enable_billing_patterns: bool = True
    
    # Poisoning attacks
    enable_poisoning_attacks: bool = False  # Disabled by default for safety
    max_poisoning_rate: float = 0.05
    
    def validate(self) -> List[str]:
        """Validate adversarial configuration"""
        issues = []
        
        if self.gan_latent_dim < 10:
            issues.append("GAN latent dimension too small (minimum 10)")
            
        if self.gan_feature_dim < 5:
            issues.append("GAN feature dimension too small (minimum 5)")
            
        if not (0.0001 <= self.gan_learning_rate <= 0.01):
            issues.append("GAN learning rate should be between 0.0001 and 0.01")
            
        if not (0.0 <= self.max_evasion_budget <= 1.0):
            issues.append("Evasion budget must be between 0.0 and 1.0")
            
        if self.enable_poisoning_attacks and self.max_poisoning_rate > 0.1:
            issues.append("Poisoning rate too high (maximum 0.1 for safety)")
            
        return issues


@dataclass
class EconomicConfig:
    """Configuration for economic abuse detection"""
    
    # Detection thresholds
    enable_economic_monitoring: bool = True
    hourly_cost_limit_usd: float = 100.0
    daily_cost_limit_usd: float = 1000.0
    burst_multiplier_threshold: float = 5.0
    
    # DoW detection
    enable_dow_detection: bool = True
    dow_invocation_rate_threshold: float = 10.0  # per second
    dow_cost_anomaly_threshold: float = 5.0
    dow_duration_threshold: float = 30.0  # seconds
    
    # Mining detection
    enable_mining_detection: bool = True
    mining_duration_consistency_threshold: float = 0.1  # coefficient of variation
    mining_cpu_threshold: float = 80.0
    mining_periodicity_threshold: float = 0.7
    
    # Billing abuse
    enable_billing_abuse_detection: bool = True
    billing_variance_threshold: float = 3.0
    billing_trend_window: int = 3600  # seconds
    
    def validate(self) -> List[str]:
        """Validate economic configuration"""
        issues = []
        
        if self.hourly_cost_limit_usd <= 0:
            issues.append("Hourly cost limit must be positive")
            
        if self.daily_cost_limit_usd <= self.hourly_cost_limit_usd:
            issues.append("Daily cost limit should be greater than hourly limit")
            
        if self.dow_invocation_rate_threshold <= 0:
            issues.append("DoW invocation rate threshold must be positive")
            
        if not (0.0 <= self.mining_periodicity_threshold <= 1.0):
            issues.append("Mining periodicity threshold must be between 0.0 and 1.0")
            
        return issues


@dataclass
class SilentFailureConfig:
    """Configuration for silent failure detection"""
    
    # Core detection settings
    enable_silent_failure_detection: bool = True
    detection_confidence_threshold: float = 0.5
    
    # Output validation
    enable_output_validation: bool = True
    enable_schema_checking: bool = True
    enable_type_validation: bool = True
    
    # Invariant checking
    enable_invariant_checking: bool = True
    invariant_violation_threshold: float = 0.7
    
    # Semantic analysis
    enable_semantic_analysis: bool = True
    semantic_consistency_threshold: float = 0.6
    
    # Behavioral analysis
    enable_behavioral_analysis: bool = True
    behavioral_anomaly_threshold: float = 0.6
    
    # Data corruption detection
    enable_corruption_detection: bool = True
    corruption_indicator_threshold: float = 0.7
    
    def validate(self) -> List[str]:
        """Validate silent failure configuration"""
        issues = []
        
        if not (0.0 <= self.detection_confidence_threshold <= 1.0):
            issues.append("Detection confidence threshold must be between 0.0 and 1.0")
            
        if not (0.0 <= self.invariant_violation_threshold <= 1.0):
            issues.append("Invariant violation threshold must be between 0.0 and 1.0")
            
        return issues


@dataclass
class FormalVerificationConfig:
    """Configuration for formal verification"""
    
    # Verification settings
    enable_formal_verification: bool = True
    verification_timeout_seconds: int = 30
    
    # Completeness verification
    temporal_completeness_threshold: float = 0.95
    spatial_completeness_threshold: float = 0.90
    semantic_completeness_threshold: float = 0.85
    
    # LTL properties
    enable_ltl_verification: bool = True
    ltl_formula_timeout_seconds: int = 10
    max_ltl_model_size: int = 10000
    
    # Proof generation
    enable_proof_generation: bool = True
    proof_detail_level: str = "SUMMARY"  # MINIMAL, SUMMARY, DETAILED, FULL
    
    def validate(self) -> List[str]:
        """Validate formal verification configuration"""
        issues = []
        
        if self.verification_timeout_seconds <= 0:
            issues.append("Verification timeout must be positive")
            
        if not (0.0 <= self.temporal_completeness_threshold <= 1.0):
            issues.append("Temporal completeness threshold must be between 0.0 and 1.0")
            
        if self.proof_detail_level not in ["MINIMAL", "SUMMARY", "DETAILED", "FULL"]:
            issues.append(f"Invalid proof detail level: {self.proof_detail_level}")
            
        return issues


@dataclass
class ProvenanceConfig:
    """Configuration for provenance tracking"""
    
    # Core provenance settings
    enable_provenance_tracking: bool = True
    max_chain_length: int = 100
    chain_ttl_seconds: int = 86400  # 24 hours
    
    # I/O tracking
    enable_io_tracking: bool = True
    track_input_hashes: bool = True
    track_output_hashes: bool = True
    max_io_records: int = 10000
    
    # State snapshots
    enable_state_snapshots: bool = True
    snapshot_interval_seconds: int = 300
    max_snapshots: int = 100
    
    # Causal analysis
    enable_causal_analysis: bool = True
    causal_window_seconds: int = 1800  # 30 minutes
    min_causal_confidence: float = 0.6
    
    def validate(self) -> List[str]:
        """Validate provenance configuration"""
        issues = []
        
        if self.max_chain_length <= 0:
            issues.append("Maximum chain length must be positive")
            
        if self.chain_ttl_seconds <= 0:
            issues.append("Chain TTL must be positive")
            
        if not (0.0 <= self.min_causal_confidence <= 1.0):
            issues.append("Causal confidence must be between 0.0 and 1.0")
            
        return issues


@dataclass
class PerformanceConfig:
    """Configuration for performance optimization"""
    
    # Memory management
    max_memory_usage_mb: int = 256
    gc_threshold: int = 1000
    enable_memory_monitoring: bool = True
    
    # Concurrency
    max_concurrent_operations: int = 10
    async_timeout_seconds: int = 30
    enable_async_processing: bool = True
    
    # Caching
    enable_caching: bool = True
    cache_ttl_seconds: int = 300
    max_cache_size: int = 1000
    
    # Metrics collection
    enable_performance_metrics: bool = True
    metrics_collection_interval: int = 60
    metrics_retention_hours: int = 24
    
    def validate(self) -> List[str]:
        """Validate performance configuration"""
        issues = []
        
        if self.max_memory_usage_mb < 64:
            issues.append("Maximum memory usage too small (minimum 64MB)")
            
        if self.max_concurrent_operations <= 0:
            issues.append("Maximum concurrent operations must be positive")
            
        if self.async_timeout_seconds <= 0:
            issues.append("Async timeout must be positive")
            
        return issues


@dataclass
class Layer0Config:
    """
    Master configuration class for SCAFAD Layer 0
    
    Aggregates all component configurations and provides validation,
    environment loading, and deployment management.
    """
    
    # Core settings
    version: Dict = field(default_factory=lambda: SCAFAD_VERSION.copy())
    deployment_environment: DeploymentEnvironment = DeploymentEnvironment.DEVELOPMENT
    verbosity_level: VerbosityLevel = VerbosityLevel.NORMAL
    
    # Component configurations
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)
    adversarial: AdversarialConfig = field(default_factory=AdversarialConfig)
    economic: EconomicConfig = field(default_factory=EconomicConfig)
    silent_failure: SilentFailureConfig = field(default_factory=SilentFailureConfig)
    formal_verification: FormalVerificationConfig = field(default_factory=FormalVerificationConfig)
    provenance: ProvenanceConfig = field(default_factory=ProvenanceConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    schema: SchemaConfig = field(default_factory=SchemaConfig)
    # P3.1 / ADR-002 — Layer 1 canonical pipeline configuration surface.
    layer1: Layer1Config = field(default_factory=Layer1Config)
    algorithm_weights: Dict[str, float] = field(default_factory=lambda: {
        'statistical_outlier': 0.15,
        'isolation_forest': 0.12,
        'temporal_deviation': 0.10,
        'resource_spike': 0.08,
        'execution_pattern': 0.08,
        'network_anomaly': 0.07,
        'memory_leak': 0.06,
        'cpu_burst': 0.06,
        'io_intensive': 0.05,
        'cold_start': 0.05,
        'timeout_pattern': 0.04,
        'frequency_anomaly': 0.04,
        'duration_outlier': 0.03,
        'correlation_break': 0.03,
        'seasonal_deviation': 0.02,
        'trend_change': 0.02
    })
    trust_weights: Dict[str, float] = field(default_factory=lambda: {
        'high_confidence': 1.0,
        'medium_confidence': 0.7,
        'low_confidence': 0.4,
        'untrusted': 0.1
    })
    
    # Feature flags (for easy enable/disable of entire subsystems)
    enable_graph_analysis: bool = True
    enable_adversarial_simulation: bool = True
    enable_economic_monitoring: bool = True
    enable_silent_failure_detection: bool = True
    enable_formal_verification: bool = True
    enable_provenance_tracking: bool = True
    
    # Deployment-specific settings
    aws_region: str = "us-east-1"
    log_level: str = "INFO"
    enable_debug_mode: bool = False
    enable_test_mode: bool = False
    
    def __post_init__(self):
        """Post-initialization configuration loading"""
        self._load_from_environment()
        self._apply_deployment_overrides()
        self._validate_configuration()
    
    def _load_from_environment(self):
        """Load configuration from environment variables"""
        
        # Core settings
        if "SCAFAD_ENVIRONMENT" in os.environ:
            try:
                self.deployment_environment = DeploymentEnvironment(
                    os.environ["SCAFAD_ENVIRONMENT"].upper()
                )
            except ValueError:
                logger.warning(f"Invalid SCAFAD_ENVIRONMENT: {os.environ['SCAFAD_ENVIRONMENT']}")
        
        if "SCAFAD_VERBOSITY" in os.environ:
            try:
                self.verbosity_level = VerbosityLevel(
                    os.environ["SCAFAD_VERBOSITY"].upper()
                )
            except ValueError:
                logger.warning(f"Invalid SCAFAD_VERBOSITY: {os.environ['SCAFAD_VERBOSITY']}")
        
        if "SCAFAD_DEBUG" in os.environ:
            self.enable_debug_mode = os.environ["SCAFAD_DEBUG"].lower() == "true"
        
        if "SCAFAD_TEST_MODE" in os.environ:
            self.enable_test_mode = os.environ["SCAFAD_TEST_MODE"].lower() == "true"
        
        # AWS settings
        if "AWS_REGION" in os.environ:
            self.aws_region = os.environ["AWS_REGION"]
        
        if "SCAFAD_LOG_LEVEL" in os.environ:
            self.log_level = os.environ["SCAFAD_LOG_LEVEL"].upper()
        
        # Feature flags
        self._load_feature_flags_from_env()
        
        # Component-specific settings
        self._load_component_configs_from_env()
    
    def _load_feature_flags_from_env(self):
        """Load feature flags from environment"""
        feature_flag_mapping = {
            "SCAFAD_ENABLE_GRAPH": "enable_graph_analysis",
            "SCAFAD_ENABLE_ADVERSARIAL": "enable_adversarial_simulation",
            "SCAFAD_ENABLE_ECONOMIC": "enable_economic_monitoring",
            "SCAFAD_ENABLE_SILENT_FAILURE": "enable_silent_failure_detection",
            "SCAFAD_ENABLE_FORMAL": "enable_formal_verification",
            "SCAFAD_ENABLE_PROVENANCE": "enable_provenance_tracking"
        }
        
        for env_var, attr_name in feature_flag_mapping.items():
            if env_var in os.environ:
                setattr(self, attr_name, os.environ[env_var].lower() == "true")
    
    def _load_component_configs_from_env(self):
        """Load component-specific configurations from environment"""
        
        # Telemetry configuration
        if "SCAFAD_TEMPORAL_WINDOW" in os.environ:
            self.telemetry.temporal_window_seconds = int(os.environ["SCAFAD_TEMPORAL_WINDOW"])
        
        if "SCAFAD_TIMEOUT_THRESHOLD" in os.environ:
            self.telemetry.timeout_threshold_seconds = float(os.environ["SCAFAD_TIMEOUT_THRESHOLD"])
        
        # Graph configuration  
        if "SCAFAD_MAX_GRAPH_NODES" in os.environ:
            self.graph.max_nodes = int(os.environ["SCAFAD_MAX_GRAPH_NODES"])
        
        if "SCAFAD_GRAPH_TTL" in os.environ:
            self.graph.node_ttl_seconds = int(os.environ["SCAFAD_GRAPH_TTL"])
        
        # Adversarial configuration
        if "SCAFAD_ADVERSARIAL_MODE" in os.environ:
            try:
                self.adversarial.adversarial_mode = AdversarialMode(
                    os.environ["SCAFAD_ADVERSARIAL_MODE"].upper()
                )
            except ValueError:
                logger.warning(f"Invalid SCAFAD_ADVERSARIAL_MODE: {os.environ['SCAFAD_ADVERSARIAL_MODE']}")
        
        # Economic configuration
        if "SCAFAD_HOURLY_COST_LIMIT" in os.environ:
            self.economic.hourly_cost_limit_usd = float(os.environ["SCAFAD_HOURLY_COST_LIMIT"])

        if "SCAFAD_DAILY_COST_LIMIT" in os.environ:
            self.economic.daily_cost_limit_usd = float(os.environ["SCAFAD_DAILY_COST_LIMIT"])

        # Performance configuration
        if "SCAFAD_MAX_MEMORY" in os.environ:
            self.performance.max_memory_usage_mb = int(os.environ["SCAFAD_MAX_MEMORY"])

        # Schema configuration
        if "SCAFAD_SCHEMA_COMPATIBILITY" in os.environ:
            self.schema.compatibility_policy = os.environ["SCAFAD_SCHEMA_COMPATIBILITY"].upper()

        if "SCAFAD_SCHEMA_STRICTNESS" in os.environ:
            self.schema.validation_strictness = os.environ["SCAFAD_SCHEMA_STRICTNESS"].upper()

        if "SCAFAD_SCHEMA_AUTO_MIGRATION" in os.environ:
            self.schema.allow_auto_migration = (
                os.environ["SCAFAD_SCHEMA_AUTO_MIGRATION"].lower() == "true"
            )

        if "SCAFAD_SCHEMA_TIMEOUT" in os.environ:
            self.schema.validation_timeout_seconds = int(os.environ["SCAFAD_SCHEMA_TIMEOUT"])

        # Layer 1 configuration (P3.1)
        if "SCAFAD_L1_PRIVACY_REGIME" in os.environ:
            self.layer1.privacy_regime = os.environ["SCAFAD_L1_PRIVACY_REGIME"].upper()

        if "SCAFAD_L1_HASH_ALGORITHM" in os.environ:
            self.layer1.hash_algorithm = os.environ["SCAFAD_L1_HASH_ALGORITHM"].lower()

        if "SCAFAD_L1_HASH_FIELDS" in os.environ:
            raw = os.environ["SCAFAD_L1_HASH_FIELDS"].strip()
            if raw:
                self.layer1.hash_fields = tuple(
                    f.strip() for f in raw.split(",") if f.strip()
                )

        if "SCAFAD_L1_FAIL_ON_VALIDATION_ERROR" in os.environ:
            self.layer1.fail_on_validation_error = (
                os.environ["SCAFAD_L1_FAIL_ON_VALIDATION_ERROR"].lower() == "true"
            )

    # ------------------------------------------------------------------
    # Legacy attribute shims
    # ------------------------------------------------------------------

    @property
    def clustering_eps(self) -> float:
        """Expose graph clustering epsilon on the top-level config.

        Several historical modules – including the fallback orchestrator and
        contract validation suites – reach directly into ``Layer0Config`` for
        clustering parameters.  The modern implementation scopes those values
        under ``graph``; this property keeps the legacy surface available while
        delegating to the canonical location.
        """

        return self.graph.clustering_eps

    @clustering_eps.setter
    def clustering_eps(self, value: float) -> None:
        self.graph.clustering_eps = value

    @property
    def clustering_min_samples(self) -> int:
        """Expose DBSCAN sample threshold on the top-level config."""

        return self.graph.clustering_min_samples

    @clustering_min_samples.setter
    def clustering_min_samples(self, value: int) -> None:
        self.graph.clustering_min_samples = value

    def __getattr__(self, name: str) -> Any:
        """Fallback to nested configurations for legacy attribute access."""

        for component_name in (
            "graph",
            "telemetry",
            "adversarial",
            "economic",
            "silent_failure",
            "formal_verification",
            "provenance",
            "performance",
            "schema",
            "layer1",
        ):
            component = object.__getattribute__(self, component_name)
            if hasattr(component, name):
                return getattr(component, name)

        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        """Propagate legacy assignments into component configurations."""

        descriptor = getattr(type(self), name, None)
        if isinstance(descriptor, property) and descriptor.fset is not None:
            descriptor.fset(self, value)
            return

        fields = getattr(type(self), "__dataclass_fields__", {})
        if name in fields:
            object.__setattr__(self, name, value)
            return

        for component_name in (
            "graph",
            "telemetry",
            "adversarial",
            "economic",
            "silent_failure",
            "formal_verification",
            "provenance",
            "performance",
            "schema",
            "layer1",
        ):
            try:
                component = object.__getattribute__(self, component_name)
            except AttributeError:
                continue

            if hasattr(component, name):
                setattr(component, name, value)
                return

        object.__setattr__(self, name, value)
    
    def _apply_deployment_overrides(self):
        """Apply deployment-specific configuration overrides"""
        
        if self.deployment_environment == DeploymentEnvironment.PRODUCTION:
            # Production overrides
            self.enable_debug_mode = False
            self.enable_test_mode = False
            self.verbosity_level = VerbosityLevel.LOW
            self.log_level = "WARNING"
            
            # Disable potentially expensive features
            self.formal_verification.enable_proof_generation = False
            self.performance.enable_performance_metrics = True
            
        elif self.deployment_environment == DeploymentEnvironment.RESEARCH:
            # Research overrides - enable all features for comprehensive evaluation
            self.enable_debug_mode = True
            self.verbosity_level = VerbosityLevel.HIGH
            self.log_level = "DEBUG"
            
            # Enable all research features
            self.adversarial.enable_poisoning_attacks = True
            self.formal_verification.enable_proof_generation = True
            self.formal_verification.proof_detail_level = "DETAILED"
            
        elif self.deployment_environment == DeploymentEnvironment.TESTING:
            # Testing overrides
            self.enable_test_mode = True
            self.verbosity_level = VerbosityLevel.HIGH
            
            # Reduce resource limits for testing
            self.graph.max_nodes = 1000
            self.performance.max_memory_usage_mb = 128
            
        elif self.deployment_environment == DeploymentEnvironment.DEVELOPMENT:
            # Development overrides
            self.enable_debug_mode = True
            self.verbosity_level = VerbosityLevel.DEBUG
            self.log_level = "DEBUG"
    
    def _validate_configuration(self):
        """Validate entire configuration and log issues"""
        all_issues = []
        
        # Validate each component configuration
        component_validators = [
            ("telemetry", self.telemetry.validate),
            ("graph", self.graph.validate),
            ("adversarial", self.adversarial.validate),
            ("economic", self.economic.validate),
            ("silent_failure", self.silent_failure.validate),
            ("formal_verification", self.formal_verification.validate),
            ("provenance", self.provenance.validate),
            ("performance", self.performance.validate),
            ("schema", self.schema.validate),
            ("layer1", self.layer1.validate),
        ]
        
        for component_name, validator in component_validators:
            issues = validator()
            if issues:
                all_issues.extend([f"{component_name}: {issue}" for issue in issues])
        
        # Log validation results
        if all_issues:
            logger.warning("Configuration validation issues found:")
            for issue in all_issues:
                logger.warning(f"  - {issue}")
            
            if self.deployment_environment == DeploymentEnvironment.PRODUCTION:
                raise ValueError(f"Configuration validation failed with {len(all_issues)} issues")
        else:
            logger.info("Configuration validation passed")
    
    def to_dict(self) -> Dict:
        """Convert configuration to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert configuration to JSON string"""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    def save_to_file(self, file_path: Union[str, Path]):
        """Save configuration to JSON file"""
        with open(file_path, 'w') as f:
            f.write(self.to_json())
        logger.info(f"Configuration saved to {file_path}")
    
    @classmethod
    def load_from_file(cls, file_path: Union[str, Path]) -> 'Layer0Config':
        """Load configuration from JSON file"""
        with open(file_path, 'r') as f:
            config_dict = json.load(f)
        
        # Convert nested dicts back to dataclass instances
        config = cls()
        config._update_from_dict(config_dict)
        
        logger.info(f"Configuration loaded from {file_path}")
        return config
    
    def _update_from_dict(self, config_dict: Dict):
        """Update configuration from dictionary (for loading from file)"""
        # This would implement deep update of nested dataclasses
        # Simplified implementation for core fields
        for key, value in config_dict.items():
            if hasattr(self, key) and not key.startswith('_'):
                setattr(self, key, value)
    
    def get_summary(self) -> Dict:
        """Get configuration summary for logging/monitoring"""
        return {
            "version": self.version["version"],
            "environment": self.deployment_environment.value,
            "verbosity": self.verbosity_level.value,
            "features_enabled": {
                "graph_analysis": self.enable_graph_analysis,
                "adversarial_simulation": self.enable_adversarial_simulation,
                "economic_monitoring": self.enable_economic_monitoring,
                "silent_failure_detection": self.enable_silent_failure_detection,
                "formal_verification": self.enable_formal_verification,
                "provenance_tracking": self.enable_provenance_tracking
            },
            "resource_limits": {
                "max_memory_mb": self.performance.max_memory_usage_mb,
                "max_graph_nodes": self.graph.max_nodes,
                "temporal_window_s": self.telemetry.temporal_window_seconds
            }
        }


@dataclass
class ScafadConfig(Layer0Config):
    """Backward-compatible alias for the primary Layer 0 configuration."""

    pass


# =============================================================================
# Environment Validation Functions
# =============================================================================

def validate_environment() -> Dict[str, bool]:
    """
    Validate deployment environment for Layer 0
    
    Returns:
        Dictionary of validation results
    """
    validation_results = {
        'python_version_ok': sys.version_info >= (3, 8),
        'required_modules_available': True,
        'memory_sufficient': True,
        'aws_credentials_available': False,
        'environment_variables_valid': True
    }
    
    # Check required modules
    required_modules = [
        'json', 'time', 'random', 'hashlib', 'uuid', 'asyncio',
        'numpy', 'networkx', 'dataclasses', 'typing', 'enum'
    ]
    
    try:
        for module in required_modules:
            __import__(module)
    except ImportError as e:
        validation_results['required_modules_available'] = False
        validation_results['missing_module'] = str(e)
    
    # Check memory availability (simplified)
    try:
        test_data = bytearray(50 * 1024 * 1024)  # 50MB test
        del test_data
    except MemoryError:
        validation_results['memory_sufficient'] = False
    
    # Check AWS credentials
    aws_env_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN']
    if any(var in os.environ for var in aws_env_vars):
        validation_results['aws_credentials_available'] = True
    
    # Validate environment variables
    try:
        config = Layer0Config()
        validation_results['environment_variables_valid'] = True
    except Exception as e:
        validation_results['environment_variables_valid'] = False
        validation_results['config_error'] = str(e)
    
    return validation_results


def get_deployment_info() -> Dict:
    """Get deployment information and requirements"""
    return {
        'scafad_version': SCAFAD_VERSION,
        'python_requirements': {
            'minimum_version': '3.8',
            'recommended_version': '3.9+',
            'required_modules': [
                'numpy>=1.21.0',
                'networkx>=2.6',
                'torch>=1.10.0',
                'scikit-learn>=1.0.0',
                'scipy>=1.7.0'
            ]
        },
        'aws_requirements': {
            'lambda_runtime': 'python3.8+',
            'minimum_memory': '128MB',
            'recommended_memory': '256MB',
            'timeout': '30s+',
            'permissions': [
                'logs:CreateLogGroup',
                'logs:CreateLogStream', 
                'logs:PutLogEvents',
                'kinesis:PutRecord',
                'cloudwatch:PutMetricData'
            ]
        },
        'environment_variables': {
            'required': [],
            'optional': [
                'SCAFAD_ENVIRONMENT',
                'SCAFAD_VERBOSITY',
                'SCAFAD_ADVERSARIAL_MODE',
                'SCAFAD_ENABLE_GRAPH',
                'AWS_REGION'
            ]
        }
    }


# =============================================================================
# Configuration Utilities
# =============================================================================

def create_development_config() -> Layer0Config:
    """Create configuration optimized for development"""
    config = Layer0Config()
    config.deployment_environment = DeploymentEnvironment.DEVELOPMENT
    config.verbosity_level = VerbosityLevel.DEBUG
    config.enable_debug_mode = True
    config.log_level = "DEBUG"
    
    # Reduce resource limits for development
    config.graph.max_nodes = 1000
    config.graph.max_edges = 5000
    config.performance.max_memory_usage_mb = 128
    config.telemetry.temporal_window_seconds = 180  # 3 minutes
    
    # Enable all features for testing
    config.enable_graph_analysis = True
    config.enable_adversarial_simulation = True
    config.enable_economic_monitoring = True
    config.enable_silent_failure_detection = True
    config.enable_formal_verification = True
    config.enable_provenance_tracking = True
    
    # Development-friendly settings
    config.adversarial.adversarial_mode = AdversarialMode.TEST
    config.formal_verification.verification_timeout_seconds = 10
    config.formal_verification.proof_detail_level = "SUMMARY"
    
    return config


def create_testing_config() -> Layer0Config:
    """Create configuration optimized for testing"""
    config = Layer0Config()
    config.deployment_environment = DeploymentEnvironment.TESTING
    config.verbosity_level = VerbosityLevel.HIGH
    config.enable_test_mode = True
    config.log_level = "INFO"
    
    # Testing-specific limits
    config.graph.max_nodes = 500
    config.graph.max_edges = 2000
    config.performance.max_memory_usage_mb = 64
    config.telemetry.temporal_window_seconds = 120  # 2 minutes
    
    # Enable comprehensive testing
    config.adversarial.adversarial_mode = AdversarialMode.TEST
    config.adversarial.enable_poisoning_attacks = True
    config.adversarial.max_poisoning_rate = 0.01  # Very low for safety
    
    # Faster timeouts for testing
    config.formal_verification.verification_timeout_seconds = 5
    config.performance.async_timeout_seconds = 10
    
    return config


def create_research_config() -> Layer0Config:
    """Create configuration optimized for academic research"""
    config = Layer0Config()
    config.deployment_environment = DeploymentEnvironment.RESEARCH
    config.verbosity_level = VerbosityLevel.HIGH
    config.enable_debug_mode = True
    config.log_level = "DEBUG"
    
    # Research-grade resource limits
    config.graph.max_nodes = 50000
    config.graph.max_edges = 200000
    config.performance.max_memory_usage_mb = 512
    config.telemetry.temporal_window_seconds = 600  # 10 minutes
    
    # Enable all research features
    config.enable_graph_analysis = True
    config.enable_adversarial_simulation = True
    config.enable_economic_monitoring = True
    config.enable_silent_failure_detection = True
    config.enable_formal_verification = True
    config.enable_provenance_tracking = True
    
    # Research-specific settings
    config.adversarial.adversarial_mode = AdversarialMode.RESEARCH
    config.adversarial.enable_poisoning_attacks = True
    config.adversarial.max_poisoning_rate = 0.05
    config.adversarial.gan_epochs = 200  # More training for research
    
    # Detailed verification for research
    config.formal_verification.enable_proof_generation = True
    config.formal_verification.proof_detail_level = "DETAILED"
    config.formal_verification.verification_timeout_seconds = 60
    
    # Comprehensive provenance for academic audit
    config.provenance.enable_causal_analysis = True
    config.provenance.max_chain_length = 1000
    config.provenance.enable_state_snapshots = True
    
    return config


def create_production_config() -> Layer0Config:
    """Create configuration optimized for production deployment"""
    config = Layer0Config()
    config.deployment_environment = DeploymentEnvironment.PRODUCTION
    config.verbosity_level = VerbosityLevel.LOW
    config.enable_debug_mode = False
    config.enable_test_mode = False
    config.log_level = "WARNING"
    
    # Production resource limits
    config.graph.max_nodes = 10000
    config.graph.max_edges = 50000
    config.performance.max_memory_usage_mb = 256
    config.telemetry.temporal_window_seconds = 300  # 5 minutes
    
    # Core features only for production
    config.enable_graph_analysis = True
    config.enable_adversarial_simulation = False  # Disabled for performance
    config.enable_economic_monitoring = True
    config.enable_silent_failure_detection = True
    config.enable_formal_verification = False  # Disabled for performance
    config.enable_provenance_tracking = True
    
    # Production safety settings
    config.adversarial.adversarial_mode = AdversarialMode.DISABLED
    config.adversarial.enable_poisoning_attacks = False
    
    # Optimized performance settings
    config.performance.enable_caching = True
    config.performance.max_concurrent_operations = 20
    config.performance.enable_performance_metrics = True
    
    # Minimal verification for performance
    config.formal_verification.enable_proof_generation = False
    config.formal_verification.verification_timeout_seconds = 5
    
    return config


# =============================================================================
# Configuration Factory
# =============================================================================

class ConfigurationFactory:
    """Factory for creating configuration instances"""
    
    _config_creators = {
        DeploymentEnvironment.DEVELOPMENT: create_development_config,
        DeploymentEnvironment.TESTING: create_testing_config,
        DeploymentEnvironment.RESEARCH: create_research_config,
        DeploymentEnvironment.PRODUCTION: create_production_config
    }
    
    @classmethod
    def create_config(cls, environment: Union[str, DeploymentEnvironment] = None) -> Layer0Config:
        """Create configuration for specified environment"""
        
        if environment is None:
            # Auto-detect from environment variable
            env_str = os.environ.get('SCAFAD_ENVIRONMENT', 'DEVELOPMENT')
            environment = DeploymentEnvironment(env_str.upper())
        elif isinstance(environment, str):
            environment = DeploymentEnvironment(environment.upper())
        
        creator_func = cls._config_creators.get(environment)
        if creator_func is None:
            logger.warning(f"No specific config creator for {environment}, using default")
            return Layer0Config()
        
        config = creator_func()
        logger.info(f"Created {environment.value} configuration")
        return config
    
    @classmethod
    def get_available_environments(cls) -> List[str]:
        """Get list of available environment configurations"""
        return [env.value for env in cls._config_creators.keys()]


# =============================================================================
# Configuration Validation & Health Checks
# =============================================================================

class ConfigurationValidator:
    """Comprehensive configuration validation"""
    
    def __init__(self, config: Layer0Config):
        self.config = config
        self.validation_results = {}
    
    def validate_all(self) -> Dict[str, Any]:
        """Run comprehensive validation"""
        
        self.validation_results = {
            'overall_valid': True,
            'component_validations': {},
            'environment_compatibility': {},
            'resource_requirements': {},
            'security_checks': {},
            'performance_warnings': []
        }
        
        # Component validations
        self._validate_components()
        
        # Environment compatibility
        self._check_environment_compatibility()
        
        # Resource requirements
        self._check_resource_requirements()
        
        # Security validations
        self._perform_security_checks()
        
        # Performance warnings
        self._check_performance_implications()
        
        # Update overall validity
        self.validation_results['overall_valid'] = self._calculate_overall_validity()
        
        return self.validation_results
    
    def _validate_components(self):
        """Validate individual components"""
        components = {
            'telemetry': self.config.telemetry,
            'graph': self.config.graph,
            'adversarial': self.config.adversarial,
            'economic': self.config.economic,
            'silent_failure': self.config.silent_failure,
            'formal_verification': self.config.formal_verification,
            'provenance': self.config.provenance,
            'performance': self.config.performance
        }
        
        for name, component in components.items():
            if hasattr(component, 'validate'):
                issues = component.validate()
                self.validation_results['component_validations'][name] = {
                    'valid': len(issues) == 0,
                    'issues': issues
                }
    
    def _check_environment_compatibility(self):
        """Check environment-specific compatibility"""
        env = self.config.deployment_environment
        
        compatibility_checks = {
            'python_version': sys.version_info >= (3, 8),
            'memory_requirements': True,
            'feature_compatibility': True
        }
        
        # Environment-specific checks
        if env == DeploymentEnvironment.PRODUCTION:
            # Production shouldn't have debug features enabled
            if self.config.enable_debug_mode:
                compatibility_checks['debug_in_production'] = False
            
            # Production should have reasonable resource limits
            if self.config.performance.max_memory_usage_mb > 512:
                compatibility_checks['excessive_memory'] = False
        
        elif env == DeploymentEnvironment.RESEARCH:
            # Research should have comprehensive features
            if not all([
                self.config.enable_graph_analysis,
                self.config.enable_formal_verification,
                self.config.enable_provenance_tracking
            ]):
                compatibility_checks['insufficient_research_features'] = False
        
        self.validation_results['environment_compatibility'] = compatibility_checks
    
    def _check_resource_requirements(self):
        """Check resource requirement consistency"""
        requirements = {
            'estimated_memory_mb': self._estimate_memory_usage(),
            'estimated_cpu_load': self._estimate_cpu_load(),
            'storage_requirements_mb': self._estimate_storage_requirements(),
            'network_bandwidth_kbps': self._estimate_network_bandwidth()
        }
        
        # Check against configured limits
        requirements['within_memory_limit'] = (
            requirements['estimated_memory_mb'] <= self.config.performance.max_memory_usage_mb
        )
        
        self.validation_results['resource_requirements'] = requirements
    
    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage based on configuration"""
        base_memory = 32  # Base SCAFAD overhead
        
        if self.config.enable_graph_analysis:
            # Estimate based on max nodes and edges
            node_memory = self.config.graph.max_nodes * 0.001  # ~1KB per node
            edge_memory = self.config.graph.max_edges * 0.0005  # ~0.5KB per edge
            base_memory += node_memory + edge_memory
        
        if self.config.enable_adversarial_simulation and self.config.adversarial.enable_gan_generation:
            # GAN models require significant memory
            gan_memory = (
                self.config.adversarial.gan_latent_dim * 
                self.config.adversarial.gan_feature_dim * 
                0.001  # Rough estimate
            )
            base_memory += gan_memory
        
        if self.config.enable_provenance_tracking:
            # Provenance chains
            provenance_memory = self.config.provenance.max_chain_length * 0.01
            base_memory += provenance_memory
        
        return int(base_memory)
    
    def _estimate_cpu_load(self) -> float:
        """Estimate CPU load (0.0 to 1.0)"""
        base_load = 0.1  # Base processing
        
        if self.config.enable_graph_analysis:
            base_load += 0.2
        
        if self.config.enable_adversarial_simulation:
            base_load += 0.3
        
        if self.config.enable_formal_verification:
            base_load += 0.25
        
        return min(base_load, 1.0)
    
    def _estimate_storage_requirements(self) -> int:
        """Estimate storage requirements in MB"""
        base_storage = 5  # Base SCAFAD
        
        if self.config.enable_provenance_tracking:
            base_storage += self.config.provenance.max_snapshots * 0.1
        
        if self.config.performance.enable_caching:
            base_storage += self.config.performance.max_cache_size * 0.001
        
        return int(base_storage)
    
    def _estimate_network_bandwidth(self) -> int:
        """Estimate network bandwidth requirements in KB/s"""
        base_bandwidth = 1  # Minimal telemetry
        
        if self.config.telemetry.enable_primary_channel:
            base_bandwidth += 5
        
        if self.config.telemetry.enable_metrics_channel:
            base_bandwidth += 2
        
        return base_bandwidth
    
    def _perform_security_checks(self):
        """Perform security-related configuration checks"""
        security_checks = {
            'adversarial_safety': True,
            'debug_mode_safe': True,
            'resource_limits_safe': True,
            'feature_exposure_safe': True
        }
        
        # Check adversarial settings
        if (self.config.adversarial.enable_poisoning_attacks and 
            self.config.adversarial.max_poisoning_rate > 0.1):
            security_checks['adversarial_safety'] = False
        
        # Check debug mode in production
        if (self.config.deployment_environment == DeploymentEnvironment.PRODUCTION and
            self.config.enable_debug_mode):
            security_checks['debug_mode_safe'] = False
        
        # Check resource limits
        if self.config.performance.max_memory_usage_mb > 1024:  # 1GB
            security_checks['resource_limits_safe'] = False
        
        self.validation_results['security_checks'] = security_checks
    
    def _check_performance_implications(self):
        """Check for performance implications and warnings"""
        warnings = []
        
        # High resource usage warnings
        if self.config.graph.max_nodes > 10000:
            warnings.append("Large graph size may impact performance")
        
        if (self.config.enable_formal_verification and 
            self.config.formal_verification.verification_timeout_seconds > 30):
            warnings.append("Long verification timeout may cause latency")
        
        if (self.config.adversarial.enable_gan_generation and
            self.config.adversarial.gan_epochs > 100):
            warnings.append("High GAN epoch count may cause startup delays")
        
        # Feature combination warnings
        enabled_features = sum([
            self.config.enable_graph_analysis,
            self.config.enable_adversarial_simulation,
            self.config.enable_economic_monitoring,
            self.config.enable_silent_failure_detection,
            self.config.enable_formal_verification,
            self.config.enable_provenance_tracking
        ])
        
        if enabled_features > 4:
            warnings.append("Many features enabled may impact performance")
        
        self.validation_results['performance_warnings'] = warnings
    
    def _calculate_overall_validity(self) -> bool:
        """Calculate overall configuration validity"""
        
        # Check component validations
        component_valid = all(
            result['valid'] 
            for result in self.validation_results['component_validations'].values()
        )
        
        # Check environment compatibility
        env_compatible = all(
            self.validation_results['environment_compatibility'].values()
        )
        
        # Check security
        security_safe = all(
            self.validation_results['security_checks'].values()
        )
        
        # Check resource requirements
        resources_ok = self.validation_results['resource_requirements']['within_memory_limit']
        
        return component_valid and env_compatible and security_safe and resources_ok


# =============================================================================
# Configuration Monitoring & Health Checks
# =============================================================================

class ConfigurationMonitor:
    """Monitor configuration health and provide runtime diagnostics"""
    
    def __init__(self, config: Layer0Config):
        self.config = config
        self.start_time = time.time()
        self.health_history = []
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current configuration health status"""
        
        current_time = time.time()
        uptime_seconds = current_time - self.start_time
        
        health_status = {
            'timestamp': current_time,
            'uptime_seconds': uptime_seconds,
            'configuration_version': self.config.version['version'],
            'environment': self.config.deployment_environment.value,
            'feature_status': self._get_feature_status(),
            'resource_usage': self._get_resource_usage(),
            'performance_metrics': self._get_performance_metrics(),
            'warnings': self._get_current_warnings()
        }
        
        # Store in history
        self.health_history.append(health_status)
        
        # Keep only last 100 entries
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]
        
        return health_status
    
    def _get_feature_status(self) -> Dict[str, str]:
        """Get status of each feature"""
        return {
            'graph_analysis': 'enabled' if self.config.enable_graph_analysis else 'disabled',
            'adversarial_simulation': 'enabled' if self.config.enable_adversarial_simulation else 'disabled',
            'economic_monitoring': 'enabled' if self.config.enable_economic_monitoring else 'disabled',
            'silent_failure_detection': 'enabled' if self.config.enable_silent_failure_detection else 'disabled',
            'formal_verification': 'enabled' if self.config.enable_formal_verification else 'disabled',
            'provenance_tracking': 'enabled' if self.config.enable_provenance_tracking else 'disabled'
        }
    
    def _get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage estimates"""
        try:
            import psutil
            process = psutil.Process()
            
            return {
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'cpu_percent': process.cpu_percent(),
                'memory_limit_mb': self.config.performance.max_memory_usage_mb,
                'memory_utilization': (process.memory_info().rss / 1024 / 1024) / self.config.performance.max_memory_usage_mb
            }
        except ImportError:
            return {
                'memory_mb': 'unknown',
                'cpu_percent': 'unknown',
                'memory_limit_mb': self.config.performance.max_memory_usage_mb,
                'memory_utilization': 'unknown'
            }
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance-related metrics"""
        return {
            'max_graph_nodes': self.config.graph.max_nodes,
            'temporal_window_s': self.config.telemetry.temporal_window_seconds,
            'async_timeout_s': self.config.performance.async_timeout_seconds,
            'caching_enabled': self.config.performance.enable_caching,
            'verbosity_level': self.config.verbosity_level.value
        }
    
    def _get_current_warnings(self) -> List[str]:
        """Get current configuration warnings"""
        warnings = []
        
        # Runtime validation
        validator = ConfigurationValidator(self.config)
        validation_results = validator.validate_all()
        
        # Add performance warnings
        warnings.extend(validation_results.get('performance_warnings', []))
        
        # Add security warnings
        security_checks = validation_results.get('security_checks', {})
        for check_name, check_result in security_checks.items():
            if not check_result:
                warnings.append(f"Security concern: {check_name}")
        
        return warnings


# =============================================================================
# Main Module Interface
# =============================================================================

def get_default_config() -> Layer0Config:
    """Get default configuration based on environment"""
    return ConfigurationFactory.create_config()


def validate_current_environment() -> Dict[str, Any]:
    """Validate current environment and return comprehensive report"""
    env_validation = validate_environment()
    deployment_info = get_deployment_info()
    
    # Try to create default config and validate it
    try:
        config = get_default_config()
        validator = ConfigurationValidator(config)
        config_validation = validator.validate_all()
    except Exception as e:
        config_validation = {'error': str(e), 'overall_valid': False}
    
    return {
        'environment_validation': env_validation,
        'deployment_info': deployment_info,
        'configuration_validation': config_validation,
        'timestamp': time.time()
    }


# =============================================================================
# CLI Interface & Testing
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='SCAFAD Layer 0 Configuration Management')
    parser.add_argument('--validate', action='store_true', help='Validate environment and configuration')
    parser.add_argument('--create-config', choices=['development', 'testing', 'research', 'production'], 
                       help='Create configuration for specified environment')
    parser.add_argument('--save-config', type=str, help='Save configuration to file')
    parser.add_argument('--load-config', type=str, help='Load configuration from file')
    parser.add_argument('--show-summary', action='store_true', help='Show configuration summary')
    parser.add_argument('--environment', choices=['development', 'testing', 'research', 'production'],
                       help='Specify deployment environment')
    
    args = parser.parse_args()
    
    if args.validate:
        print("Validating SCAFAD Layer 0 Environment...")
        print("=" * 50)
        
        validation_report = validate_current_environment()
        
        # Environment validation
        env_results = validation_report['environment_validation']
        print("Environment Validation:")
        for check, result in env_results.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check}")
        
        # Configuration validation
        config_results = validation_report['configuration_validation']
        if 'error' in config_results:
            print(f"\n❌ Configuration Error: {config_results['error']}")
        else:
            print(f"\nConfiguration Validation: {'✅ PASSED' if config_results['overall_valid'] else '❌ FAILED'}")
            
            # Component results
            for component, result in config_results.get('component_validations', {}).items():
                status = "✅" if result['valid'] else "❌"
                print(f"  {status} {component}")
                if result['issues']:
                    for issue in result['issues']:
                        print(f"    - {issue}")
        
        print(f"\nOverall Status: {'✅ READY' if all(env_results.values()) and config_results.get('overall_valid', False) else '❌ ISSUES FOUND'}")
    
    elif args.create_config:
        print(f"Creating {args.create_config} configuration...")
        
        config = ConfigurationFactory.create_config(args.create_config)
        
        if args.save_config:
            config.save_to_file(args.save_config)
            print(f"Configuration saved to {args.save_config}")
        else:
            print("\nConfiguration Summary:")
            print(json.dumps(config.get_summary(), indent=2))
    
    elif args.load_config:
        print(f"Loading configuration from {args.load_config}...")
        
        try:
            config = Layer0Config.load_from_file(args.load_config)
            print("Configuration loaded successfully!")
            
            if args.show_summary:
                print("\nConfiguration Summary:")
                print(json.dumps(config.get_summary(), indent=2))
                
        except Exception as e:
            print(f"❌ Failed to load configuration: {e}")
    
    elif args.show_summary:
        config = get_default_config()
        print("Default Configuration Summary:")
        print("=" * 40)
        print(json.dumps(config.get_summary(), indent=2))
    
    else:
        print("SCAFAD Layer 0 Configuration Management")
        print("Use --help for available options")
        
        # Show quick status
        try:
            config = get_default_config()
            print(f"\nDefault Environment: {config.deployment_environment.value}")
            print(f"Version: {config.version['version']}")
            print(f"Features Enabled: {sum(config.get_summary()['features_enabled'].values())}/6")
        except Exception as e:
            print(f"❌ Configuration Error: {e}")