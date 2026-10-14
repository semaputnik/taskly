"""
`search_activity` (spec #247, #248, #259): the activity log itself, narrowed
the way `GET /activity-log/` already narrows it — by kind of change, by task,
by project, by actor and by period — read as compact lines rather than a page
of raw entries an agent would have to sort "finished" out of by hand.

Built on `app.activity_log.read_activity` (#298), the reader both this tool
and the REST route call — not re-derived from `app.access`/`crud` the way
`search_tasks` is. The scope narrowing (ADR-0011), the all-or-nothing batch
rule, the tag exemption and the permission check are all that reader's own
code; this tool only maps its arguments onto the reader's narrowing and
turns each row it hands back into one compact line, straight through, with
nothing to serialise and re-parse: an MCP caller is always a bot
(ADR-0012), so there is no `restorable` or deletion id to read here even if
this tool wanted to show one — it never asks the reader to compute them,
rather than asking a route to compute and then hide them.

This tool's own job, once the reader has answered: naming who acted
(`app.mcp.conventions.actor_label`'s own convention, also `get_task`'s
comment rows and `list_completions`'s own `closed_by`), saying what
happened in one short phrase, and naming the task, project or tag (or, for
a batch, the selection) the entry is about — ported from the web UI's own
`ActivityDescription.tsx`, since there is no backend description of an
entry yet and this tool is the first thing besides a human reading the
page that needs one.

`actor` and the `since`/`until` widening are read through
`app.mcp.conventions.resolve_actor`/`since_datetime`/`until_datetime`:
settled here first, then moved there once `list_completions` (#260) needed
the exact same reading of a period and of who acted, rather than its own
copy of either. `narrow_with` is `app.mcp.conventions.narrow_hint`'s own
(#301), with this tool's own priority order.
"""

import uuid
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlmodel import Session

from app import activity_details, crud
from app.activity_details import (
    AssigneeRef,
    AttachmentAddedDetails,
    AttachmentDeletedDetails,
    CommentAddedDetails,
    CommentDeletedDetails,
    CommentEditedDetails,
    ProjectChangedDetails,
    ProjectCreatedDetails,
    ProjectDeletedDetails,
    ProjectRestoredDetails,
    TagCreatedDetails,
    TagDeletedDetails,
    TagMergedDetails,
    TagRenamedDetails,
    TaskAssignedDetails,
    TaskChangedDetails,
    TaskCompletedDetails,
    TaskCreatedDetails,
    TaskDeletedBatch,
    TaskDeletedSingle,
    TaskMovedDetails,
    TaskReopenedDetails,
    TaskRestoredBatch,
    TaskRestoredSingle,
    TasksBulkChangedDetails,
    TaskStatusChangedDetails,
    TaskUnassignedDetails,
)
from app.activity_log import ActivityNarrowing, read_activity
from app.api.deps import Caller
from app.mcp.conventions import (
    actor_label,
    list_result,
    narrow_hint,
    open_caller,
    refusal,
    resolve_actor,
    resolve_project_id,
    resolve_task_id,
    short_id,
    since_datetime,
    until_datetime,
)
from app.mcp.server import mcp_server
from app.models import (
    ActivityEntry,
    ActivityKind,
    ActivityOrder,
    BotUserRef,
    TaskStatus,
)
from app.refusals import Refusal

# Every task-shaped detail model that carries a top-level `title` — every
# action but a batch's (`TaskDeletedBatch`/`TaskRestoredBatch`/
# `TasksBulkChangedDetails`, which name no single task at all) and a
# comment's or attachment's (which name their task by `TaskRef` instead).
_TASK_TITLED = (
    TaskCreatedDetails,
    TaskChangedDetails,
    TaskMovedDetails,
    TaskAssignedDetails,
    TaskUnassignedDetails,
    TaskCompletedDetails,
    TaskReopenedDetails,
    TaskStatusChangedDetails,
    TaskDeletedSingle,
    TaskRestoredSingle,
)
_PROJECT_NAMED = (
    ProjectCreatedDetails,
    ProjectChangedDetails,
    ProjectDeletedDetails,
    ProjectRestoredDetails,
)
_TAG_NAMED = (TagCreatedDetails, TagRenamedDetails, TagDeletedDetails, TagMergedDetails)
_ON_A_TASK = (
    CommentAddedDetails,
    CommentEditedDetails,
    CommentDeletedDetails,
    AttachmentAddedDetails,
    AttachmentDeletedDetails,
)

# How a status reads in a sentence, the backend's own copy of the web UI's
# `STATUS_LABELS` (`frontend/src/components/Tasks/statuses.tsx`) — this tool
# is the first thing on this side that renders an entry as a sentence at all.
_STATUS_LABELS = {
    TaskStatus.BACKLOG: "Backlog",
    TaskStatus.TODO: "To do",
    TaskStatus.IN_PROGRESS: "In progress",
    TaskStatus.WAITING: "Waiting",
    TaskStatus.REVIEW: "Review",
    TaskStatus.DONE: "Done",
}

# What each field is called when a "changed" entry lists what changed —
# ported from `ActivityDescription.tsx`'s own `FIELD_LABELS`.
_FIELD_LABELS = {
    "title": "title",
    "description": "description",
    "due_date": "due date",
    "priority": "priority",
    "tags": "tags",
    "recurrence": "repeat",
}


@mcp_server.tool(
    annotations=ToolAnnotations(read_only_hint=True),
)
def search_activity(
    ctx: Context,
    kind: ActivityKind | None = None,
    task_id: str | None = None,
    project: str | None = None,
    actor: str | None = None,
    since: str | None = None,
    until: str | None = None,
    order: ActivityOrder = ActivityOrder.NEWEST,
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict[str, Any]:
    """
    What has already happened — to one task, to one project, or across the
    whole account over a period — read from the activity log this bot user's
    `read_activity` grant opens (refused by name without it).

    `kind` groups the log the way a reader thinks about it rather than by
    its two dozen action names: `completed`, `created`, `changed`,
    `deleted`, `comments` or `tags`. The groups never overlap — closing
    several tasks in one act is `completed`, never `changed`, whichever act
    did it.

    `task_id` narrows to one task's own history: the entries about it, about
    the comments and files on it, and the batches that touched it, even
    though a batch is filed under only the first task it named. It takes a
    full id or the short prefix a compact line's own `id` prints, which only
    matches a live task — a deleted task's history still reads, but only by
    its full id from here on, once it is no longer there to prefix-match.
    `project` narrows to one project's chronology: the project itself, its
    tasks, and their comments and files, by a full id or by name
    case-insensitively. Either one outside this bot user's scope, or simply
    not there, is refused the way the API refuses it — never an empty
    history that would look like one with nothing in it.

    `actor` narrows to who acted: `self` (this bot user), `owner`, `any_bot`
    (any of the owner's bot users), or one bot user by name or id, resolved
    case-insensitively and refused by name if none matches — a deleted bot
    user's own entries still answer to its name (FR-08.19).

    `since` and `until` take a date — an ISO date, `today`, `tomorrow`, or
    `+<count>d` — read against the server's own date and widened to the
    whole day, so a closed calendar period ("last month") is named by its
    two dates rather than by exact moments: `since` from its start,
    exclusive, `until` through its end, inclusive.

    `order` reads `newest` or `oldest` first; `limit` and `offset` page
    through it. Nothing outside this bot user's scope ever appears, under
    any narrowing (ADR-0011); an entry about a task since deleted still
    reads, and nothing it says invites a restore only the owner can perform.

    Each result is one compact line: `at` (when), `actor` ("owner", or a bot
    user by name), `what` (one short phrase), and `subject` — the task,
    project or tag it happened to, with its id, or, for a batch, the
    selection it acted on. `count` is every entry the filters matched, not
    only this page; a `truncated` answer names one filter (`narrow_with`)
    still free to narrow with.
    """
    with open_caller(ctx) as (session, caller):
        return search_activity_body(
            session,
            caller,
            kind=kind,
            task_id=task_id,
            project=project,
            actor=actor,
            since=since,
            until=until,
            order=order,
            limit=limit,
            offset=offset,
        )


def search_activity_body(
    session: Session,
    caller: Caller,
    *,
    kind: ActivityKind | None = None,
    task_id: str | None = None,
    project: str | None = None,
    actor: str | None = None,
    since: str | None = None,
    until: str | None = None,
    order: ActivityOrder = ActivityOrder.NEWEST,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """`search_activity`'s own body (#302): callable directly, with any session and any `Caller`, with no protocol in between."""
    try:
        resolved_task_id = (
            resolve_task_id(session, caller, task_id) if task_id is not None else None
        )
        resolved_project_id = (
            resolve_project_id(session, caller, project)
            if project is not None
            else None
        )
        actor_bot_user_id, by_bots, by_user = (
            resolve_actor(session, caller, actor)
            if actor is not None
            else (None, False, False)
        )
        since_at = since_datetime(since) if since is not None else None
        until_at = until_datetime(until) if until is not None else None

        page = read_activity(
            session,
            caller,
            ActivityNarrowing(
                kind=kind,
                task_id=resolved_task_id,
                project_id=resolved_project_id,
                actor_bot_user_id=actor_bot_user_id,
                by_bots=by_bots,
                by_user=by_user,
                since=since_at,
                until=until_at,
                order=order,
                skip=offset,
                limit=limit,
            ),
        )
    except (HTTPException, Refusal) as exc:
        raise refusal(exc) from exc

    rows = _rows(session, page.entries)

    narrow_with = narrow_hint(
        ("kind", kind is not None),
        ("task_id or project", task_id is not None or project is not None),
        ("actor", actor is not None),
        ("since or until", since is not None or until is not None),
    )
    return list_result(
        rows, key="entries", count=page.total, offset=offset, narrow_with=narrow_with
    )


# Rows: one compact line per entry


def _rows(session: Session, entries: Sequence[ActivityEntry]) -> list[dict[str, Any]]:
    bot_ids = {entry.actor_bot_user_id for entry in entries if entry.actor_bot_user_id}
    bots = crud.get_bot_user_refs(session=session, bot_user_ids=bot_ids)
    return [
        {
            "at": entry.created_at.isoformat() if entry.created_at else None,
            "actor": _actor_label(entry, bots),
            "what": _describe(entry),
            "subject": _subject(entry),
        }
        for entry in entries
    ]


def _actor_label(entry: ActivityEntry, bots: dict[uuid.UUID, BotUserRef]) -> str:
    """Who acted: `actor_label`'s own convention, once this entry's actor is read down to a bot or the owner."""
    if entry.actor_id is not None:
        return actor_label(None)
    assert entry.actor_bot_user_id is not None
    bot = bots.get(entry.actor_bot_user_id)
    assert bot is not None, "a bot user is kept, not removed, once it acted (FR-08.19)"
    return actor_label(bot)


# Subjects: the task, project, tag, or batch an entry is about


def _subject(entry: ActivityEntry) -> dict[str, Any]:
    decoded = activity_details.decode(entry.action, entry.details)
    entity_type = entry.entity_type

    if isinstance(
        decoded, (TaskDeletedBatch, TaskRestoredBatch, TasksBulkChangedDetails)
    ):
        # A batch deletion or restore (`TaskDeletedBatch`/`TaskRestoredBatch`)
        # names no task ids, only a count; a bulk status change
        # (`TasksBulkChangedDetails`) names them in `task_ids`. Either way
        # the subject is the selection, not any one task it happened to be
        # filed under (`app.activity_log._on_task`'s own reason) — the three
        # shapes a batch can take, declared rather than read off which
        # fields happen to be there (ADR-0011's all-or-nothing batch).
        subject: dict[str, Any] = {"type": "tasks", "count": decoded.task_count}
        if isinstance(decoded, TasksBulkChangedDetails):
            subject["ids"] = [short_id(uuid.UUID(i)) for i in decoded.task_ids]
        return subject

    if entity_type in ("comment", "attachment"):
        assert isinstance(decoded, _ON_A_TASK)
        return {
            "type": "task",
            "id": short_id(decoded.task.id),
            "title": decoded.task.title or "Untitled task",
        }
    if entity_type == "project":
        assert isinstance(decoded, _PROJECT_NAMED)
        return {
            "type": "project",
            "id": str(entry.entity_id),
            "name": decoded.name or "Untitled project",
        }
    if entity_type == "tag":
        assert isinstance(decoded, _TAG_NAMED)
        return {
            "type": "tag",
            "id": str(entry.entity_id),
            "name": decoded.name or "Untitled tag",
        }
    assert isinstance(decoded, _TASK_TITLED)
    return {
        "type": "task",
        "id": short_id(entry.entity_id),
        "title": decoded.title or "Untitled task",
    }


# What happened: one short phrase per action, ported from the web UI's own
# `ActivityDescription.tsx` — there is no backend description of an entry
# yet, and this tool is the first thing besides that page that needs one.


def _describe(entry: ActivityEntry) -> str:  # noqa: PLR0911
    decoded = activity_details.decode(entry.action, entry.details)

    if isinstance(decoded, TaskCreatedDetails):
        project = decoded.task.project
        return "Created" + (f" in {project.name}" if project is not None else "")
    if isinstance(decoded, TaskChangedDetails):
        fields = ", ".join(_FIELD_LABELS.get(name, name) for name in decoded.changes)
        return f"Changed {fields}" if fields else "Changed"
    if isinstance(decoded, TaskCompletedDetails):
        return "Completed"
    if isinstance(decoded, TaskReopenedDetails):
        return "Reopened"
    if isinstance(decoded, TaskStatusChangedDetails):
        to = decoded.to
        return f"Moved to {_STATUS_LABELS.get(to, to)}"
    if isinstance(decoded, TaskDeletedSingle):
        return _with_count("Deleted", decoded.subtask_count, "subtask")
    if isinstance(decoded, TaskDeletedBatch):
        return "Deleted"  # the count is in the subject, not here
    if isinstance(decoded, TaskRestoredSingle):
        return _with_count("Restored", decoded.subtask_count, "subtask")
    if isinstance(decoded, TaskRestoredBatch):
        return "Restored"
    if isinstance(decoded, TaskMovedDetails):
        from_name = decoded.from_project.name if decoded.from_project else "no project"
        to_name = decoded.to_project.name if decoded.to_project else "no project"
        return f"Moved from {from_name} to {to_name}"
    if isinstance(decoded, TaskAssignedDetails):
        return f"Assigned to {_assignee_label(decoded.assignee)}"
    if isinstance(decoded, TaskUnassignedDetails):
        # Named only for a bot user, the same asymmetry
        # `ActivityDescription.tsx`'s own `task_unassigned` case has: the
        # owner is always "you" to themselves, so naming a previous human
        # assignee says nothing a reader does not already know.
        previous = decoded.previous_assignee
        if previous is not None and previous.type == "bot_user":
            return f"Unassigned (was {_assignee_label(previous)})"
        return "Unassigned"
    if isinstance(decoded, TasksBulkChangedDetails):
        count = decoded.task_count
        said = _describe_batch_changes(decoded.changes)
        base = f"Changed {count} task{'' if count == 1 else 's'}"
        return f"{base}: {said}" if said else base
    if isinstance(decoded, ProjectCreatedDetails):
        return "Created"
    if isinstance(decoded, ProjectChangedDetails):
        fields = ", ".join(decoded.changes)
        return f"Changed {fields}" if fields else "Changed"
    if isinstance(decoded, ProjectDeletedDetails):
        return _with_count("Deleted", decoded.task_count, "task")
    if isinstance(decoded, ProjectRestoredDetails):
        return _with_count("Restored", decoded.task_count, "task")
    if isinstance(decoded, CommentAddedDetails):
        return "Commented"
    if isinstance(decoded, CommentEditedDetails):
        return "Edited a comment"
    if isinstance(decoded, CommentDeletedDetails):
        return "Deleted a comment"
    if isinstance(decoded, AttachmentAddedDetails):
        return f"Attached “{decoded.filename}”"
    if isinstance(decoded, AttachmentDeletedDetails):
        return f"Removed “{decoded.filename}”"
    if isinstance(decoded, TagCreatedDetails):
        return "Created"
    if isinstance(decoded, TagRenamedDetails):
        old = decoded.changes["name"].from_
        return f"Renamed from “{old}”" if old else "Renamed"
    if isinstance(decoded, TagMergedDetails):
        said = (
            "Merged " + ", ".join(f"“{name}”" for name in decoded.sources) + " into it"
        )
        tasks = decoded.task_count
        if tasks:
            said += f", moving {tasks} task{'' if tasks == 1 else 's'} onto it"
        return said
    if isinstance(decoded, TagDeletedDetails):
        tasks = decoded.task_count
        if tasks:
            return f"Deleted, removed from {tasks} task{'' if tasks == 1 else 's'}"
        return "Deleted"
    return str(entry.action)


def _with_count(verb: str, count: int | None, noun: str) -> str:
    if not count:
        return verb
    return f"{verb} with {count} {noun}{'' if count == 1 else 's'}"


def _assignee_label(assignee: AssigneeRef | None) -> str:
    if assignee is None:
        return "nobody"
    if assignee.type == "bot_user":
        return f"the bot user {assignee.name}"
    return "owner"


def _describe_batch_changes(changes: dict[str, Any]) -> str:
    """What a batch did, in the words `ActivityDescription.tsx`'s own `describeBatch` uses."""
    said = []
    if "status" in changes:
        status = changes["status"]
        said.append(
            "completed"
            if status == TaskStatus.DONE
            else f"moved to {_STATUS_LABELS.get(status, status)}"
        )
    if "priority" in changes:
        priority = changes["priority"]
        said.append(f"priority {priority}" if priority else "priority cleared")
    if "due_date" in changes:
        due_date = changes["due_date"]
        said.append(f"due {due_date}" if due_date else "due date cleared")
    project = changes.get("project")
    if project and project.get("name"):
        said.append(f"moved to {project['name']}")
    added = changes.get("added_tags")
    if added:
        said.append(f"tagged {', '.join(added)}")
    removed = changes.get("removed_tags")
    if removed:
        said.append(f"untagged {', '.join(removed)}")
    return ", ".join(said)
