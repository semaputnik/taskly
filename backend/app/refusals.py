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

Only the codes this slice (#279) needs are introduced here. The other forty
code-less refusals `app.api.access` and inline route checks still raise as a
plain-string `HTTPException` detail are left exactly as they are (#275) —
this module gains a code only when a ticket actually moves the path it sits
on, never ahead of it.
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


class Refusal(Exception):
    """
    A decision not to perform an act: an exhaustive `code` a client matches
    on, the `status` an HTTP adapter answers with, one `message` for a
    person, and a typed `payload` carrying what stood in the way — `None`
    when there is nothing beyond the message itself to carry.
    """

    def __init__(
        self,
        code: RefusalCode,
        status: int,
        message: str,
        payload: object = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.status = status
        self.message = message
        self.payload = payload


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
