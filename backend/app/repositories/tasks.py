"""
Tasks: creating and updating one, including what an update means for its
series and its next occurrence; listing and filtering them; its subtree
(subtasks at any depth) and the counts built on it; and batch updates over a
selection.
"""

import calendar
import uuid
from collections.abc import Collection, Sequence
from datetime import date, timedelta
from typing import Any, NamedTuple

from sqlalchemy import case, nullslast, or_
from sqlmodel import Session, col, func, select

from app.models import (
    DueDateScope,
    Recurrence,
    RecurrenceFrequency,
    Series,
    SortOrder,
    SubtaskCompletion,
    Tag,
    Task,
    TaskBulkUpdate,
    TaskCreate,
    TaskPriority,
    TaskQuery,
    TaskSort,
    TaskStatus,
    TaskTag,
    TaskUpdate,
)

from .predicates import (
    archived_task_ids,
    is_open,
    not_deleted,
    project_task_ids,
    subtree_cte,
    tasks_in_projects,
)
from .tags import get_task_tags


class Assignee(NamedTuple):
    """
    Who a task is assigned to, as the two columns that can hold it. Both None
    is nobody; the API's single `assignee_id` is resolved into this first.
    """

    user_id: uuid.UUID | None = None
    bot_user_id: uuid.UUID | None = None


class Reporter(NamedTuple):
    """
    Who filed a task, as the two columns that hold it. Exactly one is set:
    every task has an author, so unlike `Assignee` there is no empty value
    and no default — a caller has to say who is filing.
    """

    user_id: uuid.UUID | None = None
    bot_user_id: uuid.UUID | None = None


def create_task(
    *,
    session: Session,
    task_create: TaskCreate,
    project_id: uuid.UUID | None,
    owner_id: uuid.UUID,
    reporter: Reporter,
    assignee: Assignee = Assignee(),
    tag_names: Sequence[str] = (),
) -> Task:
    """
    Create a task. `project_id` is set on root tasks and None on subtasks,
    which derive their project from their root ancestor. A task created with a
    recurrence is the first occurrence of a new series, which the caller has
    checked it can be: a root task with a due date.
    """
    db_obj = Task.model_validate(
        task_create,
        update={
            "project_id": project_id,
            "owner_id": owner_id,
            "assignee_id": assignee.user_id,
            "assignee_bot_user_id": assignee.bot_user_id,
            "reporter_id": reporter.user_id,
            "reporter_bot_user_id": reporter.bot_user_id,
        },
    )
    session.add(db_obj)
    # Flush so the task row exists before the tag links that point at it, while
    # keeping the whole creation in one transaction: a task never lands without
    # the tags it was typed with.
    session.flush()
    _stage_task_tags(session=session, task=db_obj, names=tag_names)
    if task_create.recurrence is not None:
        _stage_recurrence(
            session=session, task=db_obj, recurrence=task_create.recurrence
        )
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_task(
    *,
    session: Session,
    db_task: Task,
    task_in: TaskUpdate,
    assignee: Assignee | None = None,
    tag_names: Sequence[str] | None = None,
) -> Task:
    """
    Apply an update to a task, including what it means for the task's series,
    and commit it as one transaction.

    Moving an occurrence of a recurring task to done creates the next one here,
    in the same commit as the move (FR-01.14): there is never a moment with
    the series left with no open occurrence, or with two.
    """
    # The directives steer what happens around the row (the subtree, the
    # series) rather than naming columns of it, so they never reach it as such.
    # The assignee arrives resolved, as `assignee`.
    task_data = task_in.model_dump(
        exclude_unset=True,
        exclude={"subtasks", "tags", "recurrence", "due_date_scope", "assignee_id"},
    )
    fields_set = task_in.model_fields_set
    if "assignee_id" in fields_set and assignee is None:
        raise ValueError("An update that sets the assignee needs it resolved")
    if assignee is not None:
        task_data["assignee_id"] = assignee.user_id
        task_data["assignee_bot_user_id"] = assignee.bot_user_id
    was_done = db_task.status is TaskStatus.DONE

    db_task.sqlmodel_update(task_data)
    session.add(db_task)

    if "recurrence" in fields_set:
        _stage_recurrence(session=session, task=db_task, recurrence=task_in.recurrence)
    # Not an alternative to the above: a client resending the rule the task
    # already has is still asking for the series to move.
    if (
        task_in.due_date_scope is DueDateScope.THIS_AND_FOLLOWING
        and db_task.series_id is not None
    ):
        _stage_reanchor(session=session, task=db_task)

    # The move to done has to reach the database before the next occurrence
    # does: only one open occurrence per series is ever allowed to exist.
    session.flush()

    if tag_names is not None:
        _stage_task_tags(session=session, task=db_task, names=tag_names)

    if (
        db_task.status is TaskStatus.DONE
        and not was_done
        and db_task.series_id is not None
    ):
        _stage_next_occurrence(session=session, task=db_task)

    session.commit()
    session.refresh(db_task)
    return db_task


def get_recurrences(
    *, session: Session, tasks: Sequence[Task]
) -> dict[uuid.UUID, Recurrence | None]:
    """The recurrence of each of the given tasks, keyed by task id."""
    series_ids = {task.series_id for task in tasks if task.series_id is not None}
    series: dict[uuid.UUID, Series] = {}
    if series_ids:
        statement = select(Series).where(col(Series.id).in_(series_ids))
        series = {row.id: row for row in session.exec(statement).all()}
    return {
        task.id: _recurrence_of(series[task.series_id])
        if task.series_id is not None
        else None
        for task in tasks
    }


def _recurrence_of(series: Series) -> Recurrence:
    return Recurrence(frequency=series.frequency, interval_days=series.interval_days)


def _shift_date(start: date, recurrence: Recurrence, intervals: int) -> date:
    """
    The date a whole number of recurrence intervals away from `start`.

    Months are counted on the calendar, keeping the day of the month and
    landing on the month's last day when it is shorter: from January 31st,
    one month is February's last day and two months is March 31st.
    """
    if recurrence.frequency is RecurrenceFrequency.MONTHLY:
        months = start.month - 1 + intervals
        year = start.year + months // 12
        month = months % 12 + 1
        day = min(start.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    if recurrence.frequency is RecurrenceFrequency.DAILY:
        days = 1
    elif recurrence.frequency is RecurrenceFrequency.WEEKLY:
        days = 7
    else:
        assert recurrence.interval_days is not None
        days = recurrence.interval_days
    return start + timedelta(days=days * intervals)


def is_superseded(*, session: Session, task: Task) -> bool:
    """
    Whether a later occurrence of the task's series already exists. Only the
    latest occurrence can be open, so only it can be moved out of done.
    """
    if task.series_id is None or task.series_step is None:
        return False
    statement = (
        select(Task.id)
        .where(
            Task.series_id == task.series_id,
            col(Task.series_step) > task.series_step,
            not_deleted(Task),
        )
        .limit(1)
    )
    return session.exec(statement).first() is not None


def _stage_recurrence(
    *, session: Session, task: Task, recurrence: Recurrence | None
) -> None:
    """
    Give the task the recurrence it asks for.

    `None` takes the task out of its series, so completing it creates nothing.
    A task that did not recur starts a series with itself as the first
    occurrence. A task whose rule changes keeps its series and restarts the
    schedule from its own due date: a new rhythm has no older date to keep to.
    """
    if recurrence is None:
        task.series_id = None
        task.series_step = None
        session.add(task)
        return

    assert task.due_date is not None, "a recurring task needs a due date"

    if task.series_id is None:
        series = Series(
            owner_id=task.owner_id,
            frequency=recurrence.frequency,
            interval_days=recurrence.interval_days,
            anchor_date=task.due_date,
            anchor_step=0,
        )
        session.add(series)
        session.flush()
        task.series_id = series.id
        task.series_step = 0
        session.add(task)
        return

    series = session.get_one(Series, task.series_id)
    if _recurrence_of(series) == recurrence:
        return
    series.frequency = recurrence.frequency
    series.interval_days = recurrence.interval_days
    session.add(series)
    _stage_reanchor(session=session, task=task)


def _stage_reanchor(*, session: Session, task: Task) -> None:
    """
    Move the series' schedule onto this occurrence's due date, so every later
    occurrence is counted from it (FR-01.19).
    """
    assert task.due_date is not None and task.series_step is not None
    series = session.get_one(Series, task.series_id)
    series.anchor_date = task.due_date
    series.anchor_step = task.series_step
    session.add(series)


def _stage_next_occurrence(*, session: Session, task: Task) -> Task:
    """
    Create the occurrence that follows `task` in its series (FR-01.14).

    Its due date comes from the series' schedule, not from `task`'s own date,
    so an occurrence moved on its own leaves the rest where they were
    (FR-01.15, FR-01.18). The subtask tree comes along with every subtask back
    in to do; comments and attachments stay with the occurrence they were
    about.
    """
    assert task.due_date is not None and task.series_step is not None
    series = session.get_one(Series, task.series_id)
    step = task.series_step + 1
    due_date = _shift_date(
        series.anchor_date, _recurrence_of(series), step - series.anchor_step
    )

    successor = _stage_copy(
        session=session,
        source=task,
        parent_id=None,
        project_id=task.project_id,
        due_date=due_date,
    )
    successor.series_id = series.id
    successor.series_step = step
    session.add(successor)

    _stage_subtree_copy(
        session=session,
        source_id=task.id,
        target_id=successor.id,
        # Subtasks keep their distance from the task at the top: a checklist
        # item due the day before the occurrence is due the day before the
        # next one too.
        offset=due_date - task.due_date,
    )
    return successor


def _stage_copy(
    *,
    session: Session,
    source: Task,
    parent_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    due_date: date | None,
) -> Task:
    """A to-do copy of `source`'s own fields and tags, and nothing else."""
    copy = Task(
        title=source.title,
        # Not Backlog, where a new task starts: the decision to do recurring
        # work was made when its series was set up (ADR-0008).
        status=TaskStatus.TODO,
        description=source.description,
        priority=source.priority,
        assignee_id=source.assignee_id,
        assignee_bot_user_id=source.assignee_bot_user_id,
        # The series was filed once. Each occurrence is that same work
        # recurring, not something new filed by whoever completed the last
        # one, so the author comes along with everything else it copies.
        reporter_id=source.reporter_id,
        reporter_bot_user_id=source.reporter_bot_user_id,
        due_date=due_date,
        parent_id=parent_id,
        project_id=project_id,
        owner_id=source.owner_id,
    )
    session.add(copy)
    session.flush()
    names = get_task_tags(session=session, task_ids=[source.id])[source.id]
    _stage_task_tags(session=session, task=copy, names=names)
    return copy


def _stage_subtree_copy(
    *, session: Session, source_id: uuid.UUID, target_id: uuid.UUID, offset: timedelta
) -> None:
    """Copy every subtask under `source_id` that is not deleted to under
    `target_id`, keeping the tree's shape and its siblings' order."""
    children = session.exec(
        select(Task)
        .where(Task.parent_id == source_id, not_deleted(Task))
        .order_by(col(Task.created_at))
    ).all()
    for child in children:
        copy = _stage_copy(
            session=session,
            source=child,
            parent_id=target_id,
            project_id=None,
            due_date=child.due_date + offset if child.due_date else None,
        )
        _stage_subtree_copy(
            session=session, source_id=child.id, target_id=copy.id, offset=offset
        )


def get_tasks(
    *,
    session: Session,
    owner_id: uuid.UUID,
    query: TaskQuery,
    project_ids: Collection[uuid.UUID] | None = None,
) -> tuple[Sequence[Task], int]:
    """
    A page of the user's tasks, narrowed and ordered by `query`, with the
    number of tasks the filters match in full.

    `project_ids`, when given, keeps to the tasks of those projects, as a bot
    user's scope does; the query's filters narrow within them.
    """
    conditions = _task_filters(owner_id=owner_id, query=query)
    if project_ids is not None:
        conditions.append(col(Task.id).in_(tasks_in_projects(project_ids)))

    count = session.exec(
        select(func.count()).select_from(Task).where(*conditions)
    ).one()
    statement = (
        select(Task)
        .where(*conditions)
        .order_by(*_task_ordering(query))
        .offset(query.skip)
        .limit(query.limit)
    )
    return session.exec(statement).all(), count


# Unset priority sorts as P4 (lowest) without being reported as P4.
_PRIORITY_RANK = case(
    (Task.priority == TaskPriority.P1, 1),  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
    (Task.priority == TaskPriority.P2, 2),  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
    (Task.priority == TaskPriority.P3, 3),  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
    else_=4,
)


def _task_filters(*, owner_id: uuid.UUID, query: TaskQuery) -> list[Any]:
    """
    What a task has to satisfy to be listed: the user's own tasks that are not
    deleted, on the side of the archive that was asked for, plus every filter
    that is set (FR-06.2, FR-06.3).
    """
    conditions: list[Any] = [Task.owner_id == owner_id, not_deleted(Task)]

    # Archived work is its own view rather than one more thing to filter in:
    # the default list is live work only, and asking for the archive lists
    # nothing else (FR-05.14).
    archived = col(Task.id).in_(archived_task_ids(owner_id))
    conditions.append(archived if query.archived else ~archived)

    if query.project_id is not None:
        conditions.append(col(Task.id).in_(project_task_ids(query.project_id)))

    if query.parent_id is not None:
        conditions.append(col(Task.parent_id) == query.parent_id)

    if query.unassigned:
        conditions.append(col(Task.assignee_id).is_(None))
        conditions.append(col(Task.assignee_bot_user_id).is_(None))
    elif query.assignee_id is not None:
        # The owner or a bot user: the id names one or the other.
        conditions.append(
            or_(
                col(Task.assignee_id) == query.assignee_id,
                col(Task.assignee_bot_user_id) == query.assignee_id,
            )
        )

    if query.assigned_to_bots:
        conditions.append(col(Task.assignee_bot_user_id).is_not(None))

    if query.reporter_id is not None:
        # The owner or a bot user: the id names one or the other, as it does
        # for the assignee.
        conditions.append(
            or_(
                col(Task.reporter_id) == query.reporter_id,
                col(Task.reporter_bot_user_id) == query.reporter_id,
            )
        )

    if query.tag is not None:
        tagged = (
            select(TaskTag.task_id)
            .join(Tag, col(Tag.id) == TaskTag.tag_id)
            .where(Tag.owner_id == owner_id, Tag.name == query.tag)
        )
        conditions.append(col(Task.id).in_(tagged))

    if query.title is not None:
        # `%` and `_` in the typed text are letters, not wildcards.
        conditions.append(col(Task.title).icontains(query.title, autoescape=True))

    if query.priority is not None:
        if query.priority is TaskPriority.P4:
            # A task with no priority behaves as P4 (FR-01.3), so it answers to
            # a P4 filter too.
            conditions.append(
                or_(
                    col(Task.priority) == TaskPriority.P4,
                    col(Task.priority).is_(None),
                )
            )
        else:
            conditions.append(Task.priority == query.priority)

    if query.status:
        conditions.append(col(Task.status).in_(query.status))

    if query.due_from is not None:
        conditions.append(col(Task.due_date) >= query.due_from)
    if query.due_to is not None:
        conditions.append(col(Task.due_date) <= query.due_to)
    if query.overdue:
        conditions.append(col(Task.due_date) < date.today())
        conditions.append(is_open(Task))

    return conditions


# Which way each sort runs when the request names no direction. Only the
# created order reads backwards: the point of it is what has just arrived.
_NATURAL_ORDER = {
    TaskSort.DUE_DATE: SortOrder.ASC,
    TaskSort.PRIORITY: SortOrder.ASC,
    TaskSort.CREATED_AT: SortOrder.DESC,
}


def _task_ordering(query: TaskQuery) -> list[Any]:
    """
    How the list is ordered. Without a sort it is the created order, newest
    filed first (FR-06.4); the most pressing work is asked for by name.
    """
    sort = query.sort or TaskSort.CREATED_AT
    descending = (query.order or _NATURAL_ORDER[sort]) is SortOrder.DESC
    created_at = col(Task.created_at)
    # Annotated because the branches build expressions over columns of
    # different types, which mypy will not unify on its own.
    ordering: Any
    if sort is TaskSort.DUE_DATE:
        due_date = col(Task.due_date)
        # A task with no due date is not early or late, so it goes last either
        # way rather than leading one of the two orders.
        ordering = nullslast(due_date.desc() if descending else due_date.asc())
    elif sort is TaskSort.CREATED_AT:
        ordering = created_at.desc() if descending else created_at.asc()
    else:
        ordering = _PRIORITY_RANK.desc() if descending else _PRIORITY_RANK.asc()

    # Two tasks filed in the same instant would otherwise come back in
    # whatever order the database found them, which can differ between the
    # queries that fetch two pages of one list: a task shown twice, and
    # another never shown at all.
    return [ordering, created_at, Task.id]


class _SubtaskCounts(NamedTuple):
    total: int
    done: int


def get_subtask_counts(
    *, session: Session, task_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, _SubtaskCounts]:
    """
    How many live subtasks each of the given tasks has one level down, and how
    many of those are done, keyed by task id. A deleted subtask is not counted.
    """
    if not task_ids:
        return {}

    statement = (
        select(
            Task.parent_id,
            func.count(),
            func.count().filter(col(Task.status) == TaskStatus.DONE),
        )
        .where(col(Task.parent_id).in_(task_ids), col(Task.deletion_id).is_(None))
        .group_by(col(Task.parent_id))
    )
    counts = dict.fromkeys(task_ids, _SubtaskCounts(0, 0))
    for parent_id, total, done in session.exec(statement).all():
        if parent_id is not None:
            counts[parent_id] = _SubtaskCounts(total, done)
    return counts


def _stage_task_tags(*, session: Session, task: Task, names: Sequence[str]) -> None:
    """
    Replace a task's tags with `names`, creating the ones the user does not
    have yet (FR-01.20). A tag taken off its last task stays (FR-01.23). Staged
    but not committed, so a caller can put it in the same transaction as
    whatever else it is writing.
    """
    links = session.exec(select(TaskTag).where(TaskTag.task_id == task.id)).all()
    linked = {link.tag_id: link for link in links}

    tags = _tags_for_names(session=session, owner_id=task.owner_id, names=names)
    wanted = {tag.id for tag in tags}

    for tag_id, link in linked.items():
        if tag_id not in wanted:
            session.delete(link)
    for tag in tags:
        if tag.id not in linked:
            session.add(TaskTag(task_id=task.id, tag_id=tag.id))

    session.flush()


def _tags_for_names(
    *, session: Session, owner_id: uuid.UUID, names: Sequence[str]
) -> list[Tag]:
    """The user's tags with these names, creating any that are new to them."""
    if not names:
        return []

    statement = select(Tag).where(Tag.owner_id == owner_id, col(Tag.name).in_(names))
    existing = {tag.name: tag for tag in session.exec(statement).all()}

    tags = []
    for name in names:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name, owner_id=owner_id)
            session.add(tag)
        tags.append(tag)
    session.flush()
    return tags


def has_open_subtasks(*, session: Session, task: Task) -> bool:
    """
    Whether anything under the task, at any depth, is still open.
    """
    subtree = subtree_cte(task.id)
    statement = select(subtree.c.id).where(subtree.c.status != TaskStatus.DONE).limit(1)
    return session.exec(statement).first() is not None


def open_subtasks(*, session: Session, task: Task) -> list[Task]:
    """
    Every still-open descendant of `task`, at any depth — the same subtree
    `has_open_subtasks` checks, read out in full rather than as a boolean,
    for a refusal that names what is in the way (`complete_task`, #257)
    instead of only saying something is.
    """
    subtree = subtree_cte(task.id)
    open_ids = select(subtree.c.id).where(subtree.c.status != TaskStatus.DONE)
    statement = (
        select(Task).where(col(Task.id).in_(open_ids)).order_by(col(Task.created_at))
    )
    return list(session.exec(statement).all())


def has_subtasks(*, session: Session, task: Task) -> bool:
    """
    Whether the task still has subtasks that are not deleted.

    Direct children are enough: deleting takes a whole subtree, so nothing is
    left below a deleted child.
    """
    statement = (
        select(Task.id).where(Task.parent_id == task.id, not_deleted(Task)).limit(1)
    )
    return session.exec(statement).first() is not None


def subtasks(*, session: Session, task: Task) -> list[Task]:
    """
    Every live descendant of `task`, at any depth, whatever its own status —
    the same subtree a delete cascades over (`app.deletions.delete_task`),
    read out in full for a refusal that names what would go down with it
    (`delete_task`, #258).

    Deliberately not `open_subtasks`: that one filters to what is still open,
    which is the right question for closing a task (only an open subtask
    stands in the way, #257) but the wrong one for deleting it — a delete
    takes a done subtask along with an open one, so a refusal built on
    `open_subtasks` would undercount what is actually at stake.
    """
    subtree = subtree_cte(task.id)
    statement = (
        select(Task)
        .where(col(Task.id).in_(select(subtree.c.id)))
        .order_by(col(Task.created_at))
    )
    return list(session.exec(statement).all())


def bulk_update_tasks(
    *,
    session: Session,
    tasks: Sequence[Task],
    changes: TaskBulkUpdate,
    assignee: Assignee | None = None,
) -> None:
    """
    Apply one set of changes to every task, in one transaction.

    Staged task by task and committed once: a batch either lands whole or not
    at all, so a refusal anywhere leaves the selection exactly as it was.
    """
    fields = changes.model_dump(
        exclude_unset=True,
        exclude={
            "task_ids",
            "subtasks",
            "add_tags",
            "remove_tags",
            "assignee_id",
        },
    )
    if "assignee_id" in changes.model_fields_set:
        if assignee is None:
            raise ValueError("A batch that sets the assignee needs it resolved")
        fields["assignee_id"] = assignee.user_id
        fields["assignee_bot_user_id"] = assignee.bot_user_id

    for task in tasks:
        if (
            changes.status is TaskStatus.DONE
            and changes.subtasks is SubtaskCompletion.COMPLETE
        ):
            complete_subtasks(session=session, task=task)
        was_done = task.status is TaskStatus.DONE
        task.sqlmodel_update(fields)
        session.add(task)
        # Moving an occurrence of a recurring task to done creates the next
        # one, in the same transaction, so a series is never left with no open
        # occurrence — a batch closes a task exactly as a single update does
        # (FR-01.14).
        if (
            task.status is TaskStatus.DONE
            and not was_done
            and task.series_id is not None
        ):
            _stage_next_occurrence(session=session, task=task)
        if changes.add_tags or changes.remove_tags:
            _stage_tag_changes(
                session=session,
                task=task,
                add=changes.add_tags,
                remove=changes.remove_tags,
            )
    session.commit()


def _stage_tag_changes(
    *, session: Session, task: Task, add: Sequence[str], remove: Sequence[str]
) -> None:
    """
    Put tags on a task and take tags off it, leaving the rest alone.

    A batch labels a selection; it does not replace what each task carried,
    which is why this adds and removes rather than setting the whole set.
    """
    current = get_task_tags(session=session, task_ids=[task.id])[task.id]
    wanted = [name for name in current if name not in remove]
    wanted.extend(name for name in add if name not in wanted)
    if wanted != current:
        _stage_task_tags(session=session, task=task, names=wanted)


def complete_subtasks(*, session: Session, task: Task) -> None:
    """
    Move the task's whole subtree to done, leaving the task itself to the
    caller. Staged, not committed: the caller's update commits both together.
    """
    subtree = subtree_cte(task.id)
    statement = select(Task).where(col(Task.id).in_(select(subtree.c.id)))
    for subtask in session.exec(statement):
        subtask.status = TaskStatus.DONE
        session.add(subtask)
