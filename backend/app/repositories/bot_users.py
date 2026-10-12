"""
Bot users: creating, updating and deleting one, the token it authenticates
with, and the projects and task counts attached to it. Its webhooks ride
along with it — a bot user deleted drops its webhooks too.
"""

import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlmodel import Session, col, func, select

from app.core.security import generate_bot_token, hash_bot_token
from app.models import (
    BotUser,
    BotUserCreate,
    BotUserProject,
    BotUserRef,
    BotUserUpdate,
    Project,
    Task,
    WebhookDelivery,
)

from .predicates import not_deleted


def create_bot_user(
    *, session: Session, bot_user_create: BotUserCreate, owner_id: uuid.UUID
) -> BotUser:
    permissions = bot_user_create.scope.permissions
    bot = BotUser(
        owner_id=owner_id,
        name=bot_user_create.name,
        **permissions.model_dump(),
    )
    session.add(bot)
    session.flush()
    for project_id in dict.fromkeys(bot_user_create.scope.project_ids):
        session.add(BotUserProject(bot_user_id=bot.id, project_id=project_id))
    session.commit()
    session.refresh(bot)
    return bot


def update_bot_user(
    *, session: Session, bot: BotUser, bot_user_update: BotUserUpdate
) -> BotUser:
    """
    Rename a bot user and replace its scope. Nothing about the bot user is
    cached anywhere, so its very next request is authorized against what is
    saved here (FR-08.6, FR-08.9).

    A deleted project stays in the scope it was in, out of sight: it drops out
    of what the bot user can reach while it is deleted, and restoring it puts
    it back as it was, whether or not the scope was edited in between.
    """
    if bot_user_update.name is not None:
        bot.name = bot_user_update.name
    scope = bot_user_update.scope
    if scope is not None:
        bot.sqlmodel_update(scope.permissions.model_dump())
        wanted = set(scope.project_ids)
        rows = session.exec(
            select(BotUserProject, Project.deletion_id).where(
                BotUserProject.bot_user_id == bot.id,
                BotUserProject.project_id == Project.id,
            )
        ).all()
        for row, deletion_id in rows:
            if deletion_id is None and row.project_id not in wanted:
                session.delete(row)
        held = {row.project_id for row, _ in rows}
        for project_id in dict.fromkeys(scope.project_ids):
            if project_id not in held:
                session.add(BotUserProject(bot_user_id=bot.id, project_id=project_id))
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def delete_bot_user(*, session: Session, bot: BotUser) -> None:
    """
    Mark a bot user deleted. The row stays, so its activity log entries, its
    comments and the tasks assigned to it keep naming it (FR-08.19, FR-08.21).
    Its token goes with it: authentication refuses a deleted bot user anyway
    (FR-08.20), and this way it holds no credential at all. So do its
    webhooks: the events still waiting for them are discarded and its
    deliveries end (FR-11.13).
    """
    now = datetime.now(UTC)
    bot.deleted_at = now
    if bot.token_hash is not None:
        bot.token_hash = None
        bot.token_revoked_at = now
    bot.task_webhook_url = None
    bot.comment_webhook_url = None
    bot.webhook_secret_encrypted = None
    session.exec(
        delete(WebhookDelivery).where(col(WebhookDelivery.bot_user_id) == bot.id)
    )
    session.add(bot)
    session.commit()


def get_bot_user_project_ids(
    *, session: Session, bot_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """
    The projects in each bot user's scope, keyed by bot user id. A deleted
    project is left out: the scope never points at anything the owner cannot
    see.
    """
    project_ids: dict[uuid.UUID, list[uuid.UUID]] = {bot_id: [] for bot_id in bot_ids}
    rows = session.exec(
        select(BotUserProject.bot_user_id, BotUserProject.project_id).where(
            col(BotUserProject.bot_user_id).in_(bot_ids),
            BotUserProject.project_id == Project.id,
            not_deleted(Project),
        )
    ).all()
    for bot_id, project_id in rows:
        project_ids[bot_id].append(project_id)
    return project_ids


def get_bot_user_assigned_task_counts(
    *, session: Session, bot_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """
    How many tasks name each bot user as their assignee, keyed by bot user id.
    Deleted tasks are not counted; archived ones are, as they still name it.
    """
    counts: dict[uuid.UUID, int] = dict.fromkeys(bot_ids, 0)
    rows = session.exec(
        select(Task.assignee_bot_user_id, func.count())
        .where(col(Task.assignee_bot_user_id).in_(bot_ids), not_deleted(Task))
        .group_by(col(Task.assignee_bot_user_id))
    ).all()
    for bot_id, count in rows:
        if bot_id is not None:
            counts[bot_id] = count
    return counts


def issue_bot_token(
    *, session: Session, bot: BotUser, expires_at: datetime | None = None
) -> str:
    """
    Issue a token for a bot user and return it. Only its digest is kept, so
    the caller's response is the one place the token is ever seen (FR-08.13).

    Everything about the previous token goes with it: a re-issued token starts
    unused, with its own expiry (FR-08.16).
    """
    token = generate_bot_token()
    bot.token_hash = hash_bot_token(token)
    bot.token_issued_at = datetime.now(UTC)
    bot.token_expires_at = expires_at
    bot.token_last_used_at = None
    bot.token_revoked_at = None
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return token


def revoke_bot_token(*, session: Session, bot: BotUser) -> BotUser:
    """
    Revoke a bot user's token. Its digest goes, so the token matches nothing
    from the next request on (FR-08.15), and the bot user holds no token until
    one is issued again.
    """
    bot.token_hash = None
    bot.token_revoked_at = datetime.now(UTC)
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot


def get_bot_user_refs(
    *, session: Session, bot_user_ids: Iterable[uuid.UUID | None]
) -> dict[uuid.UUID, BotUserRef]:
    """Bot users as tasks and comments name them, deleted ones included, by id."""
    ids = {bot_user_id for bot_user_id in bot_user_ids if bot_user_id}
    if not ids:
        return {}
    bots = session.exec(select(BotUser).where(col(BotUser.id).in_(ids))).all()
    return {
        bot.id: BotUserRef(id=bot.id, name=bot.name, deleted=bot.deleted_at is not None)
        for bot in bots
    }
