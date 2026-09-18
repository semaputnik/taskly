import calendar
import hashlib
import re
import uuid
from collections.abc import Collection, Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any, NamedTuple

from sqlalchemy import and_, case, nullslast, or_
from sqlalchemy.orm import aliased
from sqlmodel import Session, col, func, select

from app.core.security import (
    generate_bot_token,
    get_password_hash,
    hash_bot_token,
    verify_password,
)
from app.models import (
    ActivityAction,
    ActivityEntityType,
    ActivityEntry,
    Attachment,
    BotUser,
    BotUserCreate,
    BotUserProject,
    BotUserRef,
    BotUserUpdate,
    Comment,
    CommentCreate,
    CommentUpdate,
    DueDateScope,
    Project,
    ProjectCreate,
    ProjectPublic,
    ProjectUpdate,
    Recurrence,
    RecurrenceFrequency,
    Series,
    SortOrder,
    SubtaskCompletion,
    Tag,
    TagDuplicateDismissal,
    TagPublic,
    Task,
    TaskBulkUpdate,
    TaskCreate,
    TaskPriority,
    TaskQuery,
    TaskSort,
    TaskStatus,
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


class Assignee(NamedTuple):
    """
    Who a task is assigned to, as the two columns that can hold it. Both None
    is nobody; the API's single `assignee_id` is resolved into this first.
    """

    user_id: uuid.UUID | None = None
    bot_user_id: uuid.UUID | None = None


def create_task(
    *,
    session: Session,
    task_create: TaskCreate,
    project_id: uuid.UUID | None,
    owner_id: uuid.UUID,
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
    """A to-do copy of `source`'s own fields and tags, and nothing else."""
    copy = Task(
        title=source.title,
        description=source.description,
        priority=source.priority,
        assignee_id=source.assignee_id,
        assignee_bot_user_id=source.assignee_bot_user_id,
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
        conditions.append(
            col(Task.id).in_(
                _task_trees(col(Task.project_id).in_(project_ids), name="scope_tasks")
            )
        )

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
    near: str | None = None,
    skip: int = 0,
    limit: int = 100,
    name_creators: bool = True,
) -> tuple[list[TagPublic], int]:
    """
    The user's tags, each with the number of tasks carrying it. `q` matches
    from the start of the name, ignoring case, so what they type narrows to
    what they typed before rather than to every tag with those letters
    somewhere inside. `near` finds the tags a name would read the same as
    (`tag_key`), over the whole vocabulary: what a name about to become a new
    tag would duplicate (FR-01.28).
    """
    where: list[Any] = [Tag.owner_id == owner_id]
    if q:
        where.append(col(Tag.name).ilike(f"{q}%"))
    if near is not None:
        # Narrowed in the database to names that fold to the key with or
        # without a trailing "s", then held to `tag_key` exactly: this runs as
        # a name is typed, so it must not read the whole vocabulary each time.
        key = tag_key(near)
        folded = func.lower(
            func.regexp_replace(func.trim(col(Tag.name)), r"[\s_-]+", " ", "g")
        )
        candidates = session.exec(
            select(Tag.name).where(
                Tag.owner_id == owner_id, folded.in_([key, f"{key}s"])
            )
        ).all()
        where.append(
            col(Tag.name).in_([name for name in candidates if tag_key(name) == key])
        )

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
    tags = session.exec(statement).all()
    return tag_publics(session=session, tags=tags, name_creators=name_creators), count


def tag_publics(
    *, session: Session, tags: Sequence[Tag], name_creators: bool = True
) -> list[TagPublic]:
    """
    Tags as the API reports them, with how many tasks carry each.

    `task_count` is the live tasks carrying the tag — neither deleted nor
    archived with their project — because that is exactly what the task list
    filtered by the tag shows, and the count is read as a promise about that
    list (FR-01.26). The tasks archived with their project are
    reported beside it rather than dropped: deleting or merging the tag still
    reaches them, and those confirmations have to say so.

    The counts are the owner's whoever asks, a bot user included, so one tag
    never means two things (ADR-0003). Which bot user created a tag is the
    owner's to know: `name_creators` is off for a bot user reading.
    """
    if not tags:
        return []
    owner_id = tags[0].owner_id
    tag_ids = [tag.id for tag in tags]
    archived = col(Task.id).in_(archived_task_ids(owner_id))
    rows = session.exec(
        select(
            TaskTag.tag_id,
            func.count().filter(~archived),
            func.count().filter(archived),
        )
        .where(
            col(TaskTag.tag_id).in_(tag_ids),
            TaskTag.task_id == Task.id,
            not_deleted(Task),
        )
        .group_by(col(TaskTag.tag_id))
    ).all()
    counts = {tag_id: (live, archived_count) for tag_id, live, archived_count in rows}
    # Who created a tag is what its "created" entry in the activity log says.
    creators = (
        {}
        if not name_creators
        else {
            tag_id: bot_id
            for tag_id, bot_id in session.exec(
                select(ActivityEntry.entity_id, ActivityEntry.actor_bot_user_id).where(
                    ActivityEntry.entity_type == ActivityEntityType.TAG,
                    ActivityEntry.action == ActivityAction.TAG_CREATED,
                    col(ActivityEntry.entity_id).in_(tag_ids),
                )
            ).all()
            if bot_id is not None
        }
    )
    bots = get_bot_user_refs(session=session, bot_user_ids=creators.values())
    return [
        TagPublic(
            id=tag.id,
            name=tag.name,
            task_count=counts.get(tag.id, (0, 0))[0],
            archived_task_count=counts.get(tag.id, (0, 0))[1],
            created_by_bot_user=bots.get(creators[tag.id])
            if tag.id in creators
            else None,
        )
        for tag in tags
    ]


def get_tag_by_name(*, session: Session, owner_id: uuid.UUID, name: str) -> Tag | None:
    return session.exec(
        select(Tag).where(Tag.owner_id == owner_id, Tag.name == name)
    ).first()


def get_tag_names(
    *, session: Session, owner_id: uuid.UUID, names: Sequence[str]
) -> set[str]:
    """Which of `names` the user already has a tag for."""
    if not names:
        return set()
    statement = select(Tag.name).where(
        Tag.owner_id == owner_id, col(Tag.name).in_(names)
    )
    return set(session.exec(statement).all())


def create_tag(*, session: Session, owner_id: uuid.UUID, name: str) -> Tag:
    tag = Tag(name=name, owner_id=owner_id)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def rename_tag(*, session: Session, tag: Tag, name: str) -> Tag:
    """
    Rename a tag. Tasks point at it by key, so every task carrying it shows
    the new name at once (FR-01.24).
    """
    tag.name = name
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def delete_tag(*, session: Session, tag: Tag) -> None:
    """
    Delete a tag for good (FR-01.25). The database takes it off every task
    carrying it, deleted tasks included, so a task restored later comes back
    without it.
    """
    session.delete(tag)
    session.commit()


_SEPARATORS = re.compile(r"[\s_-]+")


def tag_key(name: str) -> str:
    """
    What a tag name reads as, for spotting likely duplicates only: letter case,
    separators (hyphens, underscores, runs of whitespace), surrounding space
    and one trailing plural "s" are set aside. Never applied to a stored name —
    names stay exactly as typed (ADR-0003).
    """
    key = _SEPARATORS.sub(" ", name).strip().lower()
    if key.endswith("s") and not key.endswith("ss") and len(key) > 3:
        key = key[:-1]
    return key


def _duplicate_signature(tags: Sequence[Tag]) -> str:
    members = sorted(f"{tag.id}:{tag.name}" for tag in tags)
    return hashlib.sha256("\n".join(members).encode()).hexdigest()


def get_tag_duplicate_groups(
    *, session: Session, owner_id: uuid.UUID
) -> list[list[Tag]]:
    """
    The user's tags that read as the same name, grouped, over the whole
    vocabulary. A group the user dismissed is left out for as long as it is
    exactly the group they dismissed.
    """
    tags = session.exec(select(Tag).where(Tag.owner_id == owner_id)).all()
    by_key: dict[str, list[Tag]] = {}
    for tag in tags:
        by_key.setdefault(tag_key(tag.name), []).append(tag)
    dismissed = set(
        session.exec(
            select(TagDuplicateDismissal.signature).where(
                TagDuplicateDismissal.owner_id == owner_id
            )
        ).all()
    )
    groups = [
        sorted(group, key=lambda tag: (tag.name.lower(), tag.name))
        for group in by_key.values()
        if len(group) > 1 and _duplicate_signature(group) not in dismissed
    ]
    return sorted(groups, key=lambda group: group[0].name.lower())


def dismiss_tag_duplicates(
    *, session: Session, owner_id: uuid.UUID, tags: Sequence[Tag]
) -> None:
    signature = _duplicate_signature(tags)
    exists = session.exec(
        select(TagDuplicateDismissal).where(
            TagDuplicateDismissal.owner_id == owner_id,
            TagDuplicateDismissal.signature == signature,
        )
    ).first()
    if exists is None:
        session.add(TagDuplicateDismissal(owner_id=owner_id, signature=signature))
        session.commit()


def tag_merge_counts(
    *, session: Session, owner_id: uuid.UUID, source_ids: Sequence[uuid.UUID]
) -> tuple[int, int]:
    """
    How many tasks carry any of `source_ids`, each counted once, as (live,
    archived). Deleted tasks are not counted, as a tag's own count leaves
    them out, though a merge moves them too.
    """
    archived = col(Task.id).in_(archived_task_ids(owner_id))
    carrying = (
        select(TaskTag.task_id)
        .where(col(TaskTag.tag_id).in_(source_ids))
        .distinct()
        .subquery()
    )
    live, archived_count = session.exec(
        select(func.count().filter(~archived), func.count().filter(archived)).where(
            Task.id == carrying.c.task_id,
            not_deleted(Task),
        )
    ).one()
    return live, archived_count


def merge_tags(*, session: Session, target: Tag, sources: Sequence[Tag]) -> None:
    """
    Fold `sources` into `target`: every task carrying a source carries the
    target instead — once, however many of the tags it had — and the sources
    are deleted. Deleted and archived tasks move too, so neither comes back
    later under a name that no longer exists.

    One commit, so a merge either happens whole or not at all
    (FR-01.27).
    """
    source_ids = [source.id for source in sources]
    carrying_target = set(
        session.exec(select(TaskTag.task_id).where(TaskTag.tag_id == target.id)).all()
    )
    links = session.exec(
        select(TaskTag).where(col(TaskTag.tag_id).in_(source_ids))
    ).all()
    for link in links:
        session.delete(link)
        if link.task_id not in carrying_target:
            session.add(TaskTag(task_id=link.task_id, tag_id=target.id))
            carrying_target.add(link.task_id)
    # The links go first: removing a tag takes its links with it in the
    # database, and the unit of work does not know to order them.
    session.flush()
    for source in sources:
        session.delete(source)
    session.commit()


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


class SubtaskCounts(NamedTuple):
    total: int
    done: int


def get_subtask_counts(
    *, session: Session, task_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, SubtaskCounts]:
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
    counts = dict.fromkeys(task_ids, SubtaskCounts(0, 0))
    for parent_id, total, done in session.exec(statement).all():
        if parent_id is not None:
            counts[parent_id] = SubtaskCounts(total, done)
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


def is_open(model: type[Task]) -> Any:
    """The filter for tasks that are not done (FR-01.4)."""
    return col(model.status) != TaskStatus.DONE


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
    (id, status) rows.

    Deleted subtasks are left out: they carry their own deletion event, and a
    deletion always takes a whole subtree, so nothing that is still there hides
    under a deleted one.
    """
    return _tree_walk(Task.parent_id == root_id, name="subtree")


def task_ancestry(
    *,
    owner_id: uuid.UUID,
    task_ids: Collection[uuid.UUID],
    including_deleted: bool = False,
) -> Any:
    """
    The one walk up the task tree: from each of `task_ids` to its root, as
    (task_id, parent_id, project_id) rows. The row whose `parent_id` is None
    carries the project the task resolves to (FR-02.4).

    The cost follows the tasks asked about and their depth, not the size of
    the account. A task that is deleted, or that hangs under a deleted
    ancestor, never reaches a root, which is how callers tell a live task from
    one that is gone. `including_deleted` walks through deleted tasks instead,
    for the one question that is asked about deleted tasks: where restoring
    them would bring them back to.
    """
    live: list[Any] = [] if including_deleted else [not_deleted(Task)]
    walk = (
        select(
            col(Task.id).label("task_id"),
            col(Task.parent_id).label("parent_id"),
            col(Task.project_id).label("project_id"),
        )
        .where(col(Task.id).in_(set(task_ids)), Task.owner_id == owner_id, *live)
        .cte("task_ancestry", recursive=True)
    )
    parent = aliased(Task)
    live_parent: list[Any] = [] if including_deleted else [not_deleted(parent)]
    return walk.union_all(
        select(walk.c.task_id, parent.parent_id, parent.project_id)
        .join(walk, col(parent.id) == walk.c.parent_id)
        .where(*live_parent)
    )


def get_task_project_ids(
    *,
    session: Session,
    owner_id: uuid.UUID,
    task_ids: Collection[uuid.UUID],
    including_deleted: bool = False,
) -> dict[uuid.UUID, uuid.UUID]:
    """
    The project each of `task_ids` belongs to, keyed by task id, in one
    `task_ancestry` walk. A task that is gone is left out, unless
    `including_deleted` asks about deleted tasks too.
    """
    if not task_ids:
        return {}
    walk = task_ancestry(
        owner_id=owner_id, task_ids=task_ids, including_deleted=including_deleted
    )
    rows = session.exec(
        select(walk.c.task_id, walk.c.project_id).where(walk.c.parent_id.is_(None))
    ).all()
    return dict(rows)


def get_project_task_counts(
    *,
    session: Session,
    owner_id: uuid.UUID,
    project_ids: Sequence[uuid.UUID] | None = None,
) -> dict[uuid.UUID, int]:
    """
    How many tasks resolve to each of a user's projects, keyed by project id,
    narrowed to `project_ids` where the caller only needs some of them.

    A subtask holds no project of its own, so the count follows each tree down
    from its root: what a project holds is its whole trees, not their tops
    (FR-02.4). Deleted tasks are not counted — the user cannot see them, and
    deleting the project again would be what brings them back into play.
    """
    roots: list[Any] = [
        Task.owner_id == owner_id,
        col(Task.parent_id).is_(None),
        not_deleted(Task),
    ]
    # Only the projects being reported: a panel showing one project has no use
    # for a walk over every tree in the account.
    if project_ids is not None:
        if not project_ids:
            return {}
        roots.append(col(Task.project_id).in_(project_ids))

    tree = _tree_walk(and_(*roots), name="project_task_counts")
    rows = session.exec(
        select(tree.c.project_id, func.count()).group_by(tree.c.project_id)
    ).all()
    return {project_id: count for project_id, count in rows if project_id}


def project_public(project: Project, task_count: int = 0) -> ProjectPublic:
    return ProjectPublic.model_validate(project, update={"task_count": task_count})


def has_open_subtasks(*, session: Session, task: Task) -> bool:
    """
    Whether anything under the task, at any depth, is still open.
    """
    subtree = _subtree_cte(task.id)
    statement = select(subtree.c.id).where(subtree.c.status != TaskStatus.DONE).limit(1)
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


def subtree_ids(root_id: uuid.UUID) -> Any:
    """Selects the ids of every live descendant of `root_id`."""
    return select(_subtree_cte(root_id).c.id)


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
    """
    return select(_tree_walk(root_condition, name=name).c.id)


def _tree_walk(start_condition: Any, *, name: str) -> Any:
    """
    The one walk down the task tree: the tasks matching `start_condition` and
    every task under them, leaving deleted ones out, as (id, status,
    project_id) rows. `project_id` is carried down from the starting task, so
    a walk that starts at root tasks says which project each row resolves to.

    Subtasks hold no project of their own, so the tasks of a project are only
    reachable by walking down from its root tasks. `name` names the CTE, which
    has to be unique among the ones a single statement uses.
    """
    tree = (
        select(Task.id, Task.status, Task.project_id)
        .where(start_condition, not_deleted(Task))
        .cte(name, recursive=True)
    )
    child = aliased(Task)
    return tree.union_all(
        select(child.id, child.status, tree.c.project_id)
        .join(tree, col(child.parent_id) == tree.c.id)
        .where(not_deleted(child))
    )


def complete_subtasks(*, session: Session, task: Task) -> None:
    """
    Move the task's whole subtree to done, leaving the task itself to the
    caller. Staged, not committed: the caller's update commits both together.
    """
    subtree = _subtree_cte(task.id)
    statement = select(Task).where(col(Task.id).in_(select(subtree.c.id)))
    for subtask in session.exec(statement):
        subtask.status = TaskStatus.DONE
        session.add(subtask)


def create_comment(
    *,
    session: Session,
    comment_create: CommentCreate,
    task_id: uuid.UUID,
    owner_id: uuid.UUID,
    author_bot_user_id: uuid.UUID | None = None,
) -> Comment:
    db_obj = Comment.model_validate(
        comment_create,
        update={
            "task_id": task_id,
            "owner_id": owner_id,
            "author_bot_user_id": author_bot_user_id,
        },
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


def create_bot_user(
    *, session: Session, bot_user_create: BotUserCreate, owner_id: uuid.UUID
) -> BotUser:
    permissions = bot_user_create.scope.permissions
    bot = BotUser(
        owner_id=owner_id,
        name=bot_user_create.name,
        **permissions.model_dump(),
    )
    session.add(bot)
    session.flush()
    for project_id in dict.fromkeys(bot_user_create.scope.project_ids):
        session.add(BotUserProject(bot_user_id=bot.id, project_id=project_id))
    session.commit()
    session.refresh(bot)
    return bot


def update_bot_user(
    *, session: Session, bot: BotUser, bot_user_update: BotUserUpdate
) -> BotUser:
    """
    Rename a bot user and replace its scope. Nothing about the bot user is
    cached anywhere, so its very next request is authorized against what is
    saved here (FR-08.6, FR-08.9).

    A deleted project stays in the scope it was in, out of sight: it drops out
    of what the bot user can reach while it is deleted, and restoring it puts
    it back as it was, whether or not the scope was edited in between.
    """
    if bot_user_update.name is not None:
        bot.name = bot_user_update.name
    scope = bot_user_update.scope
    if scope is not None:
        bot.sqlmodel_update(scope.permissions.model_dump())
        wanted = set(scope.project_ids)
        rows = session.exec(
            select(BotUserProject, Project.deletion_id).where(
                BotUserProject.bot_user_id == bot.id,
                BotUserProject.project_id == Project.id,
            )
        ).all()
        for row, deletion_id in rows:
            if deletion_id is None and row.project_id not in wanted:
                session.delete(row)
        held = {row.project_id for row, _ in rows}
        for project_id in dict.fromkeys(scope.project_ids):
            if project_id not in held:
                session.add(BotUserProject(bot_user_id=bot.id, project_id=project_id))
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def delete_bot_user(*, session: Session, bot: BotUser) -> None:
    """
    Mark a bot user deleted. The row stays, so its activity log entries, its
    comments and the tasks assigned to it keep naming it (FR-08.19, FR-08.21).
    Its token goes with it: authentication refuses a deleted bot user anyway
    (FR-08.20), and this way it holds no credential at all.
    """
    now = datetime.now(UTC)
    bot.deleted_at = now
    if bot.token_hash is not None:
        bot.token_hash = None
        bot.token_revoked_at = now
    session.add(bot)
    session.commit()


def get_bot_user_project_ids(
    *, session: Session, bot_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """
    The projects in each bot user's scope, keyed by bot user id. A deleted
    project is left out: the scope never points at anything the owner cannot
    see.
    """
    project_ids: dict[uuid.UUID, list[uuid.UUID]] = {bot_id: [] for bot_id in bot_ids}
    rows = session.exec(
        select(BotUserProject.bot_user_id, BotUserProject.project_id).where(
            col(BotUserProject.bot_user_id).in_(bot_ids),
            BotUserProject.project_id == Project.id,
            not_deleted(Project),
        )
    ).all()
    for bot_id, project_id in rows:
        project_ids[bot_id].append(project_id)
    return project_ids


def issue_bot_token(
    *, session: Session, bot: BotUser, expires_at: datetime | None = None
) -> str:
    """
    Issue a token for a bot user and return it. Only its digest is kept, so
    the caller's response is the one place the token is ever seen (FR-08.13).

    Everything about the previous token goes with it: a re-issued token starts
    unused, with its own expiry (FR-08.16).
    """
    token = generate_bot_token()
    bot.token_hash = hash_bot_token(token)
    bot.token_issued_at = datetime.now(UTC)
    bot.token_expires_at = expires_at
    bot.token_last_used_at = None
    bot.token_revoked_at = None
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return token


def revoke_bot_token(*, session: Session, bot: BotUser) -> BotUser:
    """
    Revoke a bot user's token. Its digest goes, so the token matches nothing
    from the next request on (FR-08.15), and the bot user holds no token until
    one is issued again.
    """
    bot.token_hash = None
    bot.token_revoked_at = datetime.now(UTC)
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def get_bot_user_refs(
    *, session: Session, bot_user_ids: Iterable[uuid.UUID | None]
) -> dict[uuid.UUID, BotUserRef]:
    """Bot users as tasks and comments name them, deleted ones included, by id."""
    ids = {bot_user_id for bot_user_id in bot_user_ids if bot_user_id}
    if not ids:
        return {}
    bots = session.exec(select(BotUser).where(col(BotUser.id).in_(ids))).all()
    return {
        bot.id: BotUserRef(id=bot.id, name=bot.name, deleted=bot.deleted_at is not None)
        for bot in bots
    }
