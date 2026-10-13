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
("owner", or a bot user by name, the same convention `get_task`'s comment
rows use), saying what happened in one short phrase, and naming the task,
project or tag (or, for a batch, the selection) the entry is about — ported
from the web UI's own `ActivityDescription.tsx`, since there is no backend
description of an entry yet and this tool is the first thing besides a human
reading the page that needs one.

`actor` and the `since`/`until` widening are read through
`app.mcp.conventions.resolve_actor`/`since_datetime`/`until_datetime`:
settled here first, then moved there once `list_completions` (#260) needed
the exact same reading of a period and of who acted, rather than its own
copy of either.
"""

import uuid
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlmodel import Session

from app import crud
from app.activity_log import ActivityNarrowing, read_activity
from app.mcp.conventions import (
    list_result,
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
    ActivityAction,
    ActivityEntry,
    ActivityKind,
    ActivityOrder,
    BotUserRef,
    TaskStatus,
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
        try:
            resolved_task_id = (
                resolve_task_id(session, caller, task_id)
                if task_id is not None
                else None
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
        except HTTPException as exc:
            raise refusal(exc) from exc

        rows = _rows(session, page.entries)

    narrow_with = _narrow_hint(
        kind=kind,
        task_id=task_id,
        project=project,
        actor=actor,
        since=since,
        until=until,
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
    """
    Who acted, the same convention `get_task`'s own comment rows use: "owner"
    for the human, or a bot user by the name the entry itself carries
    (present whatever its scope, FR-08.19), "(deleted)" appended if it no
    longer exists.
    """
    if entry.actor_id is not None:
        return "owner"
    assert entry.actor_bot_user_id is not None
    bot = bots.get(entry.actor_bot_user_id)
    assert bot is not None, "a bot user is kept, not removed, once it acted (FR-08.19)"
    return f"{bot.name} (deleted)" if bot.deleted else bot.name


# Subjects: the task, project, tag, or batch an entry is about


def _subject(entry: ActivityEntry) -> dict[str, Any]:
    details = entry.details
    entity_type = entry.entity_type

    if entry.action == ActivityAction.TASKS_BULK_CHANGED or (
        "task_count" in details and "title" not in details
    ):
        # A batch deletion or restore (`app.activity._deletion_entry`,
        # `_restore_entry`) names no task ids, only a count; a bulk status
        # change (`app.activity._write`) names them in `task_ids`. Either
        # way the subject is the selection, not any one task it happened to
        # be filed under (`app.activity_log._on_task`'s own reason).
        subject: dict[str, Any] = {"type": "tasks", "count": details["task_count"]}
        if "task_ids" in details:
            subject["ids"] = [short_id(uuid.UUID(i)) for i in details["task_ids"]]
        return subject

    if entity_type in ("comment", "attachment"):
        task = details.get("task") or {}
        task_id = uuid.UUID(task["id"]) if "id" in task else entry.entity_id
        return {
            "type": "task",
            "id": short_id(task_id),
            "title": task.get("title") or "Untitled task",
        }
    if entity_type == "project":
        return {
            "type": "project",
            "id": str(entry.entity_id),
            "name": details.get("name") or "Untitled project",
        }
    if entity_type == "tag":
        return {
            "type": "tag",
            "id": str(entry.entity_id),
            "name": details.get("name") or "Untitled tag",
        }
    return {
        "type": "task",
        "id": short_id(entry.entity_id),
        "title": details.get("title") or "Untitled task",
    }


# What happened: one short phrase per action, ported from the web UI's own
# `ActivityDescription.tsx` — there is no backend description of an entry
# yet, and this tool is the first thing besides that page that needs one.


def _describe(entry: ActivityEntry) -> str:
    action = entry.action
    details: Any = entry.details

    if action == ActivityAction.TASK_CREATED:
        task = details.get("task") or {}
        project = task.get("project")
        return "Created" + (f" in {project['name']}" if project else "")
    if action == ActivityAction.TASK_CHANGED:
        fields = ", ".join(
            _FIELD_LABELS.get(name, name) for name in details.get("changes", {})
        )
        return f"Changed {fields}" if fields else "Changed"
    if action == ActivityAction.TASK_COMPLETED:
        return "Completed"
    if action == ActivityAction.TASK_REOPENED:
        return "Reopened"
    if action == ActivityAction.TASK_STATUS_CHANGED:
        to = details.get("to")
        return f"Moved to {_STATUS_LABELS.get(to, to)}"
    if action == ActivityAction.TASK_DELETED:
        if "task_count" in details:
            return "Deleted"  # the count is in the subject, not here
        return _with_count("Deleted", details.get("subtask_count"), "subtask")
    if action == ActivityAction.TASK_RESTORED:
        if "task_count" in details and "title" not in details:
            return "Restored"
        return _with_count("Restored", details.get("subtask_count"), "subtask")
    if action == ActivityAction.TASK_MOVED:
        from_name = (details.get("from_project") or {}).get("name", "no project")
        to_name = (details.get("to_project") or {}).get("name", "no project")
        return f"Moved from {from_name} to {to_name}"
    if action == ActivityAction.TASK_ASSIGNED:
        return f"Assigned to {_assignee_label(details.get('assignee'))}"
    if action == ActivityAction.TASK_UNASSIGNED:
        # Named only for a bot user, the same asymmetry
        # `ActivityDescription.tsx`'s own `task_unassigned` case has: the
        # owner is always "you" to themselves, so naming a previous human
        # assignee says nothing a reader does not already know.
        previous = details.get("previous_assignee")
        if previous and previous.get("type") == "bot_user":
            return f"Unassigned (was {_assignee_label(previous)})"
        return "Unassigned"
    if action == ActivityAction.TASKS_BULK_CHANGED:
        count = details.get("task_count") or 0
        said = _describe_batch_changes(details.get("changes") or {})
        base = f"Changed {count} task{'' if count == 1 else 's'}"
        return f"{base}: {said}" if said else base
    if action == ActivityAction.PROJECT_CREATED:
        return "Created"
    if action == ActivityAction.PROJECT_CHANGED:
        fields = ", ".join(details.get("changes", {}))
        return f"Changed {fields}" if fields else "Changed"
    if action == ActivityAction.PROJECT_DELETED:
        return _with_count("Deleted", details.get("task_count"), "task")
    if action == ActivityAction.PROJECT_RESTORED:
        return _with_count("Restored", details.get("task_count"), "task")
    if action == ActivityAction.COMMENT_ADDED:
        return "Commented"
    if action == ActivityAction.COMMENT_EDITED:
        return "Edited a comment"
    if action == ActivityAction.COMMENT_DELETED:
        return "Deleted a comment"
    if action == ActivityAction.ATTACHMENT_ADDED:
        return f"Attached “{details.get('filename', 'a file')}”"
    if action == ActivityAction.ATTACHMENT_DELETED:
        return f"Removed “{details.get('filename', 'a file')}”"
    if action == ActivityAction.TAG_CREATED:
        return "Created"
    if action == ActivityAction.TAG_RENAMED:
        old = (details.get("changes", {}).get("name") or {}).get("from")
        return f"Renamed from “{old}”" if old else "Renamed"
    if action == ActivityAction.TAG_MERGED:
        sources = details.get("sources") or []
        said = "Merged " + ", ".join(f"“{name}”" for name in sources) + " into it"
        tasks = details.get("task_count") or 0
        if tasks:
            said += f", moving {tasks} task{'' if tasks == 1 else 's'} onto it"
        return said
    if action == ActivityAction.TAG_DELETED:
        tasks = details.get("task_count") or 0
        if tasks:
            return f"Deleted, removed from {tasks} task{'' if tasks == 1 else 's'}"
        return "Deleted"
    return str(action)


def _with_count(verb: str, count: int | None, noun: str) -> str:
    if not count:
        return verb
    return f"{verb} with {count} {noun}{'' if count == 1 else 's'}"


def _assignee_label(assignee: dict[str, Any] | None) -> str:
    if assignee is None:
        return "nobody"
    if assignee.get("type") == "bot_user":
        return f"the bot user {assignee.get('name')}"
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


# The narrow hint


def _narrow_hint(
    *,
    kind: ActivityKind | None,
    task_id: str | None,
    project: str | None,
    actor: str | None,
    since: str | None,
    until: str | None,
) -> str | None:
    """
    The one filter, among those not already set, most likely to turn a
    truncated answer into a complete one — named, not applied, the same
    convention `search_tasks`'s own `_narrow_hint` follows.
    """
    if kind is None:
        return "kind"
    if task_id is None and project is None:
        return "task_id or project"
    if actor is None:
        return "actor"
    if since is None and until is None:
        return "since or until"
    return None
