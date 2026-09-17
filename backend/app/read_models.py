"""
Read models: records as the API shows them, assembled in one place.

A `TaskPublic` is more than its row: the project its tree resolves to, its
tags, its recurrence and its assignee all come from elsewhere. Every route
that returns tasks hands them here, so a field added to `TaskPublic` is added
once, and serialising a page of tasks costs a fixed number of queries however
many tasks it holds.
"""

import uuid
from collections.abc import Mapping, Sequence

from sqlmodel import Session

from app import crud
from app.models import Recurrence, Task, TaskPublic


def task_publics(
    session: Session,
    tasks: Sequence[Task],
    *,
    projects: Mapping[uuid.UUID, uuid.UUID] | None = None,
    recurrences: Mapping[uuid.UUID, Recurrence | None] | None = None,
) -> list[TaskPublic]:
    """
    `tasks` as the API shows them, in the order given.

    `projects` and `recurrences` are what the caller already resolved, keyed
    by task id — the project Task access walked up to, the recurrence an
    update already read — so they are not looked up a second time. Anything
    they leave out is looked up for all the tasks at once.
    """
    if not tasks:
        return []
    known_projects = dict(projects or {})
    if unresolved := [task.id for task in tasks if task.id not in known_projects]:
        known_projects.update(
            crud.get_task_project_ids(
                session=session, owner_id=tasks[0].owner_id, task_ids=unresolved
            )
        )
    known_recurrences = dict(recurrences or {})
    if unread := [task for task in tasks if task.id not in known_recurrences]:
        known_recurrences.update(crud.get_recurrences(session=session, tasks=unread))
    tags = crud.get_task_tags(session=session, task_ids=[task.id for task in tasks])
    bot_users = crud.get_bot_user_refs(
        session=session, bot_user_ids=[task.assignee_bot_user_id for task in tasks]
    )

    return [
        TaskPublic.model_validate(
            task,
            update={
                "project_id": known_projects[task.id],
                "tags": tags[task.id],
                "recurrence": known_recurrences[task.id],
                "assignee_id": task.assignee_id or task.assignee_bot_user_id,
                "assignee_bot_user": bot_users.get(task.assignee_bot_user_id)
                if task.assignee_bot_user_id
                else None,
            },
        )
        for task in tasks
    ]
