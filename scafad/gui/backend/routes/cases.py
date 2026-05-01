"""``/api/cases`` — case CRUD, attachments, comments, lifecycle audit (Phase 2).

Each write route emits one ``event: case`` SSE frame after commit (per
ADR-15) so the frontend can invalidate the relevant query keys without
polling.

Routes:

================  =======  =====================================================
Method            Path     Purpose
================  =======  =====================================================
GET               /api/cases                              list cases
POST              /api/cases                              create new case
GET               /api/cases/{id}                         full case
PATCH             /api/cases/{id}                         optimistic mutate
DELETE            /api/cases/{id}                         hard delete (ADR-9)
POST              /api/cases/{id}/attach                  attach detection ids
POST              /api/cases/{id}/detach                  detach detection ids
GET               /api/cases/{id}/events                  lifecycle audit log
GET               /api/cases/{id}/comments                list comments
POST              /api/cases/{id}/comments                add comment
GET               /api/cases/{id}/detections              list linked detections
================  =======  =====================================================
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from ..audit import record_audit
from ..schemas import (
    BulkActionResponse,
    BulkActionResult,
    Case,
    CaseCreate,
    CaseEvent,
    CaseEventListResponse,
    CaseListResponse,
    CaseSummary,
    CaseUpdate,
    Comment,
    CommentCreate,
    CommentListResponse,
    DetectionListResponse,
    DetectionSummary,
)
from ..store import (
    AlreadyAttached,
    DetectionStore,
    DuplicateAttachment,
    NotFound,
    StoreError,
    VersionConflict,
    case_event_to_dict,
    case_to_dict,
    case_to_summary_dict,
    comment_to_dict,
    detection_to_summary_dict,
)
from ..users import User, get_current_user


logger = logging.getLogger("scafad.gui.routes.cases")


router = APIRouter(prefix="/api/cases", tags=["cases"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _publish_case(request: Request, case_dict: dict, *, action: str) -> None:
    bus = getattr(request.app.state, "event_bus", None)
    if bus is None:
        return
    payload = {"action": action, "case": case_dict}
    try:
        await bus.publish(payload, event_type="case")
    except Exception:  # pragma: no cover - defensive
        logger.debug("SSE case publish failed", exc_info=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=CaseListResponse)
def list_cases(
    request: Request,
    status: Optional[str] = Query(default=None),
    assignee_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> CaseListResponse:
    """List cases newest-first, filtered by status / assignee."""

    store: DetectionStore = request.app.state.store
    rows, total = store.list_cases(
        status=status,
        assignee_id=assignee_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    items = [CaseSummary(**case_to_summary_dict(r)) for r in rows]
    return CaseListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=Case, status_code=201)
async def create_case(
    request: Request,
    body: CaseCreate,
    user: User = Depends(get_current_user),
) -> Case:
    """Open a new case with optional initial detection attachments."""

    store: DetectionStore = request.app.state.store
    try:
        row = store.create_case(
            title=body.title,
            created_by=user.id,
            detection_ids=list(body.detection_ids),
            assignee_id=body.assignee_id,
            status=body.status,
        )
    except AlreadyAttached as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except StoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    case = Case(**case_to_dict(row))
    await _publish_case(request, case_to_summary_dict(row), action="created")
    record_audit(
        request,
        actor_id=user.id,
        subject_kind="case",
        subject_id=row.id,
        action="created",
        payload={"title": row.title, "status": row.status},
    )
    return case


@router.get("/{case_id}", response_model=Case)
def get_case(request: Request, case_id: str) -> Case:
    store: DetectionStore = request.app.state.store
    row = store.get_case(case_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"case '{case_id}' not found")
    return Case(**case_to_dict(row))


@router.patch("/{case_id}", response_model=Case)
async def update_case(
    request: Request,
    case_id: str,
    body: CaseUpdate,
    user: User = Depends(get_current_user),
) -> Case:
    """Mutate title / status / assignee using optimistic concurrency.

    Returns ``409 Conflict`` if ``expected_version`` no longer matches the
    stored row's ``version``.
    """

    store: DetectionStore = request.app.state.store
    try:
        row = store.update_case(
            case_id,
            expected_version=body.expected_version,
            actor_id=user.id,
            title=body.title,
            status=body.status,
            assignee_id=body.assignee_id,
            reason=body.reason,
        )
    except NotFound:
        raise HTTPException(status_code=404, detail=f"case '{case_id}' not found")
    except VersionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "version conflict",
                "current_version": exc.current_version,
                "expected_version": exc.expected_version,
            },
        )
    except StoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    case = Case(**case_to_dict(row))
    await _publish_case(request, case_to_summary_dict(row), action="updated")
    record_audit(
        request,
        actor_id=user.id,
        subject_kind="case",
        subject_id=case_id,
        action="updated",
        payload={"title": row.title, "status": row.status, "assignee_id": row.assignee_id},
    )
    return case


@router.delete("/{case_id}", status_code=204, response_class=Response)
async def delete_case(
    request: Request,
    case_id: str,
    user: User = Depends(get_current_user),
) -> Response:
    store: DetectionStore = request.app.state.store
    try:
        store.delete_case(case_id, actor_id=user.id)
    except NotFound:
        raise HTTPException(status_code=404, detail=f"case '{case_id}' not found")
    await _publish_case(request, {"id": case_id}, action="deleted")
    record_audit(
        request,
        actor_id=user.id,
        subject_kind="case",
        subject_id=case_id,
        action="deleted",
        payload={},
    )
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------


@router.post("/{case_id}/attach", response_model=BulkActionResponse)
async def attach_detections(
    request: Request,
    case_id: str,
    body: dict,
    user: User = Depends(get_current_user),
) -> BulkActionResponse:
    store: DetectionStore = request.app.state.store
    detection_ids = list(body.get("detection_ids", []))
    if not detection_ids:
        raise HTTPException(status_code=422, detail="detection_ids must not be empty")
    if store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail=f"case '{case_id}' not found")
    results: List[BulkActionResult] = []
    succeeded = 0
    failed = 0
    for did in detection_ids:
        try:
            store.attach_detection(case_id, did, actor_id=user.id)
            results.append(BulkActionResult(id=did, ok=True))
            succeeded += 1
        except (AlreadyAttached, DuplicateAttachment, NotFound, StoreError) as exc:
            results.append(BulkActionResult(id=did, ok=False, error=str(exc)))
            failed += 1
    response = BulkActionResponse(
        action="attach",
        results=results,
        succeeded=succeeded,
        failed=failed,
        case_id=case_id,
    )
    case_row = store.get_case(case_id)
    if case_row is not None:
        await _publish_case(request, case_to_summary_dict(case_row), action="attached")
    record_audit(
        request,
        actor_id=user.id,
        subject_kind="case",
        subject_id=case_id,
        action="attached",
        payload={"selection_size": len(detection_ids), "succeeded": succeeded, "failed": failed},
    )
    return response


@router.post("/{case_id}/detach", response_model=BulkActionResponse)
async def detach_detections(
    request: Request,
    case_id: str,
    body: dict,
    user: User = Depends(get_current_user),
) -> BulkActionResponse:
    store: DetectionStore = request.app.state.store
    detection_ids = list(body.get("detection_ids", []))
    if not detection_ids:
        raise HTTPException(status_code=422, detail="detection_ids must not be empty")
    if store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail=f"case '{case_id}' not found")
    results: List[BulkActionResult] = []
    succeeded = 0
    failed = 0
    for did in detection_ids:
        try:
            store.detach_detection(case_id, did, actor_id=user.id)
            results.append(BulkActionResult(id=did, ok=True))
            succeeded += 1
        except (NotFound, StoreError) as exc:
            results.append(BulkActionResult(id=did, ok=False, error=str(exc)))
            failed += 1
    response = BulkActionResponse(
        action="attach",  # the endpoint doesn't reuse "attach"; we record "detach" via SSE.
        results=results,
        succeeded=succeeded,
        failed=failed,
        case_id=case_id,
    )
    case_row = store.get_case(case_id)
    if case_row is not None:
        await _publish_case(request, case_to_summary_dict(case_row), action="detached")
    record_audit(
        request,
        actor_id=user.id,
        subject_kind="case",
        subject_id=case_id,
        action="detached",
        payload={"selection_size": len(detection_ids), "succeeded": succeeded, "failed": failed},
    )
    return response


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@router.get("/{case_id}/events", response_model=CaseEventListResponse)
def list_case_events_endpoint(request: Request, case_id: str) -> CaseEventListResponse:
    store: DetectionStore = request.app.state.store
    if store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail=f"case '{case_id}' not found")
    rows = store.list_case_events(case_id)
    items = [CaseEvent(**case_event_to_dict(r)) for r in rows]
    return CaseEventListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@router.get("/{case_id}/comments", response_model=CommentListResponse)
def list_comments_endpoint(request: Request, case_id: str) -> CommentListResponse:
    store: DetectionStore = request.app.state.store
    if store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail=f"case '{case_id}' not found")
    rows = store.list_comments(case_id)
    items = [Comment(**comment_to_dict(r)) for r in rows]
    return CommentListResponse(items=items, total=len(items))


@router.post("/{case_id}/comments", response_model=Comment, status_code=201)
async def add_comment_endpoint(
    request: Request,
    case_id: str,
    body: CommentCreate,
    user: User = Depends(get_current_user),
) -> Comment:
    store: DetectionStore = request.app.state.store
    if store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail=f"case '{case_id}' not found")
    try:
        row = store.add_comment(case_id, user.id, body.body_md)
    except StoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    comment = Comment(**comment_to_dict(row))
    case_row = store.get_case(case_id)
    if case_row is not None:
        await _publish_case(request, case_to_summary_dict(case_row), action="commented")
    record_audit(
        request,
        actor_id=user.id,
        subject_kind="comment",
        subject_id=row.id,
        action="created",
        payload={"case_id": case_id},
    )
    return comment


# ---------------------------------------------------------------------------
# Linked detections
# ---------------------------------------------------------------------------


@router.get("/{case_id}/detections", response_model=DetectionListResponse)
def list_linked_detections(request: Request, case_id: str) -> DetectionListResponse:
    store: DetectionStore = request.app.state.store
    if store.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail=f"case '{case_id}' not found")
    rows = store.list_case_detections(case_id)
    items = [DetectionSummary(**detection_to_summary_dict(r)) for r in rows]
    return DetectionListResponse(items=items, total=len(items), page=1, page_size=len(items) or 50)


__all__ = ["router"]
