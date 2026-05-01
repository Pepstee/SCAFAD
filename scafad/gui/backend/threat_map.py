"""MITRE ATT&CK threat mapping for Phase 3.

This module provides:

1. The static MITRE tactic/technique vocabulary — a 1-to-1 mirror of
   scafad/layer5/threat_alignment.py emitted techniques, WITHOUT importing
   from layer5 (boundary rule ADR-5).

2. Aggregation functions to build threat-map matrices by temporal windows.

The vocabulary is deliberately static so the GUI grid shape never changes;
if Layer 5 adds a new technique, the Phase-3 drift test will fail until
the GUI grid is updated.  This prevents silent vocabulary drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .store import DetectionStore


# ─────────────────────────────────────────────────────────────────────────────
# Static MITRE vocabulary (mirrors scafad/layer5/threat_alignment.py)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TechniqueDef:
    """A single MITRE technique."""

    id: str  # e.g. "T1059" or "T1059.009"
    name: str
    description: str


# The canonical grid.  Every cell (tactic, technique) is enumerated here.
# The order and completeness is critical — it drives the frontend heatmap layout.
MITRE_TACTIC_TECHNIQUE_GRID: Dict[str, List[TechniqueDef]] = {
    "execution": [
        TechniqueDef(
            id="T1059",
            name="Command and Scripting Interpreter",
            description="Adversary executes commands via shell, command line, "
            "or other interpreted scripting language.",
        ),
        TechniqueDef(
            id="T1648",
            name="Serverless Execution",
            description="Direct abuse of serverless functions (AWS Lambda, "
            "Azure Functions, etc.) for command execution.",
        ),
    ],
    "exfiltration": [
        TechniqueDef(
            id="T1567",
            name="Exfiltration Over Web Service",
            description="Data exfiltration to an attacker-controlled web service "
            "or public cloud storage.",
        ),
        TechniqueDef(
            id="T1537",
            name="Transfer Data to Cloud Account",
            description="Data exfiltration by transferring to an attacker-controlled "
            "cloud storage account.",
        ),
    ],
    "discovery": [
        TechniqueDef(
            id="T1580",
            name="Cloud Infrastructure Discovery",
            description="Adversary enumerates cloud services (compute, storage, "
            "databases) to identify target assets.",
        ),
    ],
    "credential-access": [
        TechniqueDef(
            id="T1552.005",
            name="Unsecured Credentials: Cloud Metadata API",
            description="Adversary extracts credentials from cloud metadata services "
            "(AWS IMDSv1, GCP metadata, etc.).",
        ),
    ],
    "collection": [
        TechniqueDef(
            id="T1059.009",
            name="Cloud API",
            description="Adversary invokes cloud provider APIs to collect "
            "sensitive data or enumerate resources.",
        ),
    ],
    "impact": [
        TechniqueDef(
            id="T1499",
            name="Endpoint Denial of Service",
            description="Adversary performs resource exhaustion to degrade "
            "service availability.",
        ),
    ],
}

# Reverse index: technique ID → tactic
TECHNIQUE_TO_TACTIC: Dict[str, str] = {
    tech.id: tactic
    for tactic, techs in MITRE_TACTIC_TECHNIQUE_GRID.items()
    for tech in techs
}

# Drift contract: Layer 5 must emit exactly these.
LAYER5_EXPECTED_TECHNIQUES = frozenset(TECHNIQUE_TO_TACTIC.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ThreatMapCell:
    """A single heatmap cell: (tactic, technique)."""

    technique_id: str
    count: int
    severity_max: Optional[str]  # "observe", "review", "escalate", or None
    last_seen: Optional[datetime]  # Most recent detection in the cell


@dataclass
class ThreatMapResponse:
    """HTTP response for GET /api/threat-map."""

    matrix: Dict[str, Dict[str, ThreatMapCell]]  # matrix[tactic][technique_id]
    window_spec: str  # "24h", "7d", "30d", "custom"
    since: str  # ISO-8601 datetime
    until: str  # ISO-8601 datetime


def aggregate_threat_map(
    store: DetectionStore,
    *,
    since: datetime,
    until: datetime,
) -> Dict[str, Dict[str, ThreatMapCell]]:
    """Build a threat-map matrix for the given temporal window.

    Args:
        store: The DetectionStore instance.
        since: Inclusive lower bound.
        until: Exclusive upper bound.

    Returns:
        Nested dict: matrix[tactic][technique_id] = ThreatMapCell
        Empty cells are present with count=0 so the grid shape is constant.
    """
    # Fetch all techniques observed in the window
    rows = store.threat_map_aggregate(since=since, until=until)

    # Build a lookup of observed techniques
    observed: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        technique_id = row["technique"]
        observed[technique_id] = {
            "count": row.get("hit_count", 0),
            "severity_max": row.get("severity_max"),
            "last_seen": row.get("last_seen"),
        }

    # Build the full matrix with empty cells
    matrix: Dict[str, Dict[str, ThreatMapCell]] = {}
    for tactic, technique_defs in MITRE_TACTIC_TECHNIQUE_GRID.items():
        matrix[tactic] = {}
        for tech_def in technique_defs:
            tech_id = tech_def.id
            obs = observed.get(tech_id, {})
            matrix[tactic][tech_id] = ThreatMapCell(
                technique_id=tech_id,
                count=obs.get("count", 0),
                severity_max=obs.get("severity_max"),
                last_seen=obs.get("last_seen"),
            )

    return matrix


__all__ = [
    "TechniqueDef",
    "ThreatMapCell",
    "ThreatMapResponse",
    "MITRE_TACTIC_TECHNIQUE_GRID",
    "TECHNIQUE_TO_TACTIC",
    "LAYER5_EXPECTED_TECHNIQUES",
    "aggregate_threat_map",
]
