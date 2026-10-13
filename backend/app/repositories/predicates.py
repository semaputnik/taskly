"""
Predicates shared by more than one repository: the not-deleted and is-open
filters, the recursive walk down the task tree and the id queries built on
it, and the walk up the task tree to a root.

Everything here is a primitive several repositories genuinely need —
`not_deleted` is typed over task or project, and the tree walk serves task,
project and tag reads alike — so each lives here once rather than being
reached into across a repository boundary.
"""

import uuid
from collections.abc import Collection
from typing import Any

from sqlalchemy.orm import aliased
from sqlmodel import Session, col, select

from app.models import Project, Task, TaskStatus


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


def _fresh_cte_name(label: str) -> str:
    """
    A CTE name that cannot collide with another `tree_walk`'s: `label` for a
    reader, plus 32 hex digits no two calls ever share. A caller used to have
    to pick a name unique among the walks its own statement combines —
    `app/mcp/conventions.py` already combines two in `resolve_task_id` — and
    getting that wrong was a runtime SQL error two modules away from the
    mistake. Generating it here instead removes the chance of ever getting
    it wrong, at the cost of a name with no meaning beyond `label` to a human
    reading the compiled SQL.
    """
    return f"{label}_{uuid.uuid4().hex}"


def tree_walk(start_condition: Any, *, including_deleted: bool = False) -> Any:
    """
    The one walk down the task tree: the tasks matching `start_condition` and
    every task under them, as (id, status, project_id, due_date) rows.
    `project_id` is carried down from the starting task, so a walk that starts
    at root tasks says which project each row resolves to — true of a
    deleted root too, since nothing about deleting a task clears it.

    Leaves deleted tasks out unless `including_deleted` asks to walk through
    them: the activity log keeps a deleted task's history for ever (FR-10.4),
    so the one question it asks of this walk — which scope a task's entries
    belong to — has to resolve a deleted task exactly as it would a live one.

    Subtasks hold no project of their own, so the tasks of a project are only
    reachable by walking down from its root tasks. The CTE's own name is
    generated fresh by `_fresh_cte_name`, so nothing a caller does can make
    it collide with another walk the same statement combines.
    """
    live: list[Any] = [] if including_deleted else [not_deleted(Task)]
    tree = (
        select(Task.id, Task.status, col(Task.project_id), col(Task.due_date))
        .where(start_condition, *live)
        .cte(_fresh_cte_name("tree_walk"), recursive=True)
    )
    child = aliased(Task)
    live_child: list[Any] = [] if including_deleted else [not_deleted(child)]
    return tree.union_all(
        select(child.id, child.status, tree.c.project_id, col(child.due_date))
        .join(tree, col(child.parent_id) == tree.c.id)
        .where(*live_child)
    )


def subtree_cte(root_id: uuid.UUID) -> Any:
    """
    Every descendant of `root_id` that is not deleted, to any depth, as
    (id, status) rows.

    Deleted subtasks are left out: they carry their own deletion event, and a
    deletion always takes a whole subtree, so nothing that is still there hides
    under a deleted one.
    """
    return tree_walk(Task.parent_id == root_id)


def subtree_ids(root_id: uuid.UUID) -> Any:
    """Selects the ids of every live descendant of `root_id`."""
    return select(subtree_cte(root_id).c.id)


def _task_trees(root_condition: Any, *, including_deleted: bool = False) -> Any:
    """
    Selects the ids of the root tasks matching `root_condition` and of every
    task under them, leaving deleted ones out unless `including_deleted` asks
    to walk through them too.
    """
    return select(tree_walk(root_condition, including_deleted=including_deleted).c.id)


def project_task_ids(project_id: uuid.UUID) -> Any:
    """
    Selects the ids of every task of a project that is not deleted: its root
    tasks and everything under them.
    """
    return _task_trees(Task.project_id == project_id)


def tasks_in_projects(project_ids: Any, *, including_deleted: bool = False) -> Any:
    """
    Selects the ids of every task in any of `project_ids`: their root tasks
    and everything under them, in one walk rather than one walk per project —
    the many-project twin of `project_task_ids`, for a bot's task listing
    (narrowed to its scope) and its activity-log scope (spec #246), neither
    of which may OR one walk per project together. `project_ids` may be a
    selectable, the way `archived_task_ids` above takes one, so a scope
    already narrowed to its live projects is read once rather than twice.

    Leaves deleted tasks out unless `including_deleted` asks to walk through
    them too — the activity log needs to, since a deleted task's history
    still reads (FR-10.4).
    """
    return _task_trees(
        col(Task.project_id).in_(project_ids),
        including_deleted=including_deleted,
    )


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
    return _task_trees(col(Task.project_id).in_(archived_projects))


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
