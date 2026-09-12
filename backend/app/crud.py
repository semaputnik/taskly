import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import aliased
from sqlmodel import Session, col, func, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    Deletion,
    Project,
    ProjectCreate,
    ProjectUpdate,
    Tag,
    Task,
    TaskCreate,
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
    which derive their project from their root ancestor.
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
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_task(*, session: Session, db_task: Task, task_in: TaskUpdate) -> Task:
    # `subtasks` directs what happens to the subtree (handled by the caller)
    # rather than naming a column, so it never reaches the row.
    task_data = task_in.model_dump(exclude_unset=True, exclude={"subtasks", "tags"})
    db_task.sqlmodel_update(task_data)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task


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


def set_task_tags(*, session: Session, task: Task, names: Sequence[str]) -> None:
    """
    Replace a task's tags with `names`, creating the ones the user has not used
    before (FR-01.20) and dropping any tag left on no task at all.
    """
    _stage_task_tags(session=session, task=task, names=names)
    session.commit()


def _stage_task_tags(*, session: Session, task: Task, names: Sequence[str]) -> None:
    """The tag work itself, staged but not committed, so a caller can put it in
    the same transaction as whatever else it is writing."""
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

    project_tasks = _project_tasks_cte(project.id)
    _mark_deleted(
        session=session, task_ids=select(project_tasks.c.id), deletion=deletion
    )
    project.deletion_id = deletion.id
    session.add(project)
    session.commit()


def _project_tasks_cte(project_id: uuid.UUID) -> Any:
    """
    Every task of a project that is not deleted: its root tasks and everything
    under them.
    """
    tasks = (
        select(Task.id)
        .where(Task.project_id == project_id, not_deleted(Task))
        .cte("project_tasks", recursive=True)
    )
    child = aliased(Task)
    return tasks.union_all(
        select(child.id)
        .join(tasks, col(child.parent_id) == tasks.c.id)
        .where(not_deleted(child))
    )


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
