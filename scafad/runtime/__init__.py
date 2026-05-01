"""
runtime — SCAFAD Canonical Runtime
====================================

Orchestrates the full L0 → L6 pipeline.

Public API
----------
  SCAFADCanonicalRuntime    — process_event(event) → CanonicalRuntimeResult
  SCAFADMultilayerPipeline  — run(layer1_record) → MultilayerPipelineResult
  lambda_handler            — AWS Lambda entry point
"""

from .runtime import SCAFADCanonicalRuntime, CanonicalRuntimeResult
from .pipeline import SCAFADMultilayerPipeline, MultilayerPipelineResult

__all__ = [
    "SCAFADCanonicalRuntime",
    "CanonicalRuntimeResult",
    "SCAFADMultilayerPipeline",
    "MultilayerPipelineResult",
]
