"""
The one authorization step for endpoints that bot users can reach.

A human caller passes straight through: owning the data is all a human needs,
and ownership is checked where the row is looked up. A bot caller is narrowed
here and nowhere else, always in the same order — the archive first, then the
scope's projects, then the permission — so a new bot-reachable endpoint gets
the whole rule by calling in, rather than re-deriving part of it.
"""

import uuid
from enum import StrEnum
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app import crud
from app.api.deps import PROJECT_ARCHIVED_CODE, Caller, get_project_of, get_task_of
from app.models import BotUser, Project, Task

# A bot refused by its scope gets a client error of its own, distinct from the
# 404 for something that does not exist, so whoever wrote the integration can
# tell a configuration problem from a wrong id (story 33). A bot only ever
# addresses its owner's data, so the difference reveals nothing across users.
BOT_REFUSED_STATUS = 403
OUTSIDE_SCOPE_CODE = "outside_scope"
PERMISSION_NOT_GRANTED_CODE = "permission_not_granted"
TAGS_READ_ONLY_CODE = "tags_read_only"


class TaskAction(StrEnum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"


def _granted(bot: BotUser, action: TaskAction) -> bool:
    grants = {
        TaskAction.CREATE: bot.create_tasks,
        TaskAction.READ: bot.read_tasks,
        TaskAction.UPDATE: bot.update_tasks,
        TaskAction.DELETE: bot.delete_tasks,
    }
    return grants[action]


def _refuse(code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=BOT_REFUSED_STATUS,
        detail={"code": code, "message": message, **extra},
    )


def refuse_archived_for_bot(caller: Caller) -> None:
    """
    Refuse a bot that asks for the archive: nothing in it is reachable by a
    bot, whatever its scope (FR-05.13).
    """
    if caller.bot is not None:
        raise _refuse(
            PROJECT_ARCHIVED_CODE, "Bot users have no access to archived projects."
        )


def authorize_tasks(
    caller: Caller, action: TaskAction, project: Project | None = None
) -> None:
    """
    Refuse a bot doing `action` on tasks — in `project`, or across its scope
    when there is no one project, as a listing is.

    The archive is checked before the scope is looked at, so no scope can add
    up to access to archived work (FR-05.13).
    """
    bot = caller.bot
    if bot is None:
        return
    if project is not None:
        if project.is_archived:
            raise _refuse(
                PROJECT_ARCHIVED_CODE,
                f"The project “{project.name}” is archived. Bot users have no "
                "access to archived projects.",
                project_id=str(project.id),
            )
        if project.id not in caller.project_ids:
            raise _refuse(
                OUTSIDE_SCOPE_CODE,
                f"The project “{project.name}” is not in this bot user's scope.",
                project_id=str(project.id),
            )
    if not _granted(bot, action):
        raise _refuse(
            PERMISSION_NOT_GRANTED_CODE,
            f"This bot user is not allowed to {action} tasks.",
            permission=f"{action}_tasks",
        )


def refuse_tag_changes_for_bot(caller: Caller, fields_set: set[str]) -> None:
    """
    Refuse a bot's request that sends tags, before anything in it is applied.

    What a tag permission would mean is still open (Q-16), so no bot can hold
    one yet: a bot reads the tags on tasks it can read, and changes none.
    """
    if caller.bot is not None and "tags" in fields_set:
        raise _refuse(
            TAGS_READ_ONLY_CODE,
            "Bot users cannot set or change tags. Send the request without `tags`.",
        )


def get_project(
    session: Session,
    caller: Caller,
    project_id: uuid.UUID,
    action: TaskAction = TaskAction.READ,
) -> Project:
    """
    A project the caller does `action` on tasks in, refused like
    `authorize_tasks` refuses anything in it when the caller is a bot.
    """
    project = get_project_of(session, caller.owner_id, project_id)
    authorize_tasks(caller, action, project)
    return project


def get_task(
    session: Session, caller: Caller, task_id: uuid.UUID, action: TaskAction
) -> Task:
    """
    A task of the caller's for `action`. Whether it exists is settled first, so
    a task that is not there — or is someone else's — is a 404 for a bot as
    much as for a human; only then does a bot's scope get a say, on the project
    the task's tree resolves to.
    """
    task = get_task_of(session, caller.owner_id, task_id)
    project = session.get_one(
        Project, crud.get_task_project_id(session=session, task=task)
    )
    authorize_tasks(caller, action, project)
    return task
