"""Stub identity provider for the SCAFAD GUI (Phase 2 indirection).

Per ADR-12 of the Phase-2 architecture, write routes record an actor (case
``created_by`` / ``actor_id``, comment ``author_id``, view ``owner_id``).
Phase 5 will swap in a real OIDC/SAML provider; until then this module
exposes a single hard-coded analyst.

The indirection means Phase-2 routes can depend on
:func:`get_current_user` via ``Depends(get_current_user)`` rather than
hard-coding the literal ``analyst@scafad.local`` string at every call site.
A future agent only needs to replace the body of :func:`get_current_user`
to wire real authentication in.

A second analyst (``analyst-2@scafad.local``) is exposed via
:data:`KNOWN_USERS` so the seeder can demonstrate multi-user assignment
in demo mode without spinning up a real auth backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from fastapi import Request


@dataclass(frozen=True)
class User:
    """A minimal user record.

    Phase 2 exposes the bare minimum fields routes need to record an actor.
    Phase 5 may extend this with display name, avatar URL, group/role
    membership without breaking the dependency contract.
    """

    id: str
    email: str
    display_name: str
    role: str = "analyst"


PRIMARY_ANALYST: User = User(
    id="analyst@scafad.local",
    email="analyst@scafad.local",
    display_name="Primary Analyst",
    role="analyst",
)


SECONDARY_ANALYST: User = User(
    id="analyst-2@scafad.local",
    email="analyst-2@scafad.local",
    display_name="Secondary Analyst",
    role="analyst",
)


KNOWN_USERS: Dict[str, User] = {
    PRIMARY_ANALYST.id: PRIMARY_ANALYST,
    SECONDARY_ANALYST.id: SECONDARY_ANALYST,
}


def get_user(user_id: str) -> Optional[User]:
    """Look up a known user by id (or email)."""

    return KNOWN_USERS.get(user_id)


def list_users() -> List[User]:
    """List all known users; used by the AssigneePicker demo dropdown."""

    return list(KNOWN_USERS.values())


def get_current_user(request: Request) -> User:
    """FastAPI dependency: return the user driving the current request.

    Phase 2 always returns :data:`PRIMARY_ANALYST`.  An ``X-Test-User`` header
    is honoured in tests so route assertions can switch identities without
    reaching into FastAPI's auth machinery.
    """

    override = request.headers.get("X-Test-User") if request else None
    if override and override in KNOWN_USERS:
        return KNOWN_USERS[override]
    # Allow the app state to override the default user (used by tests).
    state_user = getattr(request.app.state, "current_user", None) if request else None
    if isinstance(state_user, User):
        return state_user
    return PRIMARY_ANALYST


__all__ = [
    "User",
    "PRIMARY_ANALYST",
    "SECONDARY_ANALYST",
    "KNOWN_USERS",
    "get_user",
    "list_users",
    "get_current_user",
]
