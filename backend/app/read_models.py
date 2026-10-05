"""
Read models: records as the API shows them, assembled in one place.

A `TaskPublic` is more than its row: the project its tree resolves to, its
tags, its recurrence, its assignee and its subtask counts all come from elsewhere. Every route
that returns tasks hands them here, so a field added to `TaskPublic` is added
once, and serialising a page of tasks costs a fixed number of queries however
many tasks it holds.
"""

import uuid
from collections.abc import Mapping, Sequence

from sqlmodel import Session

from app import crud
from app.models import (
    BotUserRef,
    Recurrence,
    Task,
    TaskHandover,
    TaskPublic,
    TaskStatus,
)


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
    subtasks = crud.get_subtask_counts(
        session=session, task_ids=[task.id for task in tasks]
    )
    # Only a task in Review can have been handed over, so a page without one
    # does not read the log at all.
    handovers = crud.get_review_moves(
        session=session,
        owner_id=tasks[0].owner_id,
        task_ids=[task.id for task in tasks if task.status is TaskStatus.REVIEW],
    )
    # Every bot-user reference in one lookup: a task can name one bot user as
    # its assignee, another as the one that filed it and a third as the one
    # that handed it over, and asking per role would cost a query per role
    # rather than per page.
    bot_users = crud.get_bot_user_refs(
        session=session,
        bot_user_ids=[
            *(
                bot_user_id
                for task in tasks
                for bot_user_id in (
                    task.assignee_bot_user_id,
                    task.reporter_bot_user_id,
                )
            ),
            *(move.bot_user_id for move in handovers.values()),
        ],
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
                "reporter_id": task.reporter_id or task.reporter_bot_user_id,
                "reporter_bot_user": bot_users.get(task.reporter_bot_user_id)
                if task.reporter_bot_user_id
                else None,
                "subtask_count": subtasks[task.id].total,
                "subtasks_done": subtasks[task.id].done,
                "handover": _handover(handovers.get(task.id), bot_users),
            },
        )
        for task in tasks
    ]


def _handover(
    move: crud.ReviewMove | None, bot_users: Mapping[uuid.UUID, BotUserRef]
) -> TaskHandover | None:
    if move is None or move.bot_user_id not in bot_users:
        return None
    return TaskHandover(bot_user=bot_users[move.bot_user_id], at=move.at)
