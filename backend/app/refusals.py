"""
A refusal: a decision not to perform an act, which names itself rather than
being assembled where it happens (#275).

Raised, never returned. A sum-typed result would mean teaching
`app.api.access` and `app.crud` to thread a refusal upward through every call
they are already part of — a rewrite of the access path this slice does not
need. Not a subclass of `HTTPException` either: an operation (`app.tasks`)
knows nothing about HTTP, and a refusal that was itself an `HTTPException`
would leak HTTP back into it. `app.main`'s own exception handler is the one
place that maps a `Refusal` to the HTTP body a route used to assemble itself,
byte for byte (#276) — the same shape `app.passkeys.PasskeyError` already
gets; `app.mcp.conventions.refusal` is the other, turning one into a
`ToolError` by reading its `code` and `message` directly, never guessing a
code from a status the way it still does for a plain `HTTPException`.

A refusal carries which of two body shapes it is (#282): `code` is `None`
for one pinned as a bare string (`#276`'s "a plain-string refusal is pinned
as code-less, exactly as it reads") and a `RefusalCode` for one pinned as
`{"code", "message"}`. `plain` builds the first kind; the handful of named
functions below build the second. Converting one of the fifteen `app.tasks`
raises this ticket moves into a refusal is never an occasion to give a bare
string a code — that is a deliberate, client-visible change the bodies #276
pinned are the proof nobody made here.

Only the codes the paths this slice (#279, #282) touches need are introduced
here. The other forty code-less refusals `app.api.access` and inline route
checks still raise as a plain-string `HTTPException` detail are left exactly
as they are (#275) — this module gains a code only when a ticket actually
moves the path it sits on, never ahead of it.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from app.models import Task


class RefusalCode(StrEnum):
    """
    Every code a `Refusal` can carry — exhaustive on purpose, so a client
    matches on one of these and never on a string this module did not name.
    """

    # ADR-0004 singles this code (and `leave_uncompleted`, a `TaskUpdate`
    # value rather than a refusal) out as wording clients already match on;
    # the words themselves are unchanged from what the route used to raise
    # inline (FR-02.5–FR-02.7, pinned byte for byte by #276).
    TASK_HAS_UNCOMPLETED_SUBTASKS = "task_has_uncompleted_subtasks"

    # A later occurrence already exists: reopening this one would leave the
    # series with two open occurrences (FR-01.16, #282).
    OCCURRENCE_SUPERSEDED = "occurrence_superseded"

    # Moving an open occurrence's due date means something different for the
    # rest of its series depending on the scope, so a request that does not
    # say which is malformed rather than defaulted (FR-01.17, #282).
    DUE_DATE_SCOPE_REQUIRED = "due_date_scope_required"

    # Deleting takes the whole subtree with it, so the request has to
    # confirm the cascade before anything goes (FR-01.12, #282).
    TASK_HAS_SUBTASKS = "task_has_subtasks"


@dataclass(frozen=True)
class OpenSubtask:
    """
    One task standing in the way of closing its parent, named by id and
    title — enough for a caller to list without a second trip to the
    database for the same subtree (#279).
    """

    id: uuid.UUID
    title: str


@dataclass(frozen=True)
class TaskHasUncompletedSubtasks:
    """What a `task_has_uncompleted_subtasks` refusal carries: the open subtasks themselves."""

    subtasks: list[OpenSubtask]


@dataclass(frozen=True)
class Subtask:
    """
    One task in the live subtree a delete would take down, named by id and
    title (#282) — not `OpenSubtask` above: a delete's cascade takes a done
    descendant along with an open one, so this one is never filtered to only
    what is still open the way closing's own refusal is.
    """

    id: uuid.UUID
    title: str


@dataclass(frozen=True)
class TaskHasSubtasks:
    """What a `task_has_subtasks` refusal carries: the whole live subtree it would take down."""

    subtasks: list[Subtask]


class Refusal(Exception):
    """
    A decision not to perform an act: an exhaustive `code` a client matches
    on, or `None` for one pinned as a bare string (#276, #282); the `status`
    an HTTP adapter answers with; one `message` for a person; and a typed
    `payload` carrying what stood in the way — `None` when there is nothing
    beyond the message itself to carry.
    """

    def __init__(
        self,
        code: RefusalCode | None,
        status: int,
        message: str,
        payload: object = None,
    ) -> None:
        super().__init__(message if code is None else f"{code}: {message}")
        self.code = code
        self.status = status
        self.message = message
        self.payload = payload


def plain(status: int, message: str) -> Refusal:
    """
    A refusal pinned as a bare string body (#276): no code, carrying only a
    status and a message — the shape every rule here had before this ticket
    (#282) moved its raise out of `app.tasks` and into this module, and the
    shape it keeps: giving one of these a code is a deliberate, client-visible
    change this ticket does not make.
    """
    return Refusal(code=None, status=status, message=message)


def task_has_uncompleted_subtasks(subtasks: list[Task]) -> Refusal:
    """
    The refusal `app.tasks.complete` raises for a close that leaves open
    subtasks unaddressed (FR-02.6): the same 409 and the same generic
    sentence the route used to assemble inline, plus the open subtasks
    themselves, so `complete_task` (the MCP tool, #257) can name them without
    asking the database again (#279).
    """
    return Refusal(
        code=RefusalCode.TASK_HAS_UNCOMPLETED_SUBTASKS,
        status=409,
        message=(
            "This task has open subtasks. Say whether they stay as they are "
            "or are done too."
        ),
        payload=TaskHasUncompletedSubtasks(
            subtasks=[OpenSubtask(id=t.id, title=t.title) for t in subtasks]
        ),
    )


def due_date_scope_required() -> Refusal:
    """
    The refusal `app.tasks.update` raises for a due-date move on an open
    occurrence of a series that does not say `due_date_scope` (FR-01.17):
    the same 400 and the same sentence the route used to assemble inline
    (#282).
    """
    return Refusal(
        code=RefusalCode.DUE_DATE_SCOPE_REQUIRED,
        status=400,
        message=(
            "This task recurs. Say whether the new due date applies to this "
            "occurrence only or to this and all following ones."
        ),
    )


def occurrence_superseded() -> Refusal:
    """
    The refusal `app.tasks.update` raises for reopening an occurrence a later
    one has already superseded (FR-01.16): the same 409 and the same
    sentence the route used to assemble inline (#282).
    """
    return Refusal(
        code=RefusalCode.OCCURRENCE_SUPERSEDED,
        status=409,
        message=(
            "A later occurrence of this recurring task already exists. Only "
            "the latest occurrence can be reopened."
        ),
    )


def task_has_subtasks(subtasks: list[Task]) -> Refusal:
    """
    The refusal `app.tasks.delete` raises for a delete that would take a
    live subtree down without confirming the cascade (FR-01.12): the same
    409 and the same generic sentence the route used to assemble inline,
    plus the whole live subtree itself — done descendants included, since
    the cascade takes them too — so `delete_task` (the MCP tool, #258) can
    name them without asking the database again (#282).
    """
    return Refusal(
        code=RefusalCode.TASK_HAS_SUBTASKS,
        status=409,
        message=(
            "This task has subtasks, which would be deleted with it. "
            "Confirm with delete_subtasks to go ahead."
        ),
        payload=TaskHasSubtasks(
            subtasks=[Subtask(id=t.id, title=t.title) for t in subtasks]
        ),
    )
