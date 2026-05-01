"""Cross-layer orchestration for the module-split SCAFAD architecture."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Optional

from layer1.pipeline import Layer1AuditRecord, Layer1ProcessedRecord, Layer1QualityReport
from layer2.detection_matrix import Layer2DetectionResult, MultiVectorDetectionMatrix
from layer3.trust_fusion import Layer3FusionResult, TrustWeightedFusionEngine
from layer4.explainability import ExplainabilityDecisionEngine, Layer4DecisionTrace
from layer5.threat_alignment import ThreatAlignmentEngine, ThreatAlignmentResult
from layer6.feedback_learning import FeedbackLearningEngine, Layer6FeedbackState


@dataclass
class MultilayerPipelineResult:
    layer1: Layer1ProcessedRecord
    layer2: Layer2DetectionResult
    layer3: Layer3FusionResult
    layer4: Layer4DecisionTrace
    layer5: ThreatAlignmentResult
    layer6: Optional[Layer6FeedbackState]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer1": self.layer1.to_dict(),
            "layer2": self.layer2.to_dict(),
            "layer3": self.layer3.to_dict(),
            "layer4": self.layer4.to_dict(),
            "layer5": self.layer5.to_dict(),
            "layer6": None if self.layer6 is None else self.layer6.to_dict(),
        }


class SCAFADMultilayerPipeline:
    def __init__(self) -> None:
        self.layer2 = MultiVectorDetectionMatrix()
        self.layer3 = TrustWeightedFusionEngine()
        self.layer4 = ExplainabilityDecisionEngine()
        self.layer5 = ThreatAlignmentEngine()
        self.layer6 = FeedbackLearningEngine()

    def process_record(
        self,
        record,
        analyst_label=None,
        redacted_fields=None,
        verbosity="standard",
        redaction_budget=0,
    ):
        if isinstance(record, Layer1ProcessedRecord):
            layer1_record = record
        else:
            quality_report = record.get("quality_report")
            if not isinstance(quality_report, Layer1QualityReport):
                quality_report = Layer1QualityReport(
                    completeness_score=1.0,
                    anomaly_signal_preservation=1.0,
                    pii_fields_redacted=0,
                    issues=[],
                )
            audit_record = record.get("audit_record")
            if not isinstance(audit_record, Layer1AuditRecord):
                audit_record = Layer1AuditRecord(
                    phases_completed=["legacy_import"],
                    redacted_fields=[],
                    hashed_fields=[],
                    warnings=[],
                    processing_time_ms=0.0,
                )
            layer1_record = Layer1ProcessedRecord(
                record_id=str(record["record_id"]),
                function_name=str(record["function_name"]),
                timestamp=float(record["timestamp"]),
                anomaly_type=str(record["anomaly_type"]),
                execution_phase=str(record["execution_phase"]),
                schema_version=str(record.get("schema_version", "v2.1")),
                telemetry_data=record.get("telemetry_data", {}),
                context_metadata=record.get("context_metadata", {}),
                provenance_chain=record.get("provenance_chain", {}),
                quality_report=quality_report,
                audit_record=audit_record,
                trace_id=str(record.get("trace_id", record["record_id"])),
                trust_context=copy.deepcopy(record.get("trust_context", {})),
            )

        l2 = self.layer2.analyze(layer1_record)
        l3 = self.layer3.fuse(l2)
        l4 = self.layer4.build_trace(
            l2, l3,
            verbosity=verbosity,
            redaction_budget=redaction_budget,
            redacted_fields=redacted_fields,
        )
        l5 = self.layer5.align(layer1_record.anomaly_type, l4)
        l6 = None
        if analyst_label is not None:
            l6 = self.layer6.ingest_feedback(
                record_id=l2.record_id,
                trace_id=l2.trace_id,
                analyst_label=analyst_label,
                threat_alignment=l5,
            )
        return MultilayerPipelineResult(
            layer1=layer1_record,
            layer2=l2,
            layer3=l3,
            layer4=l4,
            layer5=l5,
            layer6=l6,
        )


__all__ = ["MultilayerPipelineResult", "SCAFADMultilayerPipeline"]
