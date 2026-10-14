"""
A refusal: a decision not to perform an act, which names itself rather than
being assembled where it happens (#275).

Raised, never returned. A sum-typed result would mean teaching
`app.access` and `app.crud` to thread a refusal upward through every call
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
here. The other forty code-less refusals `app.access` and inline route
checks still raise as a plain-string `HTTPException` detail are left exactly
as they are (#275) — this module gains a code only when a ticket actually
moves the path it sits on, never ahead of it.

`app.access`'s own eleven raises moved here too (#309): the archive, the
scope and the missing-grant refusals, plus the comment-by-a-bot one. Four of
these carry a key besides `code` and `message` that the REST body already
gave a caller before this move — `project_id`, `permission`, `tags` — so
`Refusal` grew `extra` to carry them: a plain mapping `app.main`'s own
handler merges into the dict body, read by nothing else (`app.mcp.
conventions.refusal` only ever reads `code` and `message` off a `Refusal`,
same as it always has), so a refusal that carries nothing beyond its message
renders exactly as it did before `extra` existed.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.models import Project, Task


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

    # A bot never reaches an archived project, whichever action asked
    # (FR-05.13), and a human writing into one is refused the same way,
    # worded for what would undo it (FR-05.12, #309). The two call sites
    # share the code; the status and the wording differ by who is asking.
    PROJECT_ARCHIVED = "project_archived"

    # A bot asking after a project outside its scope (FR-08.8, #309).
    OUTSIDE_SCOPE = "outside_scope"

    # A bot asking for an action, or a tag name, its scope's permissions
    # do not grant (FR-08.9, #309).
    PERMISSION_NOT_GRANTED = "permission_not_granted"

    # A comment a bot user wrote, which no one may edit or delete, itself
    # included (FR-03.2, FR-08.10, #309).
    COMMENT_BY_BOT = "comment_by_bot"


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
    an HTTP adapter answers with; one `message` for a person; a typed
    `payload` carrying what stood in the way, read by a caller such as
    `app.mcp.conventions` that wants it structured — `None` when there is
    nothing beyond the message itself to carry; and `extra`, the handful of
    keys (`project_id`, `permission`, `tags`) a handful of refusals already
    put in their REST body before #309 moved their raise here, merged into
    the dict body alongside `code` and `message` rather than read back out
    of `payload` — empty for every refusal that carries nothing beyond its
    message.
    """

    def __init__(
        self,
        code: RefusalCode | None,
        status: int,
        message: str,
        payload: object = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message if code is None else f"{code}: {message}")
        self.code = code
        self.status = status
        self.message = message
        self.payload = payload
        self.extra = dict(extra) if extra else {}


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


# app.access's own refusals (#309): the archive, the scope, a missing grant,
# and a bot's comment — moved here from where `app.access` used to assemble
# an `HTTPException` inline, wording unchanged.


def archive_closed_to_bots() -> Refusal:
    """
    The refusal `app.access.refuse_archived_for_bot` gives a bot asking
    after the archive at large, with no one project named yet — nothing in
    it is reachable by a bot, whatever its scope (FR-05.13).
    """
    return Refusal(
        code=RefusalCode.PROJECT_ARCHIVED,
        status=403,
        message="Bot users have no access to archived projects.",
    )


def bot_project_archived(project: Project) -> Refusal:
    """
    The refusal a bot gets for a project it names directly, which turns out
    to be archived (FR-05.13): the project's own name in the sentence, and
    its id alongside `code` and `message` the way the REST body already
    carried it before this ticket moved the raise here.
    """
    return Refusal(
        code=RefusalCode.PROJECT_ARCHIVED,
        status=403,
        message=(
            f"The project “{project.name}” is archived. Bot users have no "
            "access to archived projects."
        ),
        extra={"project_id": str(project.id)},
    )


def bot_outside_scope(project: Project) -> Refusal:
    """
    The refusal a bot gets for a project it names directly, which is not in
    its scope (FR-08.8): a 403 of its own, distinct from a 404, so whoever
    wrote the integration can tell a configuration problem from a wrong id
    (story 33).
    """
    return Refusal(
        code=RefusalCode.OUTSIDE_SCOPE,
        status=403,
        message=f"The project “{project.name}” is not in this bot user's scope.",
        extra={"project_id": str(project.id)},
    )


def project_archived(project: Project) -> Refusal:
    """
    The refusal any change to an archived project, or to anything in it,
    gives — a human included: archiving freezes the project whole until it
    is unarchived (FR-05.12). The same code as the two bot-only refusals
    above, a different status and a different sentence: this one says what
    would undo it.
    """
    return Refusal(
        code=RefusalCode.PROJECT_ARCHIVED,
        status=409,
        message=(
            f"The project “{project.name}” is archived, so it and its tasks "
            "are read-only. Unarchive it to make changes."
        ),
        extra={"project_id": str(project.id)},
    )


def permission_not_granted(permission: str, doing: str) -> Refusal:
    """
    The refusal a bot gets for an action, or a listing across its scope, its
    permissions do not grant: `doing` is the sentence's own words for
    `permission` (`"create tasks"` for `create_tasks`, and so on) — shared by
    every one of `app.access`'s per-action, tag-creation and activity-log
    grant checks, which otherwise differ only in which permission and which
    words they name.
    """
    return Refusal(
        code=RefusalCode.PERMISSION_NOT_GRANTED,
        status=403,
        message=f"This bot user is not allowed to {doing}.",
        extra={"permission": permission},
    )


def tag_names_not_granted(new: list[str]) -> Refusal:
    """
    The refusal `app.access.authorize_tag_names` gives a bot without
    `create_tags` whose request names a tag its owner does not have yet
    (ADR-0003): which names were new comes back too, so an integration can
    send the rest rather than guess at the vocabulary it is allowed to add
    to.
    """
    return Refusal(
        code=RefusalCode.PERMISSION_NOT_GRANTED,
        status=403,
        message=(
            "This bot user is not allowed to create tags, and "
            + ", ".join(f"“{name}”" for name in new)
            + (" is not a tag yet." if len(new) == 1 else " are not tags yet.")
        ),
        extra={"permission": "create_tags", "tags": new},
    )


def comment_by_bot() -> Refusal:
    """
    The refusal `app.access.get_comment` gives for changing a comment a bot
    user wrote: what a bot user said stays on the record, for everyone, its
    owner included (FR-03.2, FR-08.10).
    """
    return Refusal(
        code=RefusalCode.COMMENT_BY_BOT,
        status=403,
        message=(
            "This comment was written by a bot user. Comments from bot "
            "users cannot be edited or deleted."
        ),
    )
