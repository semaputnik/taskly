import calendar
import uuid
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from sqlalchemy import case, nullslast, or_
from sqlalchemy.orm import aliased
from sqlmodel import Session, col, func, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    Attachment,
    Comment,
    CommentCreate,
    CommentUpdate,
    Deletion,
    DueDateScope,
    Project,
    ProjectCreate,
    ProjectUpdate,
    Recurrence,
    RecurrenceFrequency,
    Series,
    SortOrder,
    Tag,
    Task,
    TaskCreate,
    TaskPriority,
    TaskQuery,
    TaskSort,
    TaskTag,
    TaskUpdate,
    User,
    UserCreate,
    UserUpdate,
)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    # Flush so the user row exists before the FK-dependent Inbox insert, while
    # keeping both inserts in the same transaction as the eventual commit.
    session.flush()
    session.add(Project(name="Inbox", is_inbox=True, owner_id=db_obj.id))
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def create_project(
    *,
    session: Session,
    project_create: ProjectCreate,
    owner_id: uuid.UUID,
    is_inbox: bool = False,
) -> Project:
    db_obj = Project.model_validate(
        project_create, update={"owner_id": owner_id, "is_inbox": is_inbox}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_project(
    *, session: Session, db_project: Project, project_in: ProjectUpdate
) -> Project:
    project_data = project_in.model_dump(exclude_unset=True)
    db_project.sqlmodel_update(project_data)
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    return db_project


def set_project_archived(
    *, session: Session, project: Project, archived: bool
) -> Project:
    """
    Archive or unarchive a project, and with it every task in it (FR-05.10,
    FR-05.11).

    One write to the project is the whole of it: its tasks follow because their
    archived state is derived, which is also what makes unarchiving put back
    exactly what was there. Nothing here touches deletion — archiving is not an
    event to be restored from.
    """
    project.is_archived = archived
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def get_inbox_project(*, session: Session, owner_id: uuid.UUID) -> Project:
    statement = select(Project).where(
        Project.owner_id == owner_id,
        Project.is_inbox == True,  # noqa: E712
        not_deleted(Project),
    )
    return session.exec(statement).one()


def create_task(
    *,
    session: Session,
    task_create: TaskCreate,
    project_id: uuid.UUID | None,
    owner_id: uuid.UUID,
    tag_names: Sequence[str] = (),
) -> Task:
    """
    Create a task. `project_id` is set on root tasks and None on subtasks,
    which derive their project from their root ancestor. A task created with a
    recurrence is the first occurrence of a new series, which the caller has
    checked it can be: a root task with a due date.
    """
    db_obj = Task.model_validate(
        task_create, update={"project_id": project_id, "owner_id": owner_id}
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
    tag_names: Sequence[str] | None = None,
) -> Task:
    """
    Apply an update to a task, including what it means for the task's series,
    and commit it as one transaction.

    Completing an occurrence of a recurring task creates the next one here, in
    the same commit as the completion (FR-01.14): there is never a moment with
    the series left with no open occurrence, or with two.
    """
    # The directives steer what happens around the row (the subtree, the
    # series) rather than naming columns of it, so they never reach it as such.
    task_data = task_in.model_dump(
        exclude_unset=True,
        exclude={"subtasks", "tags", "recurrence", "due_date_scope"},
    )
    fields_set = task_in.model_fields_set
    was_completed = db_task.completed

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

    # The completion has to reach the database before the next occurrence
    # does: only one open occurrence per series is ever allowed to exist.
    session.flush()

    if tag_names is not None:
        _stage_task_tags(session=session, task=db_task, names=tag_names)

    if db_task.completed and not was_completed and db_task.series_id is not None:
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


def shift_date(start: date, recurrence: Recurrence, intervals: int) -> date:
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
    latest occurrence can be open, so only it can be returned to not completed.
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
    (FR-01.15, FR-01.18). The subtask tree comes along with every subtask not
    completed; comments and attachments stay with the occurrence they were
    about.
    """
    assert task.due_date is not None and task.series_step is not None
    series = session.get_one(Series, task.series_id)
    step = task.series_step + 1
    due_date = shift_date(
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
    """A not-completed copy of `source`'s own fields and tags, and nothing else."""
    copy = Task(
        title=source.title,
        description=source.description,
        priority=source.priority,
        assignee_id=source.assignee_id,
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
    *, session: Session, owner_id: uuid.UUID, query: TaskQuery
) -> tuple[Sequence[Task], int]:
    """
    A page of the user's tasks, narrowed and ordered by `query`, with the
    number of tasks the filters match in full.
    """
    conditions = _task_filters(owner_id=owner_id, query=query)

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

    if query.unassigned:
        conditions.append(col(Task.assignee_id).is_(None))
    elif query.assignee_id is not None:
        conditions.append(Task.assignee_id == query.assignee_id)

    if query.tag is not None:
        tagged = (
            select(TaskTag.task_id)
            .join(Tag, col(Tag.id) == TaskTag.tag_id)
            .where(Tag.owner_id == owner_id, Tag.name == query.tag)
        )
        conditions.append(col(Task.id).in_(tagged))

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

    if query.completed is not None:
        conditions.append(Task.completed == query.completed)

    if query.due_from is not None:
        conditions.append(col(Task.due_date) >= query.due_from)
    if query.due_to is not None:
        conditions.append(col(Task.due_date) <= query.due_to)
    if query.overdue:
        conditions.append(col(Task.due_date) < date.today())

    return conditions


def _task_ordering(query: TaskQuery) -> list[Any]:
    """
    How the list is ordered. Without a sort it stays as it was: the most
    pressing work first, oldest first within a priority.
    """
    if query.sort is None:
        return [_PRIORITY_RANK, Task.created_at]

    descending = query.order is SortOrder.DESC
    if query.sort is TaskSort.DUE_DATE:
        due_date = col(Task.due_date)
        # A task with no due date is not early or late, so it goes last either
        # way rather than leading one of the two orders.
        ordering = nullslast(due_date.desc() if descending else due_date.asc())
    else:
        ordering = _PRIORITY_RANK.desc() if descending else _PRIORITY_RANK.asc()

    return [ordering, Task.created_at]


def get_tags(
    *,
    session: Session,
    owner_id: uuid.UUID,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[Sequence[Tag], int]:
    """
    The tags a user has used, for autocomplete. `q` matches from the start of
    the name, ignoring case, so what they type narrows to what they typed
    before rather than to every tag with those letters somewhere inside.
    """
    where: list[Any] = [Tag.owner_id == owner_id]
    if q:
        where.append(col(Tag.name).ilike(f"{q}%"))

    count = session.exec(select(func.count()).select_from(Tag).where(*where)).one()
    statement = (
        select(Tag)
        .where(*where)
        # Case-insensitive, so "Reading" and "running" sit where the user looks
        # for them rather than in two alphabets.
        .order_by(func.lower(Tag.name))
        .offset(skip)
        .limit(limit)
    )
    return session.exec(statement).all(), count


def get_task_tags(
    *, session: Session, task_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    """The tag names on each of the given tasks, keyed by task id."""
    if not task_ids:
        return {}

    statement = (
        select(TaskTag.task_id, Tag.name)
        .join(Tag, col(Tag.id) == TaskTag.tag_id)
        .where(col(TaskTag.task_id).in_(task_ids))
    )
    tags: dict[uuid.UUID, list[str]] = {task_id: [] for task_id in task_ids}
    for task_id, name in session.exec(statement).all():
        tags[task_id].append(name)
    return {task_id: sorted(names, key=str.lower) for task_id, names in tags.items()}


def _stage_task_tags(*, session: Session, task: Task, names: Sequence[str]) -> None:
    """
    Replace a task's tags with `names`, creating the ones the user has not used
    before (FR-01.20) and dropping any tag left on no task at all. Staged but
    not committed, so a caller can put it in the same transaction as whatever
    else it is writing.
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
    _drop_unused_tags(session=session, tag_ids=set(linked) - wanted)


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


def _drop_unused_tags(*, session: Session, tag_ids: set[uuid.UUID]) -> None:
    """
    Remove tags nothing carries any more.

    Applying and removing tags is the whole of tag management (FR-01.20), so a
    tag no task holds has no way back out of autocomplete unless it goes here.
    A soft-deleted task keeps its links, and with them its tags, so restoring
    it brings them back.
    """
    if not tag_ids:
        return

    still_used = set(
        session.exec(
            select(TaskTag.tag_id).where(col(TaskTag.tag_id).in_(tag_ids))
        ).all()
    )
    for tag_id in tag_ids - still_used:
        tag = session.get(Tag, tag_id)
        if tag is not None:
            session.delete(tag)


def not_deleted(model: type[Task] | type[Project]) -> Any:
    """
    The filter every normal query needs: a deletion marks a row instead of
    removing it, so deleted rows have to be left out explicitly (FR-01.8,
    FR-05.8).
    """
    return col(model.deletion_id).is_(None)


def _subtree_cte(root_id: uuid.UUID) -> Any:
    """
    Every descendant of `root_id` that is not deleted, to any depth, as
    (id, completed) rows.

    Deleted subtasks are left out: they carry their own deletion event, and a
    deletion always takes a whole subtree, so nothing that is still there hides
    under a deleted one.
    """
    subtree = (
        select(Task.id, Task.completed)
        .where(Task.parent_id == root_id, not_deleted(Task))
        .cte("subtree", recursive=True)
    )
    child = aliased(Task)
    return subtree.union_all(
        select(child.id, child.completed)
        .join(subtree, col(child.parent_id) == subtree.c.id)
        .where(not_deleted(child))
    )


def get_task_project_id(*, session: Session, task: Task) -> uuid.UUID:
    """
    Resolve the project a task belongs to: its own if it is a root task, its
    root ancestor's if it is a subtask (FR-02.4).
    """
    if task.project_id is not None:
        return task.project_id

    ancestors = (
        select(Task.id, Task.parent_id, Task.project_id)
        .where(Task.id == task.parent_id)
        .cte("ancestors", recursive=True)
    )
    parent = aliased(Task)
    ancestors = ancestors.union_all(
        select(parent.id, parent.parent_id, parent.project_id).join(
            ancestors, ancestors.c.parent_id == parent.id
        )
    )
    statement = select(ancestors.c.project_id).where(
        ancestors.c.project_id.is_not(None)
    )
    project_id: uuid.UUID = session.exec(statement).one()
    return project_id


def get_task_project_ids(
    *, session: Session, owner_id: uuid.UUID
) -> dict[uuid.UUID, uuid.UUID]:
    """
    The project every one of a user's tasks belongs to, keyed by task id.

    One walk down from the root tasks resolves whole trees at once, so listing
    tasks does not cost a query per subtask.
    """
    tree = (
        select(Task.id, Task.project_id)
        .where(
            Task.owner_id == owner_id,
            col(Task.parent_id).is_(None),
            not_deleted(Task),
        )
        .cte("task_projects", recursive=True)
    )
    child = aliased(Task)
    tree = tree.union_all(
        select(child.id, tree.c.project_id)
        .join(tree, col(child.parent_id) == tree.c.id)
        .where(not_deleted(child))
    )
    rows = session.exec(select(tree.c.id, tree.c.project_id)).all()
    return dict(rows)


def has_uncompleted_subtasks(*, session: Session, task: Task) -> bool:
    """
    Whether anything under the task, at any depth, is still not completed.
    """
    subtree = _subtree_cte(task.id)
    statement = select(subtree.c.id).where(subtree.c.completed.is_(False)).limit(1)
    return session.exec(statement).first() is not None


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


def delete_task(*, session: Session, task: Task) -> None:
    """
    Soft-delete a task and its subtree as a single event (FR-01.8, FR-01.11). Nothing is removed: every row keeps its data and points at the
    event that took it down, so a later restore can bring back exactly these
    rows — and only these.
    """
    deletion = Deletion(owner_id=task.owner_id, task_id=task.id)
    session.add(deletion)
    # The event row has to exist before anything can point at it.
    session.flush()

    subtree = _subtree_cte(task.id)
    _mark_deleted(session=session, task_ids=select(subtree.c.id), deletion=deletion)
    task.deletion_id = deletion.id
    session.add(task)
    session.commit()


def delete_project(*, session: Session, project: Project) -> None:
    """
    Soft-delete a project and every task in it as a single event (FR-05.8,
    FR-05.9).
    """
    deletion = Deletion(owner_id=project.owner_id, project_id=project.id)
    session.add(deletion)
    session.flush()

    _mark_deleted(
        session=session, task_ids=project_task_ids(project.id), deletion=deletion
    )
    project.deletion_id = deletion.id
    session.add(project)
    session.commit()


def get_deletion_rows(*, session: Session, deletion_id: uuid.UUID) -> Sequence[Task]:
    """The tasks a deletion event took down that are still deleted by it."""
    return session.exec(select(Task).where(Task.deletion_id == deletion_id)).all()


def restoring_reopens_a_series(*, session: Session, tasks: Sequence[Task]) -> bool:
    """
    Whether bringing these tasks back would leave a recurring series with two
    open occurrences (FR-01.16): one of them is open, and its series already
    has another open occurrence that is not deleted.
    """
    restoring = [task.id for task in tasks]
    for task in tasks:
        if task.series_id is None or task.completed:
            continue
        statement = (
            select(Task.id)
            .where(
                Task.series_id == task.series_id,
                Task.completed == False,  # noqa: E712
                not_deleted(Task),
                col(Task.id).not_in(restoring),
            )
            .limit(1)
        )
        if session.exec(statement).first() is not None:
            return True
    return False


def restore_deletion(
    *, session: Session, tasks: Sequence[Task], project: Project | None = None
) -> None:
    """
    Bring back the rows of one deletion event (FR-10.4, FR-01.10, FR-05.9).

    Clearing the marker is the whole restore, for a task and its subtasks and
    for a project and its tasks alike: nothing is re-created, so each row comes
    back as itself, with its comments, attachments, tags and history. Only the
    rows still marked by this event come back, which is what leaves anything
    deleted on its own beforehand deleted. Archiving is a separate state and is
    left as it was.
    """
    for task in tasks:
        task.deletion_id = None
        session.add(task)
    if project is not None:
        project.deletion_id = None
        session.add(project)
    session.commit()


def project_task_ids(project_id: uuid.UUID) -> Any:
    """
    Selects the ids of every task of a project that is not deleted: its root
    tasks and everything under them.
    """
    return _task_trees(Task.project_id == project_id, name="project_tasks")


def archived_task_ids(owner_id: uuid.UUID) -> Any:
    """
    Selects the ids of every task of a user's archived projects that is not
    deleted.

    Nothing on a task says it is archived: it is archived because the project it
    resolves to is (FR-05.11), so this is found the same way a project's tasks
    are.
    """
    archived_projects = select(Project.id).where(
        Project.owner_id == owner_id,
        Project.is_archived == True,  # noqa: E712
    )
    return _task_trees(
        col(Task.project_id).in_(archived_projects), name="archived_tasks"
    )


def _task_trees(root_condition: Any, *, name: str) -> Any:
    """
    Selects the ids of the root tasks matching `root_condition` and of every
    task under them, leaving deleted ones out.

    Subtasks hold no project of their own, so the tasks of a project are only
    reachable by walking down from its root tasks. `name` names the CTE, which
    has to be unique among the ones a single statement uses.
    """
    tasks = (
        select(Task.id)
        .where(root_condition, not_deleted(Task))
        .cte(name, recursive=True)
    )
    child = aliased(Task)
    tasks = tasks.union_all(
        select(child.id)
        .join(tasks, col(child.parent_id) == tasks.c.id)
        .where(not_deleted(child))
    )
    return select(tasks.c.id)


def _mark_deleted(*, session: Session, task_ids: Any, deletion: Deletion) -> None:
    statement = select(Task).where(col(Task.id).in_(task_ids))
    for task in session.exec(statement):
        task.deletion_id = deletion.id
        session.add(task)


def complete_subtasks(*, session: Session, task: Task) -> None:
    """
    Mark the task's whole subtree completed, leaving the task itself to the
    caller. Staged, not committed: the caller's update commits both together.
    """
    subtree = _subtree_cte(task.id)
    statement = select(Task).where(col(Task.id).in_(select(subtree.c.id)))
    for subtask in session.exec(statement):
        subtask.completed = True
        session.add(subtask)


def create_comment(
    *,
    session: Session,
    comment_create: CommentCreate,
    task_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> Comment:
    db_obj = Comment.model_validate(
        comment_create, update={"task_id": task_id, "owner_id": owner_id}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_comments(
    *, session: Session, task_id: uuid.UUID
) -> tuple[Sequence[Comment], int]:
    """
    A task's comments, oldest first, so the thread reads as a narrative
    (FR-03.1) rather than a feed.
    """
    statement = (
        select(Comment)
        .where(Comment.task_id == task_id)
        .order_by(col(Comment.created_at))
    )
    comments = session.exec(statement).all()
    return comments, len(comments)


def update_comment(
    *, session: Session, db_comment: Comment, comment_in: CommentUpdate
) -> Comment:
    comment_data = comment_in.model_dump(exclude_unset=True)
    db_comment.sqlmodel_update(comment_data)
    session.add(db_comment)
    session.commit()
    session.refresh(db_comment)
    return db_comment


def delete_comment(*, session: Session, comment: Comment) -> None:
    session.delete(comment)
    session.commit()


def create_attachment(
    *,
    session: Session,
    task_id: uuid.UUID,
    owner_id: uuid.UUID,
    filename: str,
    content_type: str,
    size: int,
) -> Attachment:
    db_obj = Attachment(
        task_id=task_id,
        owner_id=owner_id,
        filename=filename,
        content_type=content_type,
        size=size,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_attachments(
    *, session: Session, task_id: uuid.UUID
) -> tuple[Sequence[Attachment], int]:
    statement = (
        select(Attachment)
        .where(Attachment.task_id == task_id)
        .order_by(col(Attachment.created_at))
    )
    attachments = session.exec(statement).all()
    return attachments, len(attachments)


def get_owner_attachment_ids(
    *, session: Session, owner_id: uuid.UUID
) -> Sequence[uuid.UUID]:
    """
    Every attachment id a user owns, so their bytes can be released from
    storage before the account's rows are gone — deleting the user cascades
    at the database level (FK `ondelete=CASCADE`), which drops these rows
    without ever calling into the storage backend.
    """
    statement = select(Attachment.id).where(Attachment.owner_id == owner_id)
    return session.exec(statement).all()


def delete_attachment(*, session: Session, attachment: Attachment) -> None:
    session.delete(attachment)
    session.commit()


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user
