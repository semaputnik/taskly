import uuid
from typing import Any

from sqlalchemy.orm import aliased
from sqlmodel import Session, col, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    Task,
    TaskCreate,
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
    )
    return session.exec(statement).one()


def create_task(
    *,
    session: Session,
    task_create: TaskCreate,
    project_id: uuid.UUID | None,
    owner_id: uuid.UUID,
) -> Task:
    """
    Create a task. `project_id` is set on root tasks and None on subtasks,
    which derive their project from their root ancestor.
    """
    db_obj = Task.model_validate(
        task_create, update={"project_id": project_id, "owner_id": owner_id}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_task(*, session: Session, db_task: Task, task_in: TaskUpdate) -> Task:
    # `subtasks` directs what happens to the subtree (handled by the caller)
    # rather than naming a column, so it never reaches the row.
    task_data = task_in.model_dump(exclude_unset=True, exclude={"subtasks"})
    db_task.sqlmodel_update(task_data)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task


def _subtree_cte(root_id: uuid.UUID) -> Any:
    """
    Every descendant of `root_id`, to any depth, as (id, completed) rows.
    """
    subtree = (
        select(Task.id, Task.completed)
        .where(Task.parent_id == root_id)
        .cte("subtree", recursive=True)
    )
    child = aliased(Task)
    return subtree.union_all(
        select(child.id, child.completed).join(
            subtree, col(child.parent_id) == subtree.c.id
        )
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
        .where(Task.owner_id == owner_id, col(Task.parent_id).is_(None))
        .cte("task_projects", recursive=True)
    )
    child = aliased(Task)
    tree = tree.union_all(
        select(child.id, tree.c.project_id).join(
            tree, col(child.parent_id) == tree.c.id
        )
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
