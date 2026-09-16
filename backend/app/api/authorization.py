"""
The one authorization step for endpoints that bot users can reach.

A human caller passes straight through: owning the data is all a human needs,
and ownership is checked where the row is looked up. A bot caller is narrowed
here and nowhere else, always in the same order — the archive first, then the
scope's projects, then the permission — so a new bot-reachable endpoint gets
the whole rule by calling in, rather than re-deriving part of it.
"""

import uuid
from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app import crud
from app.api.deps import (
    PROJECT_ARCHIVED_CODE,
    Caller,
    get_project_of,
    get_task_of,
    require_task_visible,
)
from app.models import Attachment, Project, Task

# A bot refused by its scope gets a client error of its own, distinct from the
# 404 for something that does not exist, so whoever wrote the integration can
# tell a configuration problem from a wrong id (story 33). A bot only ever
# addresses its owner's data, so the difference reveals nothing across users.
BOT_REFUSED_STATUS = 403
OUTSIDE_SCOPE_CODE = "outside_scope"
PERMISSION_NOT_GRANTED_CODE = "permission_not_granted"


class TaskAction(StrEnum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    # Its own permission rather than a kind of update, so a bot can report on
    # a task without being able to change it (FR-08.10).
    COMMENT = "comment"


# The permission each action needs, as `BotPermissions` names it, and how a
# refusal says what was not allowed.
_PERMISSIONS = {
    TaskAction.CREATE: ("create_tasks", "create tasks"),
    TaskAction.READ: ("read_tasks", "read tasks"),
    TaskAction.UPDATE: ("update_tasks", "update tasks"),
    TaskAction.DELETE: ("delete_tasks", "delete tasks"),
    TaskAction.COMMENT: ("add_comments", "add comments"),
}


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


def authorize_project(caller: Caller, project: Project) -> None:
    """
    Refuse a bot the project itself: the archive first, then the scope.

    Reading a project is not reading its tasks — a bot that may only write
    still has to be able to resolve the project it writes into — so no task
    permission is consulted here (FR-08.9).
    """
    bot = caller.bot
    if bot is None:
        return
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
        authorize_project(caller, project)
    permission, doing = _PERMISSIONS[action]
    if not getattr(bot, permission):
        raise _refuse(
            PERMISSION_NOT_GRANTED_CODE,
            f"This bot user is not allowed to {doing}.",
            permission=permission,
        )


def authorize_tag_creation(caller: Caller) -> None:
    """
    Refuse a bot that is not allowed to create tags (FR-08.9). Applying tags
    the owner already has is part of writing the task and needs nothing here;
    bringing a tag into being is this permission.
    """
    bot = caller.bot
    if bot is not None and not bot.create_tags:
        raise _refuse(
            PERMISSION_NOT_GRANTED_CODE,
            "This bot user is not allowed to create tags.",
            permission="create_tags",
        )


def authorize_tag_names(
    session: Session, caller: Caller, names: Sequence[str] | None
) -> None:
    """
    Refuse a bot's request that puts names its owner has no tag for onto a
    task, before anything in it is applied.

    Which names were new comes back with the refusal, so an integration can
    send the rest rather than guess at the vocabulary it is allowed to add to
    (ADR-0003).

    The names are read here and written a moment later, so a tag the owner
    deletes in between is recreated by the write the check let through. The
    window is one request and costs one tag name; closing it would mean
    resolving names to tag ids here and teaching every write path to take
    ids, which is a lot of machinery for a bot user that was, after all,
    allowed to put that very name on the task a second earlier.
    """
    bot = caller.bot
    if bot is None or bot.create_tags or not names:
        return
    known = crud.get_tag_names(session=session, owner_id=caller.owner_id, names=names)
    new = [name for name in names if name not in known]
    if new:
        raise _refuse(
            PERMISSION_NOT_GRANTED_CODE,
            "This bot user is not allowed to create tags, and "
            + ", ".join(f"“{name}”" for name in new)
            + (" is not a tag yet." if len(new) == 1 else " are not tags yet."),
            permission="create_tags",
            tags=new,
        )


def get_project(
    session: Session,
    caller: Caller,
    project_id: uuid.UUID,
    action: TaskAction | None = TaskAction.READ,
) -> Project:
    """
    A project of the caller's, refused like `authorize_tasks` refuses anything
    in it when the caller is a bot. `action` of None asks for the project
    itself rather than for what may be done to the tasks in it.
    """
    project = get_project_of(session, caller.owner_id, project_id)
    if action is None:
        authorize_project(caller, project)
    else:
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


def get_attachment(
    session: Session, caller: Caller, attachment_id: uuid.UUID, action: TaskAction
) -> Attachment:
    """
    An attachment of the caller's, for `action` on the task it is on: a bot
    downloads what it can read and adds or removes what it can update
    (FR-08.11).
    """
    attachment = session.get(Attachment, attachment_id)
    if not attachment or attachment.owner_id != caller.owner_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    require_task_visible(session, attachment.task_id, "Attachment not found")
    get_task(session, caller, attachment.task_id, action)
    return attachment
