"""
`list_completions` (spec #247, #248, #260): finished work as a table, in one
call — the answer "what did I finish last month?" needs and a task alone
cannot give, since a task records `created_at` and a current status, never
when it reached Done (ADR-0011, `docs/adr/0011-bot-users-read-the-activity-
log-in-scope.md`). The only record of that moment is the activity log: a
`task_completed` entry, or a batch entry naming `done` as the new status.

Built the way spec #248's own decision reads: the log's own narrowing —
`app.activity_log.read_activity` (#298), the same reader `search_activity`
(#259) and the REST route both call, composed with `kind=ActivityKind.
COMPLETED` — joined to the task read model (`app.models.Task`,
`app.crud.get_task_project_ids`/`get_task_tags`) — never a new REST
endpoint, and never a call per task. One query gathers every completion
entry the period and the narrowing match; one more reads the tasks they
name, batched by id rather than fetched one at a time.

Three things make the count here different from one built by reading the
log by hand, each worth saying plainly because each is the one place that
count would otherwise be silently wrong:

- **A batch is one entry, many rows.** Closing several tasks in one act
  (`POST /tasks/bulk`) writes a single `tasks_bulk_changed` entry naming the
  new status and every task it touched in `task_ids`
  (`app.activity._write`, the same entry `search_activity`'s own `kind`
  grouping already recognises as a completion). This tool expands it into
  one row per task it named, the one place a count built from entries alone
  would undercount (spec #248).
- **A reopened task closes twice.** Completing a task, reopening it, and
  completing it again writes two `task_completed` entries, and this tool
  answers with two rows — both real completions of the same task. The
  summary reports `completions` (every row here) and `distinct_tasks`
  (how many different tasks they are) side by side, so neither number is
  mistaken for the other.
- **A task deleted since keeps its row.** Its own completion entry already
  said it closed and when (`app.activity._task_entries`'s own
  `entry(ActivityAction.TASK_COMPLETED)` carries only the task's title at
  the time, nothing else); nothing else about it is read from the task
  afterwards, so the row carries that title (or, for a batch entry, which
  names no title at all, "Untitled task"), is marked `deleted`, and leaves
  its project, tags, priority and lead time out rather than guessing them
  from a row that may since have changed, moved, or come back restored. A
  report on a period a user has since tidied up must read the same either
  way.

Every other occurrence of a recurring task is simply its own task
(ADR-0001): each has its own id and its own `task_completed` entry, so each
is already its own row here without this tool doing anything further to
keep the series from collapsing.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Annotated, Any

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlmodel import Session, col, select

from app import crud
from app.activity_log import ActivityNarrowing, read_activity
from app.api import access
from app.api.deps import Caller
from app.mcp.conventions import (
    actor_label,
    list_result,
    narrow_hint,
    open_caller,
    refusal,
    resolve_actor,
    resolve_project_id,
    resolve_tag_name,
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
    Project,
    Task,
)


@dataclass(frozen=True)
class _Actor:
    actor_id: uuid.UUID | None
    actor_bot_user_id: uuid.UUID | None


@dataclass(frozen=True)
class _Completion:
    """One task reaching Done — one `task_completed` entry, or one task a batch named."""

    task_id: uuid.UUID
    closed_at: datetime
    actor: _Actor
    # What the completion entry itself recorded as the title, at the moment
    # it closed (`app.activity._task_entries`) — present for a single
    # completion, absent for a batch entry, which names no titles at all.
    title_recorded: str | None


@dataclass(frozen=True)
class _Enriched:
    """A completion, joined to what the task read model still says about it."""

    completion: _Completion
    deleted: bool
    title: str
    project: str | None
    project_id: uuid.UUID | None
    tags: list[str]
    priority: str | None
    filed_at: datetime | None
    days_to_close: float | None


@mcp_server.tool(
    annotations=ToolAnnotations(read_only_hint=True),
)
def list_completions(
    ctx: Context,
    since: str,
    until: str,
    project: str | None = None,
    actor: str | None = None,
    tag: str | None = None,
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    """
    Finished work over a closed period, as one table — what an agent reads
    to answer "what did I finish last month?" rather than paging the log and
    fetching every task it names by hand.

    `since` and `until` are both required — an ISO date, `today`,
    `tomorrow`, or `+<count>d`, read against the server's own date and
    widened to the whole day, so a period such as "last month" is named by
    its two calendar dates, `since` exclusive and `until` inclusive, rather
    than guessed at from one bound alone the way `search_activity`'s own
    (optional) dates allow.

    `project` and `tag` take a name, case-insensitively, as well as an id,
    the same way every other tool here does; a project outside this bot
    user's scope, or simply not there, is refused the way the API refuses
    it. `actor` reads `self`, `owner`, `any_bot`, or a bot user by name or
    id, refused by name if none matches. Narrowing by `project` or `tag`
    only ever drops a row: a deleted task's completion carries neither (see
    below), so it never matches either filter, whatever it would have
    matched on before it was deleted.

    Each row is one completion — a task reaching Done, once: `id`, `title`,
    `project`, `tags`, `priority`, `filed` (when the task was created),
    `closed` (when this completion happened), `days_to_close` (the time
    between, in days), and `closed_by` ("owner", or a bot user by name, the
    convention `get_task`'s own comment rows use). A row for a task since
    deleted carries `deleted: true`, the title its completion entry
    recorded (or "Untitled task" for one named only by a batch), and nulls
    everywhere else — never a current field a deletion since made stale,
    and never a guess at how long it took to close.

    The `summary` alongside the rows always covers every completion the
    filters matched, not only the page `limit` returns: `completions` (the
    total — closing a task twice counts twice) and `distinct_tasks` (how
    many different tasks they are, smaller whenever one was reopened and
    closed again) side by side, `by_project` and `by_actor` (each a count
    per name, summing back to `completions`), and `median_days_to_close`
    (over the rows whose lead time is known, null if none is). `count` is
    `completions` again, read the way every list here reports its total; a
    `truncated` answer names one filter (`narrow_with`) still free to
    narrow with — never a partial count mistaken for the whole.

    Refused by name without `read_activity` (FR-08.9), the same grant
    `search_activity` needs; nothing outside this bot user's scope is ever
    counted (ADR-0011).
    """
    with open_caller(ctx) as (session, caller):
        try:
            access.authorize_activity_log(caller)
            project_id = (
                _resolve_narrowing_project_id(session, caller, project)
                if project is not None
                else None
            )
            actor_bot_user_id, by_bots, by_user = (
                resolve_actor(session, caller, actor)
                if actor is not None
                else (None, False, False)
            )
            tag_name = (
                resolve_tag_name(session, caller.owner_id, tag)
                if tag is not None
                else None
            )
            since_at = since_datetime(since)
            until_at = until_datetime(until)
        except HTTPException as exc:
            raise refusal(exc) from exc

        entries = _completion_entries(
            session,
            caller,
            actor_bot_user_id=actor_bot_user_id,
            by_bots=by_bots,
            by_user=by_user,
            since_at=since_at,
            until_at=until_at,
        )
        completions = [c for entry in entries for c in _expand(entry)]
        enriched, bots = _enrich(session, caller, completions)

        if project_id is not None:
            enriched = [e for e in enriched if e.project_id == project_id]
        if tag_name is not None:
            enriched = [e for e in enriched if tag_name in e.tags]

        summary = _summary(enriched, bots)

    enriched.sort(key=lambda e: e.completion.closed_at, reverse=True)
    rows = [_row(e, bots) for e in enriched[:limit]]

    narrow_with = narrow_hint(
        ("project", project is not None),
        ("actor", actor is not None),
        ("tag", tag is not None),
    )
    result = list_result(
        rows, key="completions", count=len(enriched), narrow_with=narrow_with
    )
    result["summary"] = summary
    return result


def _resolve_narrowing_project_id(
    session: Session, caller: Caller, raw: str
) -> uuid.UUID:
    """
    Which project `project` narrows to, refused the way narrowing the
    activity log itself is refused (`app.activity_log.read_activity`'s own
    `project_id` handling, which this mirrors rather than
    `app.api.access.get_project`'s): a 404 for either a project that is not
    there or one outside this bot user's scope, the same answer for both,
    since a scope refusal here would otherwise confirm an id the caller has
    no business learning is real.
    """
    project_id = resolve_project_id(session, caller, raw)
    project = session.get(Project, project_id)
    if (
        project is None
        or project.owner_id != caller.owner_id
        or not access.bot_reaches_project(caller, project)
    ):
        raise HTTPException(status_code=404, detail="Project not found")
    return project_id


# Gathering: one query over the period, completions only


def _completion_entries(
    session: Session,
    caller: Caller,
    *,
    actor_bot_user_id: uuid.UUID | None,
    by_bots: bool,
    by_user: bool,
    since_at: datetime,
    until_at: datetime,
) -> Sequence[ActivityEntry]:
    """
    Every entry this period and this narrowing match that is a completion —
    a `task_completed` entry, or a batch entry that moved its tasks to Done
    — read through the shared reader (`app.activity_log.read_activity`,
    #298) with `kind=ActivityKind.COMPLETED`, the exact grouping
    `search_activity`'s own `kind="completed"` uses, composed here rather
    than re-derived: the reader already applies the scope and the actor
    narrowing the same way for every caller.

    `limit=None` asks for every match in the period rather than a page: the
    summary below has to total every completion, not only the page this
    tool's own `limit` (applied to the rendered rows afterwards) would
    return. `order=OLDEST` keeps the entries in the order this function has
    always read them in, so a tie at the final truncation below breaks the
    same way it always has.

    `project` and `tag` are not applied here at all, because a batch
    entry's `task_ids` can span more than one project and this tool's own
    project/tag narrowing is a per-task question, answered once the tasks
    are read back (`_enrich`), not a per-entry one.
    """
    page = read_activity(
        session,
        caller,
        ActivityNarrowing(
            kind=ActivityKind.COMPLETED,
            actor_bot_user_id=actor_bot_user_id,
            by_bots=by_bots,
            by_user=by_user,
            since=since_at,
            until=until_at,
            order=ActivityOrder.OLDEST,
            limit=None,
        ),
    )
    return page.entries


def _expand(entry: ActivityEntry) -> list[_Completion]:
    """
    One entry as the completions it actually records: one, for a plain
    `task_completed` entry, or one per task named in a batch's `task_ids`
    (`app.activity._write`) — the expansion this tool exists for (spec
    #248).
    """
    actor = _Actor(actor_id=entry.actor_id, actor_bot_user_id=entry.actor_bot_user_id)
    assert entry.created_at is not None
    if entry.action == ActivityAction.TASK_COMPLETED:
        return [
            _Completion(
                task_id=entry.entity_id,
                closed_at=entry.created_at,
                actor=actor,
                title_recorded=entry.details.get("title"),
            )
        ]
    task_ids = entry.details.get("task_ids") or []
    return [
        _Completion(
            task_id=uuid.UUID(task_id),
            closed_at=entry.created_at,
            actor=actor,
            title_recorded=None,
        )
        for task_id in task_ids
    ]


# Enrichment: the tasks the completions name, read back in one more query


def _enrich(
    session: Session, caller: Caller, completions: list[_Completion]
) -> tuple[list[_Enriched], dict[uuid.UUID, BotUserRef]]:
    """
    Each completion joined to its task — one query for the tasks, whatever
    their number, never one call per row — and to who closed it. A task no
    longer live (`task.deletion_id` set, or gone outright) contributes
    nothing current: its row carries only what the completion entry itself
    recorded (spec #248's own deleted-task rule).
    """
    task_ids = list({c.task_id for c in completions})
    tasks = (
        {
            task.id: task
            for task in session.exec(
                select(Task).where(col(Task.id).in_(task_ids))
            ).all()
        }
        if task_ids
        else {}
    )
    live_ids = [
        task_id
        for task_id in task_ids
        if (task := tasks.get(task_id)) is not None and task.deletion_id is None
    ]
    project_ids = crud.get_task_project_ids(
        session=session, owner_id=caller.owner_id, task_ids=live_ids
    )
    projects = (
        {
            proj.id: proj.name
            for proj in session.exec(
                select(Project).where(col(Project.id).in_(set(project_ids.values())))
            ).all()
        }
        if project_ids
        else {}
    )
    tags = crud.get_task_tags(session=session, task_ids=live_ids)
    bot_ids = {
        c.actor.actor_bot_user_id
        for c in completions
        if c.actor.actor_bot_user_id is not None
    }
    bots = crud.get_bot_user_refs(session=session, bot_user_ids=bot_ids)

    return [
        _one(c, tasks.get(c.task_id), project_ids, projects, tags) for c in completions
    ], bots


def _one(
    completion: _Completion,
    task: Task | None,
    project_ids: dict[uuid.UUID, uuid.UUID],
    projects: dict[uuid.UUID, str],
    tags: dict[uuid.UUID, list[str]],
) -> _Enriched:
    deleted = task is None or task.deletion_id is not None
    if deleted or task is None:
        return _Enriched(
            completion=completion,
            deleted=True,
            title=completion.title_recorded or "Untitled task",
            project=None,
            project_id=None,
            tags=[],
            priority=None,
            filed_at=None,
            days_to_close=None,
        )
    project_id = project_ids.get(task.id)
    filed_at = task.created_at
    return _Enriched(
        completion=completion,
        deleted=False,
        title=task.title,
        project=projects.get(project_id) if project_id is not None else None,
        project_id=project_id,
        tags=tags.get(task.id, []),
        priority=task.priority.value if task.priority is not None else None,
        filed_at=filed_at,
        days_to_close=_days_between(filed_at, completion.closed_at)
        if filed_at is not None
        else None,
    )


def _days_between(filed_at: datetime, closed_at: datetime) -> float:
    return round((closed_at - filed_at).total_seconds() / 86400, 2)


# Rendering: one row per completion, the summary over every one of them


def _row(enriched: _Enriched, bots: dict[uuid.UUID, BotUserRef]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": short_id(enriched.completion.task_id),
        "title": enriched.title,
        "project": enriched.project,
        "tags": enriched.tags,
        "priority": enriched.priority,
        "filed": enriched.filed_at.isoformat()
        if enriched.filed_at is not None
        else None,
        "closed": enriched.completion.closed_at.isoformat(),
        "days_to_close": enriched.days_to_close,
        "closed_by": _actor_label(enriched.completion.actor, bots),
    }
    if enriched.deleted:
        row["deleted"] = True
    return row


def _actor_label(actor: _Actor, bots: dict[uuid.UUID, BotUserRef]) -> str:
    """Who closed it: `actor_label`'s own convention, once this completion's actor is read down to a bot or the owner."""
    if actor.actor_id is not None:
        return actor_label(None)
    assert actor.actor_bot_user_id is not None
    bot = bots.get(actor.actor_bot_user_id)
    assert bot is not None, "a bot user is kept, not removed, once it acted (FR-08.19)"
    return actor_label(bot)


def _summary(
    enriched: list[_Enriched], bots: dict[uuid.UUID, BotUserRef]
) -> dict[str, Any]:
    """
    The totals over every matched completion, not only the rows `limit`
    returns: the count and the distinct-task count side by side (spec
    #248's own reopened-task rule), the splits by project and by actor
    (each summing back to the count), and the median lead time over the
    rows that have one.
    """
    by_project: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    days: list[float] = []
    for e in enriched:
        project_key = e.project if e.project is not None else "(deleted)"
        by_project[project_key] = by_project.get(project_key, 0) + 1
        actor_key = _actor_label(e.completion.actor, bots)
        by_actor[actor_key] = by_actor.get(actor_key, 0) + 1
        if e.days_to_close is not None:
            days.append(e.days_to_close)
    return {
        "completions": len(enriched),
        "distinct_tasks": len({e.completion.task_id for e in enriched}),
        "by_project": by_project,
        "by_actor": by_actor,
        "median_days_to_close": round(median(days), 2) if days else None,
    }
