"""DTO parity test: Pydantic schemas ↔ TypeScript types.

This guard makes sure that whenever a backend DTO grows a field, the
corresponding ``TypeScript`` interface in
``scafad/gui/frontend/src/lib/types.ts`` is updated in the same commit.
The parity is loose-grained: we extract field NAMES from each Pydantic
model and check every name appears as a property in the matching TS
interface declaration.

A drift produces an actionable failure message that names the missing
field and the file to update.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Set, Type

import pytest

pytest.importorskip("pydantic")

from pydantic import BaseModel  # noqa: E402

from scafad.gui.backend import schemas  # noqa: E402


_TYPES_TS = (
    Path(__file__).resolve().parents[2]
    / "scafad" / "gui" / "frontend" / "src" / "lib" / "types.ts"
)


# Map Pydantic model class → TS interface name.  We only assert parity for
# DTOs the frontend actually consumes.
_PARITY_PAIRS: Dict[Type[BaseModel], str] = {
    schemas.HealthResponse: "HealthResponse",
    schemas.LayerStatus: "LayerStatus",
    schemas.SystemStatusResponse: "SystemStatusResponse",
    schemas.IngestResponse: "IngestResponse",
    schemas.DetectionSummary: "DetectionSummary",
    schemas.DetectionListResponse: "DetectionListResponse",
    schemas.DetectionDetail: "DetectionDetail",
    schemas.SeverityMix: "SeverityMix",
    schemas.HistogramBucket: "HistogramBucket",
    schemas.DashboardSummary: "DashboardSummary",
    # Phase 2
    schemas.CaseSummary: "CaseSummary",
    schemas.Case: "Case",
    schemas.CaseListResponse: "CaseListResponse",
    schemas.CaseCreate: "CaseCreate",
    schemas.CaseUpdate: "CaseUpdate",
    schemas.Comment: "Comment",
    schemas.CommentCreate: "CommentCreate",
    schemas.CommentListResponse: "CommentListResponse",
    schemas.CaseEvent: "CaseEvent",
    schemas.CaseEventListResponse: "CaseEventListResponse",
    schemas.SavedView: "SavedView",
    schemas.SavedViewCreate: "SavedViewCreate",
    schemas.SavedViewUpdate: "SavedViewUpdate",
    schemas.SavedViewListResponse: "SavedViewListResponse",
    schemas.BulkActionRequest: "BulkActionRequest",
    schemas.BulkActionResult: "BulkActionResult",
    schemas.BulkActionResponse: "BulkActionResponse",
    schemas.TechniqueCount: "TechniqueCount",
    schemas.CaseStatusCounts: "CaseStatusCounts",
    schemas.InboxSummary: "InboxSummary",
}


def _extract_interface_fields(types_ts: str, name: str) -> Set[str]:
    """Return the set of property names in ``interface <name> { … }``.

    Uses a tolerant regex that handles the trailing ``extends`` clause
    (DetectionDetail extends DetectionSummary).
    """

    pattern = re.compile(
        r"export\s+interface\s+" + re.escape(name) + r"(?:\s+extends\s+\w+(?:\s*,\s*\w+)*)?\s*\{([^}]*)\}",
        re.MULTILINE,
    )
    match = pattern.search(types_ts)
    assert match, f"interface {name} not found in {_TYPES_TS}"
    body = match.group(1)
    fields: Set[str] = set()
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        # property declaration: "name?: Type;" or "name: Type;"
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*\??\s*:", line)
        if m:
            fields.add(m.group(1))
    return fields


def test_types_ts_file_exists() -> None:
    assert _TYPES_TS.exists(), f"missing {_TYPES_TS}"


def test_pydantic_models_match_typescript_interfaces() -> None:
    types_ts = _TYPES_TS.read_text(encoding="utf-8")
    # Inherited fields: every "extends X" interface inherits X's fields.
    detection_summary_fields = _extract_interface_fields(types_ts, "DetectionSummary")

    failures = []
    for model, ts_name in _PARITY_PAIRS.items():
        ts_fields = _extract_interface_fields(types_ts, ts_name)
        if ts_name == "DetectionDetail":
            ts_fields = ts_fields | detection_summary_fields
        py_fields = set(model.model_fields.keys())
        missing = py_fields - ts_fields
        if missing:
            failures.append(
                f"{model.__name__} ↔ {ts_name}: missing in TS = {sorted(missing)}"
            )
    if failures:
        msg = (
            "TypeScript types in frontend/src/lib/types.ts have drifted from "
            "the Pydantic schemas in scafad/gui/backend/schemas.py.\n  - "
            + "\n  - ".join(failures)
        )
        pytest.fail(msg)


def test_severity_literals_present_in_ts() -> None:
    types_ts = _TYPES_TS.read_text(encoding="utf-8")
    assert '"observe"' in types_ts
    assert '"review"' in types_ts
    assert '"escalate"' in types_ts


def test_case_status_literals_present_in_ts() -> None:
    types_ts = _TYPES_TS.read_text(encoding="utf-8")
    for status in ("open", "triage", "contained", "closed"):
        assert f'"{status}"' in types_ts, f"missing CaseStatus literal: {status}"


def test_case_event_kinds_present_in_ts() -> None:
    types_ts = _TYPES_TS.read_text(encoding="utf-8")
    for kind in (
        "created",
        "state_changed",
        "assigned",
        "commented",
        "detection_attached",
        "detection_detached",
        "dismissed",
        "reopened",
    ):
        assert f'"{kind}"' in types_ts, f"missing CaseEventKind literal: {kind}"


def test_bulk_action_types_present_in_ts() -> None:
    types_ts = _TYPES_TS.read_text(encoding="utf-8")
    for action in ("assign", "dismiss", "attach", "open_case"):
        assert f'"{action}"' in types_ts, f"missing BulkActionType literal: {action}"
