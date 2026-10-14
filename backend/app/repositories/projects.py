"""
Projects: creating, updating and archiving one, what it holds broken down by
where its tasks stand, and how it is reported.
"""

import uuid
from collections.abc import Collection, Sequence
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
)

from .predicates import not_deleted, tree_walk


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


def project_list_statement(
    *,
    owner_id: uuid.UUID,
    archived: bool,
    project_ids: Collection[uuid.UUID] | None = None,
) -> Any:
    """
    The owner's projects matching `archived`, Inbox first then by name
    ignoring case, with the id to settle a shared name — the one order every
    project list uses (FR-05.14). `project_ids` narrows further, for the one
    caller that is itself narrowed to a scope (FR-08.6, FR-05.13); `None`
    reads every one of the owner's that matches `archived`.

    Shared by the project list and a bot's scope list in `GET /caller`, so
    the two cannot drift apart the way they once did (issue #264) — a caller
    that only wants the whole result applies no `.offset()`/`.limit()`, and
    may run `select(func.count()).select_from(statement.subquery())` for a
    count over the same conditions.
    """
    conditions: list[Any] = [
        Project.owner_id == owner_id,
        not_deleted(Project),
        Project.is_archived == archived,
    ]
    if project_ids is not None:
        conditions.append(col(Project.id).in_(project_ids))
    return (
        select(Project)
        .where(*conditions)
        .order_by(
            col(Project.is_inbox).desc(),
            func.lower(Project.name),
            col(Project.id),
        )
    )


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

    tree = tree_walk(and_(*roots))
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
