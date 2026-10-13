"""
The activity log's reader (#298): one query that the REST route and both MCP
tools (`search_activity`, `list_completions`) build a page of the log from,
so the narrowing rules write once rather than being re-derived by each
caller.

`read_activity` takes the narrowing as one value object, `ActivityNarrowing`
— kind, task, project, actor, period, order and page — and returns the
matched entries, their total, and where each entry's entity can still be
opened (`ActivityPage.locations`). The permission check (`read_activity`,
FR-08.9), the task/project narrowing refusals, the scope condition
(`app.access.activity_log_scope`), the all-or-nothing batch rule and the
kind grouping all live here once; a caller learns one argument object and
one return shape, not a dozen keyword arguments kept in step by hand.

What the reader does not do: build the public response shape (that is a
REST concern — a human's and a bot user's projections differ, ADR-0011 —
and stays with the route) or compute restorability (also human-only, and
cheap enough that the route computes it itself over the rows this module
hands back).

Below `app.api` (`tests/migrations/test_layering.py`): imports only from
`app.access`, `app.caller`, `app.crud` and `app.models`, none of them above
this line, so both front doors — the REST route and the MCP tools — reach
down into this module rather than into each other.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Text, and_, cast, literal_column, not_, or_
from sqlmodel import Session, col, func, select

from app import access, crud
from app.caller import Caller
from app.models import (
    ACTIVITY_TASK_REF,
    ActivityAction,
    ActivityEntityType,
    ActivityEntry,
    ActivityKind,
    ActivityOrder,
    Attachment,
    Comment,
    Project,
    Tag,
    Task,
    TaskStatus,
)

# A batch that moved its tasks to done. It is logged as the one act it was —
# a single entry naming the new status, not a completion per task — so the
# only way to recognise it as finished work is to read what the batch did.
#
# `IS NOT DISTINCT FROM` rather than `=`: a batch that changed something else
# records no status at all, and comparing that missing key to a string yields
# NULL rather than false. Under plain `=`, negating this to find the changes
# would drop every such batch instead of keeping it.
_BULK_COMPLETION = and_(
    col(ActivityEntry.action) == ActivityAction.TASKS_BULK_CHANGED,
    col(ActivityEntry.details)["changes"]["status"].astext.is_not_distinct_from(
        TaskStatus.DONE.value
    ),
)

# Which actions each kind gathers. Every action belongs to exactly one kind:
# `tests/api/routes/test_activity_by_kind.py` holds the list to that, so a
# new kind of entry cannot quietly become unreachable from the filter.
_KIND_ACTIONS: dict[ActivityKind, tuple[ActivityAction, ...]] = {
    ActivityKind.COMPLETED: (ActivityAction.TASK_COMPLETED,),
    ActivityKind.CREATED: (
        ActivityAction.TASK_CREATED,
        ActivityAction.PROJECT_CREATED,
    ),
    ActivityKind.CHANGED: (
        ActivityAction.TASK_CHANGED,
        ActivityAction.TASKS_BULK_CHANGED,
        ActivityAction.TASK_REOPENED,
        ActivityAction.TASK_STATUS_CHANGED,
        ActivityAction.TASK_MOVED,
        ActivityAction.TASK_ASSIGNED,
        ActivityAction.TASK_UNASSIGNED,
        ActivityAction.PROJECT_CHANGED,
    ),
    ActivityKind.DELETED: (
        ActivityAction.TASK_DELETED,
        ActivityAction.TASK_RESTORED,
        ActivityAction.PROJECT_DELETED,
        ActivityAction.PROJECT_RESTORED,
    ),
    ActivityKind.COMMENTS: (
        ActivityAction.COMMENT_ADDED,
        ActivityAction.COMMENT_EDITED,
        ActivityAction.COMMENT_DELETED,
        ActivityAction.ATTACHMENT_ADDED,
        ActivityAction.ATTACHMENT_DELETED,
    ),
    ActivityKind.TAGS: (
        ActivityAction.TAG_CREATED,
        ActivityAction.TAG_RENAMED,
        ActivityAction.TAG_DELETED,
        ActivityAction.TAG_MERGED,
    ),
}


def of_kind(kind: ActivityKind) -> Any:
    """
    What an entry has to satisfy to belong to `kind`.

    Completing a batch is the one change that two kinds could both claim, so
    the two say the same thing from opposite sides: it is a completion, and
    for that reason not one of the changes. Public (#298): `list_completions`
    composes this with the reader's own narrowing to gather completions,
    rather than copying `ActivityKind.COMPLETED`'s own condition by hand.
    """
    actions = col(ActivityEntry.action).in_(_KIND_ACTIONS[kind])
    if kind is ActivityKind.COMPLETED:
        return actions | _BULK_COMPLETION
    if kind is ActivityKind.CHANGED:
        return and_(actions, not_(_BULK_COMPLETION))
    return actions


def _on_task(task_id: uuid.UUID) -> Any:
    """
    What an entry has to satisfy to belong to the history of one task: it is
    about the task itself, about a comment or file on it, or it is a batch
    that touched it. A batch is one entry, filed under the first task it
    touched, and names the rest in `task_ids`.
    """
    return or_(
        col(ActivityEntry.entity_id) == task_id,
        literal_column(ACTIVITY_TASK_REF) == str(task_id),
        and_(
            col(ActivityEntry.action) == ActivityAction.TASKS_BULK_CHANGED,
            col(ActivityEntry.details).contains({"task_ids": [str(task_id)]}),
        ),
    )


def _in_project(project_id: uuid.UUID) -> Any:
    """
    What an entry has to satisfy to belong to a project's chronology: it is
    about the project itself, about a task in it, about a comment or file on
    such a task, or it records a task's deletion or restore. Those carry the
    project the task was in, because the project no longer lists a deleted
    task to find it by.
    """
    tasks = crud.project_task_ids(project_id).subquery()
    return or_(
        and_(
            col(ActivityEntry.entity_type) == ActivityEntityType.PROJECT,
            col(ActivityEntry.entity_id) == project_id,
        ),
        col(ActivityEntry.entity_id).in_(select(tasks.c.id)),
        literal_column(ACTIVITY_TASK_REF).in_(select(cast(tasks.c.id, Text))),
        col(ActivityEntry.details).contains({"project": {"id": str(project_id)}}),
    )


@dataclass(frozen=True)
class ActivityNarrowing:
    """
    One read's worth of narrowing over the log — kind, task, project, actor,
    period, order and page — exactly what `read_activity` takes, so a test
    can build one directly and a caller composes it without copying the
    query it drives (#298).

    `limit=None` asks for every match rather than a page: `list_completions`
    needs every completion in its period to total correctly (a page would
    undercount), while the REST route and `search_activity` always pass a
    limit of their own.
    """

    kind: ActivityKind | None = None
    task_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    actor_bot_user_id: uuid.UUID | None = None
    by_bots: bool = False
    by_user: bool = False
    since: datetime | None = None
    until: datetime | None = None
    order: ActivityOrder = ActivityOrder.NEWEST
    skip: int = 0
    limit: int | None = 50


@dataclass(frozen=True)
class ActivityPage:
    """
    The reader's answer: the matched entries (one page of them, newest or
    oldest first per the narrowing's own `order`), their total count, and
    where each entry's entity can still be opened (`locations`, keyed by
    entity id — `None` for a tag, absent for an entity that is gone or hangs
    off a task that is).
    """

    entries: Sequence[ActivityEntry]
    total: int
    locations: dict[uuid.UUID, uuid.UUID | None]


def read_activity(
    session: Session, caller: Caller, narrowing: ActivityNarrowing
) -> ActivityPage:
    """
    One page of the caller's activity log, narrowed as `narrowing` says
    (#298). Shared by `GET /activity-log/`, `search_activity` and
    `list_completions`, so the scope narrowing (ADR-0011), the all-or-
    nothing batch rule, the tag exemption, and the task/project refusals
    write once.

    The permission check (`read_activity`, FR-08.9) happens here, first, the
    same order every other narrowing already checks in — a bot without the
    grant is refused by name whatever the rest of `narrowing` asks for.

    `narrowing.task_id`/`project_id` each 404 the same way for a task or
    project that is missing, not the caller's, or (for a bot) outside its
    reach — never a 403 that would confirm the id is real, and never an
    empty feed that would look like a history with nothing in it (ADR-0011's
    own Consequence).
    """
    access.authorize_activity_log(caller)

    where: list[Any] = [ActivityEntry.owner_id == caller.owner_id]
    if narrowing.task_id is not None:
        task = session.get(Task, narrowing.task_id)
        if (
            not task
            or task.owner_id != caller.owner_id
            or not access.bot_reaches_task(session, caller, narrowing.task_id)
        ):
            raise HTTPException(status_code=404, detail="Task not found")
        where.append(_on_task(narrowing.task_id))
    if narrowing.project_id is not None:
        project = session.get(Project, narrowing.project_id)
        if (
            not project
            or project.owner_id != caller.owner_id
            or not access.bot_reaches_project(caller, project)
        ):
            raise HTTPException(status_code=404, detail="Project not found")
        where.append(_in_project(narrowing.project_id))
    if (scope := access.activity_log_scope(caller)) is not None:
        where.append(scope)
    if narrowing.actor_bot_user_id is not None:
        where.append(ActivityEntry.actor_bot_user_id == narrowing.actor_bot_user_id)
    if narrowing.kind is not None:
        where.append(of_kind(narrowing.kind))
    if narrowing.by_bots:
        where.append(col(ActivityEntry.actor_bot_user_id).is_not(None))
    if narrowing.by_user:
        where.append(col(ActivityEntry.actor_bot_user_id).is_(None))
    since = narrowing.since
    if since is not None:
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        where.append(col(ActivityEntry.created_at) > since)
    until = narrowing.until
    if until is not None:
        if until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
        where.append(col(ActivityEntry.created_at) <= until)

    total = session.exec(
        select(func.count()).select_from(ActivityEntry).where(*where)
    ).one()
    statement = (
        select(ActivityEntry)
        .where(*where)
        .order_by(
            col(ActivityEntry.position).asc()
            if narrowing.order is ActivityOrder.OLDEST
            else col(ActivityEntry.position).desc()
        )
        .offset(narrowing.skip)
    )
    if narrowing.limit is not None:
        statement = statement.limit(narrowing.limit)
    entries = session.exec(statement).all()

    locations = _locate(session, caller.owner_id, entries)
    return ActivityPage(entries=entries, total=total, locations=locations)


def _locate(
    session: Session, owner_id: uuid.UUID, entries: Sequence[ActivityEntry]
) -> dict[uuid.UUID, uuid.UUID | None]:
    """
    Where each entry's entity can still be opened: the project to open it in,
    keyed by entity id — None for a tag, which belongs to no project. An
    entity that is gone, or hangs off a task that is, has no entry here, so
    its log entry carries no link.
    """
    by_type: dict[str, set[uuid.UUID]] = {}
    for entry in entries:
        by_type.setdefault(entry.entity_type, set()).add(entry.entity_id)

    # The task each comment and attachment hangs off, so that one lookup
    # resolves every task this page of the log touches.
    parents: dict[uuid.UUID, uuid.UUID] = {}
    for model, entity_type in (
        (Comment, ActivityEntityType.COMMENT),
        (Attachment, ActivityEntityType.ATTACHMENT),
    ):
        if ids := by_type.get(entity_type):
            parents.update(
                session.exec(
                    select(model.id, model.task_id).where(col(model.id).in_(ids))
                ).all()
            )
    task_ids = by_type.get(ActivityEntityType.TASK, set())
    task_projects = crud.get_task_project_ids(
        session=session,
        owner_id=owner_id,
        task_ids=task_ids | set(parents.values()),
    )

    locations: dict[uuid.UUID, uuid.UUID | None] = {
        task_id: task_projects[task_id]
        for task_id in task_ids
        if task_id in task_projects
    }
    locations.update(
        {
            row_id: task_projects[task_id]
            for row_id, task_id in parents.items()
            if task_id in task_projects
        }
    )
    if project_ids := by_type.get(ActivityEntityType.PROJECT):
        live = session.exec(
            select(Project.id).where(
                col(Project.id).in_(project_ids), crud.not_deleted(Project)
            )
        ).all()
        locations.update({project_id: project_id for project_id in live})
    if tag_ids := by_type.get(ActivityEntityType.TAG):
        tags = session.exec(select(Tag.id).where(col(Tag.id).in_(tag_ids))).all()
        locations.update(dict.fromkeys(tags))
    return locations
