"""``/api/views`` — saved views CRUD (per-owner) for the Inbox.

Each route filters on the current user's id (per ADR-16 of the Phase-2
architecture) so future multi-tenant isolation lights up without schema
change.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..audit import record_audit
from ..schemas import (
    SavedView,
    SavedViewCreate,
    SavedViewListResponse,
    SavedViewUpdate,
)
from ..store import (
    DetectionStore,
    NotFound,
    StoreError,
    saved_view_to_dict,
)
from ..users import User, get_current_user


router = APIRouter(prefix="/api/views", tags=["views"])


@router.get("", response_model=SavedViewListResponse)
def list_views(
    request: Request,
    user: User = Depends(get_current_user),
) -> SavedViewListResponse:
    store: DetectionStore = request.app.state.store
    rows = store.list_views(user.id)
    items = [SavedView(**saved_view_to_dict(r)) for r in rows]
    return SavedViewListResponse(items=items, total=len(items))


@router.post("", response_model=SavedView, status_code=201)
def create_view(
    request: Request,
    body: SavedViewCreate,
    user: User = Depends(get_current_user),
) -> SavedView:
    store: DetectionStore = request.app.state.store
    try:
        row = store.create_view(
            owner_id=user.id,
            name=body.name,
            filter_json=body.filter_json,
            sort_json=body.sort_json,
            pinned=body.pinned,
        )
    except StoreError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    record_audit(
        request,
        actor_id=user.id,
        subject_kind="view",
        subject_id=row.id,
        action="created",
        payload={"name": row.name},
    )
    return SavedView(**saved_view_to_dict(row))


@router.patch("/{view_id}", response_model=SavedView)
def update_view(
    request: Request,
    view_id: str,
    body: SavedViewUpdate,
    user: User = Depends(get_current_user),
) -> SavedView:
    store: DetectionStore = request.app.state.store
    try:
        row = store.update_view(
            view_id,
            owner_id=user.id,
            name=body.name,
            filter_json=body.filter_json,
            sort_json=body.sort_json,
            pinned=body.pinned,
        )
    except NotFound:
        raise HTTPException(status_code=404, detail=f"view '{view_id}' not found")
    except StoreError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    record_audit(
        request,
        actor_id=user.id,
        subject_kind="view",
        subject_id=view_id,
        action="updated",
        payload={"name": row.name},
    )
    return SavedView(**saved_view_to_dict(row))


@router.delete("/{view_id}", status_code=204, response_class=Response)
def delete_view(
    request: Request,
    view_id: str,
    user: User = Depends(get_current_user),
) -> Response:
    store: DetectionStore = request.app.state.store
    try:
        store.delete_view(view_id, owner_id=user.id)
    except NotFound:
        raise HTTPException(status_code=404, detail=f"view '{view_id}' not found")
    record_audit(
        request,
        actor_id=user.id,
        subject_kind="view",
        subject_id=view_id,
        action="deleted",
        payload={},
    )
    return Response(status_code=204)


__all__ = ["router"]
