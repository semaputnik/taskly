"""
Projects: creating, updating and archiving one, what it holds broken down by
where its tasks stand, and how it is reported. A user account rides along
here too — creating one always creates its Inbox project in the same
transaction, and the account itself has no other repository to live in.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any, NamedTuple

from sqlalchemy import and_, case
from sqlmodel import Session, col, func, select

from app.models import (
    Project,
    ProjectCreate,
    ProjectPublic,
    ProjectUpdate,
    Task,
    TaskStatus,
    User,
    UserCreate,
    UserUpdate,
)

from .predicates import not_deleted, tree_walk


def create_user(
    *,
    session: Session,
    user_create: UserCreate,
    user_id: uuid.UUID | None = None,
    commit: bool = True,
) -> User:
    """
    Create a user and their Inbox. `user_id` is for registering, where the
    account's id is fixed before it exists: it is what the first passkey is
    made under. With `commit=False` the caller commits, so the account and
    its first passkey land together.
    """
    db_obj = User.model_validate(user_create)
    if user_id is not None:
        db_obj.id = user_id
    session.add(db_obj)
    # Flush so the user row exists before the FK-dependent Inbox insert, while
    # keeping both inserts in the same transaction as the eventual commit.
    session.flush()
    session.add(Project(name="Inbox", is_inbox=True, owner_id=db_obj.id))
    if commit:
        session.commit()
        session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    db_user.sqlmodel_update(user_data)
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


class ProjectTaskStats(NamedTuple):
    """What one project holds, by where its tasks stand."""

    total: int = 0
    open: int = 0
    overdue: int = 0
    backlog: int = 0
    review: int = 0
    done: int = 0


def get_project_task_stats(
    *,
    session: Session,
    owner_id: uuid.UUID,
    project_ids: Sequence[uuid.UUID] | None = None,
) -> dict[uuid.UUID, ProjectTaskStats]:
    """
    What each of a user's projects holds, keyed by project id, narrowed to
    `project_ids` where the caller only needs some of them.

    A subtask holds no project of its own, so the count follows each tree down
    from its root: what a project holds is its whole trees, not their tops
    (FR-02.4). Deleted tasks are not counted — the user cannot see them, and
    deleting the project again would be what brings them back into play.
    Open and overdue mean what they mean in the task list (FR-01.4), so the
    open count is the number of rows the list narrowed to the project shows.
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

    tree = tree_walk(and_(*roots), name="project_task_counts")
    open_task = tree.c.status != TaskStatus.DONE

    def counted(*conditions: Any) -> Any:
        return func.count(case((and_(*conditions), 1))) if conditions else func.count()

    columns: list[Any] = [
        tree.c.project_id,
        counted(),
        counted(open_task),
        counted(open_task, tree.c.due_date < date.today()),
        counted(tree.c.status == TaskStatus.BACKLOG),
        counted(tree.c.status == TaskStatus.REVIEW),
        counted(tree.c.status == TaskStatus.DONE),
    ]
    rows = session.exec(select(*columns).group_by(tree.c.project_id)).all()
    return {row[0]: ProjectTaskStats(*row[1:]) for row in rows if row[0]}


def project_public(
    project: Project, stats: ProjectTaskStats | None = None
) -> ProjectPublic:
    stats = stats or ProjectTaskStats()
    return ProjectPublic.model_validate(
        project,
        update={
            "task_count": stats.total,
            "open_count": stats.open,
            "overdue_count": stats.overdue,
            "backlog_count": stats.backlog,
            "review_count": stats.review,
            "done_count": stats.done,
        },
    )
