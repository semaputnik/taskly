"""
Task access: whether this caller may do this to this task, decided in one
place.

A route asks one question — this task (or these tasks, or the row hanging off
one), for this caller, to do this action — and gets back the task with the
project it resolves to, or the refusal the API gives. Behind the question:

- **ownership:** the task is the caller's owner's;
- **liveness:** neither the task nor any task above it is deleted;
- **root project:** a subtask holds no project, so the tree is walked up once
  to the root task's (FR-02.4);
- **archive:** a bot never reaches an archived project (FR-05.13), a human
  only reads it (FR-05.12);
- **scope:** a bot is narrowed to the projects and permissions of its scope,
  always in the same order — the archive first, then the projects, then the
  permission (FR-08.8, FR-08.9).

The differences between the refusals are deliberate. Something missing is a
404 for a bot as much as for a human. A bot refused by its scope gets a 403 of
its own, so whoever wrote the integration can tell a configuration problem
from a wrong id (story 33). A human writing into the archive gets a 409 that
says what would undo it.
"""

import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app import crud
from app.api.deps import Caller
from app.models import Attachment, Comment, Project, Task, TaskRefusal

BOT_REFUSED_STATUS = 403
OUTSIDE_SCOPE_CODE = "outside_scope"
PERMISSION_NOT_GRANTED_CODE = "permission_not_granted"

# Writing into an archived project is refused with its own status and code
# rather than a generic permission error, so a client can tell the user why
# and what would undo it (FR-05.12).
PROJECT_ARCHIVED_STATUS = 409
PROJECT_ARCHIVED_CODE = "project_archived"

# What a bot user said stays on the record: its comments are append-only for
# everyone, its owner included (FR-03.2, FR-08.10).
COMMENT_BY_BOT_STATUS = 403
COMMENT_BY_BOT_CODE = "comment_by_bot"

TASK_NOT_FOUND = "Task not found"


class TaskAction(StrEnum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    # Its own permission rather than a kind of update, so a bot can report on
    # a task without being able to change it (FR-08.10).
    COMMENT = "comment"

    @property
    def writes(self) -> bool:
        """Whether the action changes the task's project, which the archive forbids."""
        return self is not TaskAction.READ


# The permission each action needs, as `BotPermissions` names it, and how a
# refusal says what was not allowed.
_PERMISSIONS = {
    TaskAction.CREATE: ("create_tasks", "create tasks"),
    TaskAction.READ: ("read_tasks", "read tasks"),
    TaskAction.UPDATE: ("update_tasks", "update tasks"),
    TaskAction.DELETE: ("delete_tasks", "delete tasks"),
    TaskAction.COMMENT: ("add_comments", "add comments"),
}


@dataclass(frozen=True)
class TaskAccess:
    """A task the caller may act on, and the project its tree resolves to."""

    task: Task
    project: Project


def _refuse(code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=BOT_REFUSED_STATUS,
        detail={"code": code, "message": message, **extra},
    )


# Bots


def refuse_archived_for_bot(caller: Caller) -> None:
    """
    Refuse a bot that asks for the archive: nothing in it is reachable by a
    bot, whatever its scope (FR-05.13).
    """
    if caller.bot is not None:
        raise _refuse(
            PROJECT_ARCHIVED_CODE, "Bot users have no access to archived projects."
        )


def _bot_project_refusal(caller: Caller, project: Project) -> tuple[str, str] | None:
    """
    Why the caller, if it is a bot, may not reach `project` at all — the
    archive, then the scope — as a code and a message.
    """
    if caller.bot is None:
        return None
    if project.is_archived:
        return (
            PROJECT_ARCHIVED_CODE,
            f"The project “{project.name}” is archived. Bot users have no "
            "access to archived projects.",
        )
    if project.id not in caller.project_ids:
        return (
            OUTSIDE_SCOPE_CODE,
            f"The project “{project.name}” is not in this bot user's scope.",
        )
    return None


def _refuse_bot_project(caller: Caller, project: Project) -> None:
    if refusal := _bot_project_refusal(caller, project):
        code, message = refusal
        raise _refuse(code, message, project_id=str(project.id))


def _refuse_permission(caller: Caller, action: TaskAction) -> None:
    bot = caller.bot
    if bot is None:
        return
    permission, doing = _PERMISSIONS[action]
    if not getattr(bot, permission):
        raise _refuse(
            PERMISSION_NOT_GRANTED_CODE,
            f"This bot user is not allowed to {doing}.",
            permission=permission,
        )


def authorize_tasks(caller: Caller, action: TaskAction) -> None:
    """
    Refuse a bot doing `action` across its scope, where there is no one
    project to check, as a listing is.
    """
    _refuse_permission(caller, action)


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


# Projects


def archived_refusal(project: Project) -> HTTPException:
    """How a change to an archived project, or to anything in it, is refused."""
    return HTTPException(
        status_code=PROJECT_ARCHIVED_STATUS,
        detail={
            "code": PROJECT_ARCHIVED_CODE,
            "message": (
                f"The project “{project.name}” is archived, so it and its "
                "tasks are read-only. Unarchive it to make changes."
            ),
            "project_id": str(project.id),
        },
    )


def require_project_writable(project: Project) -> None:
    """
    Refuse any change to an archived project or to anything in it: archiving
    freezes the project whole until it is unarchived (FR-05.12).
    """
    if project.is_archived:
        raise archived_refusal(project)


def _authorize(caller: Caller, action: TaskAction, project: Project) -> None:
    """Refuse `action` on tasks in `project`, for a bot and then for anyone."""
    _refuse_bot_project(caller, project)
    _refuse_permission(caller, action)
    if action.writes:
        require_project_writable(project)


def get_project(
    session: Session,
    caller: Caller,
    project_id: uuid.UUID,
    action: TaskAction | None = TaskAction.READ,
) -> Project:
    """
    A project of the caller's, for `action` on the tasks in it. `action` of
    None asks for the project itself: reading a project is not reading its
    tasks — a bot that may only write still has to be able to resolve the
    project it writes into (FR-08.9) — and archiving, unarchiving or deleting
    a project is not writing into it.
    """
    project = session.get(Project, project_id)
    if (
        not project
        or project.owner_id != caller.owner_id
        # A deleted project is invisible until it is restored (FR-05.8).
        or project.deletion_id is not None
    ):
        raise HTTPException(status_code=404, detail="Project not found")
    if action is not None:
        _authorize(caller, action, project)
    else:
        _refuse_bot_project(caller, project)
    return project


# Tasks


def _resolve(
    session: Session, owner_id: uuid.UUID, task_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, TaskAccess]:
    """
    The live tasks of the owner among `task_ids`, each with its root project,
    in one walk up the tree and one statement.
    """
    if not task_ids:
        return {}
    walk = crud.task_ancestry(owner_id=owner_id, task_ids=task_ids)
    rows = session.exec(
        select(Task, Project)
        .join(walk, col(Task.id) == walk.c.task_id)
        .join(Project, col(Project.id) == walk.c.project_id)
        .where(walk.c.parent_id.is_(None))
    ).all()
    return {task.id: TaskAccess(task=task, project=project) for task, project in rows}


def _live_task(
    session: Session, caller: Caller, task_id: uuid.UUID, not_found: str
) -> TaskAccess:
    """
    The task, if it is the caller's and still there. Settled before anything
    else, so a task that is not there — or is someone else's — is a 404 for a
    bot as much as for a human.
    """
    resolved = _resolve(session, caller.owner_id, [task_id]).get(task_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=not_found)
    return resolved


def get_task(
    session: Session, caller: Caller, task_id: uuid.UUID, action: TaskAction
) -> TaskAccess:
    """A task of the caller's for `action`, with the project it resolves to."""
    resolved = _live_task(session, caller, task_id, TASK_NOT_FOUND)
    _authorize(caller, action, resolved.project)
    return resolved


def get_tasks(
    session: Session,
    caller: Caller,
    task_ids: Sequence[uuid.UUID],
    action: TaskAction,
) -> tuple[list[TaskAccess], list[TaskRefusal]]:
    """
    The tasks among those named that the caller may act on, in the order they
    were named and each once, and a refusal for each of the rest — the shape a
    batch reports (story 29).

    A task somebody else owns is refused exactly like one that does not exist:
    the batch says nothing about whose it is. A permission the bot lacks is
    not about any one task, so it refuses the whole request.
    """
    _refuse_permission(caller, action)
    unique = list(dict.fromkeys(task_ids))
    live = _resolve(session, caller.owner_id, unique)

    resolved: list[TaskAccess] = []
    missing: list[TaskRefusal] = []
    refused: list[TaskRefusal] = []
    for task_id in unique:
        access = live.get(task_id)
        if access is None:
            missing.append(
                TaskRefusal(
                    task_id=task_id,
                    code="not_found",
                    message="This task is not there any more.",
                )
            )
        elif refusal := _batch_refusal(caller, action, access):
            refused.append(refusal)
        else:
            resolved.append(access)
    return resolved, missing + refused


def _batch_refusal(
    caller: Caller, action: TaskAction, access: TaskAccess
) -> TaskRefusal | None:
    task, project = access.task, access.project
    if refusal := _bot_project_refusal(caller, project):
        code, message = refusal
        return TaskRefusal(task_id=task.id, code=code, message=message)
    if action.writes and project.is_archived:
        return TaskRefusal(
            task_id=task.id,
            code=PROJECT_ARCHIVED_CODE,
            message=(
                f"“{task.title}” is in the archived project “{project.name}”, "
                "which is read-only."
            ),
        )
    return None


# Rows hanging off a task


def get_comment(
    session: Session, caller: Caller, comment_id: uuid.UUID, action: TaskAction
) -> Comment:
    """
    A comment of the caller's, for `action` on the task it is on. A comment
    is only there while its task is. Changing one a bot user wrote is refused
    for everyone (FR-03.2, FR-08.10).
    """
    not_found = "Comment not found"
    comment = session.get(Comment, comment_id)
    if not comment or comment.owner_id != caller.owner_id:
        raise HTTPException(status_code=404, detail=not_found)
    resolved = _live_task(session, caller, comment.task_id, not_found)
    if action.writes and comment.author_bot_user_id is not None:
        raise HTTPException(
            status_code=COMMENT_BY_BOT_STATUS,
            detail={
                "code": COMMENT_BY_BOT_CODE,
                "message": (
                    "This comment was written by a bot user. Comments from bot "
                    "users cannot be edited or deleted."
                ),
            },
        )
    _authorize(caller, action, resolved.project)
    return comment


def get_attachment(
    session: Session, caller: Caller, attachment_id: uuid.UUID, action: TaskAction
) -> Attachment:
    """
    An attachment of the caller's, for `action` on the task it is on: a bot
    downloads what it can read and adds or removes what it can update
    (FR-08.11). An attachment is only there while its task is.
    """
    not_found = "Attachment not found"
    attachment = session.get(Attachment, attachment_id)
    if not attachment or attachment.owner_id != caller.owner_id:
        raise HTTPException(status_code=404, detail=not_found)
    resolved = _live_task(session, caller, attachment.task_id, not_found)
    _authorize(caller, action, resolved.project)
    return attachment
