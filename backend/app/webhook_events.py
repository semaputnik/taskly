"""
Where webhook events are recorded (FR-11.4 to FR-11.7).

Called from the activity log's commit hook (`app.activity`), which is the one
place that sees every change as a before and an after: an event is written to
the outbox in the transaction of the change that caused it, so it is never
lost to a crash between the two and never sent for a change that rolled back.

This module decides who is told and writes the rows; sending them is
`app.webhooks`.
"""

import uuid
from collections.abc import Collection, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import event, or_
from sqlalchemy.orm import Session
from sqlmodel import col, select

from app import crud, webhooks
from app.models import (
    BotUser,
    Comment,
    Project,
    Task,
    WebhookDelivery,
    WebhookEventType,
    WebhookKind,
)

_STAGED_KEY = "webhook_staged"


def _live_unarchived(session: Session, tasks: Sequence[Task]) -> dict[uuid.UUID, Task]:
    """
    The given tasks that are neither deleted nor in an archived project, or
    under a deleted or archived root (FR-11.7), by id.
    """
    by_owner: dict[uuid.UUID, list[Task]] = {}
    for task in tasks:
        by_owner.setdefault(task.owner_id, []).append(task)
    live: dict[uuid.UUID, Task] = {}
    for owner_id, owned in by_owner.items():
        walk = crud.task_ancestry(
            owner_id=owner_id, task_ids=[task.id for task in owned]
        )
        rows = session.execute(
            select(walk.c.task_id, walk.c.project_id).where(walk.c.parent_id.is_(None))
        ).all()
        project_ids: dict[uuid.UUID, uuid.UUID] = {
            row.task_id: row.project_id for row in rows
        }
        archived = set(
            session.scalars(
                select(Project.id).where(
                    col(Project.id).in_(set(project_ids.values())),
                    Project.is_archived == True,  # noqa: E712
                )
            )
        )
        live.update(
            {
                task.id: task
                for task in owned
                if task.id in project_ids and project_ids[task.id] not in archived
            }
        )
    return live


def _bots_with_url(
    session: Session, bot_ids: Collection[uuid.UUID], kind: WebhookKind
) -> dict[uuid.UUID, BotUser]:
    url = (
        col(BotUser.task_webhook_url)
        if kind is WebhookKind.TASK
        else col(BotUser.comment_webhook_url)
    )
    rows = session.scalars(
        select(BotUser).where(
            col(BotUser.id).in_(set(bot_ids)),
            col(BotUser.deleted_at).is_(None),
            url.is_not(None),
        )
    )
    return {bot.id: bot for bot in rows}


def _stage(session: Session, rows: list[WebhookDelivery]) -> None:
    if rows:
        session.add_all(rows)
        session.info[_STAGED_KEY] = True


def stage_events(
    session: Session,
    *,
    ready: Sequence[tuple[uuid.UUID, uuid.UUID]],
    comment_ids: Sequence[uuid.UUID],
    actor_bot_user_id: uuid.UUID | None,
) -> None:
    """
    Record the events this transaction caused.

    `ready` is every (task, bot user) pair where the task has just come to be
    in To do with that bot user as its assignee, by a change that was neither
    a restore nor an unarchive (FR-11.4, FR-11.5): the activity log has
    already told those apart. `comment_ids` are the comments added.

    The bot user that made the change is never told of it (FR-11.5), and a bot
    user that has not set the webhook is told nothing (FR-11.1).
    """
    now = datetime.now(UTC)
    rows: list[WebhookDelivery] = []

    pairs = [
        (task_id, bot_id) for task_id, bot_id in ready if bot_id != actor_bot_user_id
    ]
    if pairs:
        tasks = list(
            session.scalars(
                select(Task).where(col(Task.id).in_({task_id for task_id, _ in pairs}))
            )
        )
        live = _live_unarchived(session, tasks)
        bots = _bots_with_url(
            session, {bot_id for _, bot_id in pairs}, WebhookKind.TASK
        )
        for task_id, bot_id in pairs:
            task = live.get(task_id)
            bot = bots.get(bot_id)
            if task is None or bot is None or bot.owner_id != task.owner_id:
                continue
            rows.append(
                WebhookDelivery(
                    bot_user_id=bot_id,
                    webhook=WebhookKind.TASK.value,
                    event=WebhookEventType.TASK_READY.value,
                    occurred_at=now,
                    next_attempt_at=now,
                    task_id=task.id,
                    task_title=task.title,
                )
            )

    for comment_id in comment_ids:
        comment = session.get(Comment, comment_id)
        if comment is None:
            continue
        task = session.get(Task, comment.task_id)
        if task is None or task.id not in _live_unarchived(session, [task]):
            continue
        rows.extend(_comment_rows(session, comment, task, now))

    _stage(session, rows)


def _comment_rows(
    session: Session, comment: Comment, task: Task, now: datetime
) -> list[WebhookDelivery]:
    """
    One delivery for each bot user involved in the task other than the
    comment's own author (FR-11.6): its assignee or reporter, or one that has
    commented on it.
    """
    commenters = select(col(Comment.author_bot_user_id)).where(
        Comment.task_id == task.id, col(Comment.author_bot_user_id).is_not(None)
    )
    involved: list[Any] = [col(BotUser.id).in_(commenters)]
    if task.assignee_bot_user_id is not None:
        involved.append(col(BotUser.id) == task.assignee_bot_user_id)
    if task.reporter_bot_user_id is not None:
        involved.append(col(BotUser.id) == task.reporter_bot_user_id)
    bots = session.scalars(
        select(BotUser).where(
            BotUser.owner_id == task.owner_id,
            col(BotUser.deleted_at).is_(None),
            col(BotUser.comment_webhook_url).is_not(None),
            or_(*involved),
        )
    )
    return [
        WebhookDelivery(
            bot_user_id=bot.id,
            webhook=WebhookKind.COMMENT.value,
            event=WebhookEventType.COMMENT_ADDED.value,
            occurred_at=now,
            next_attempt_at=now,
            task_id=task.id,
            task_title=task.title,
            comment_id=comment.id,
        )
        for bot in bots
        if bot.id != comment.author_bot_user_id
    ]


@event.listens_for(Session, "after_commit")
def _wake(session: Session) -> None:
    # The first attempt is "at once" (FR-11.10): tell the loop, which would
    # otherwise find the row on its next look.
    if session.info.pop(_STAGED_KEY, None):
        webhooks.wake()


@event.listens_for(Session, "after_transaction_end")
def _forget(session: Session, transaction: Any) -> None:
    if transaction.parent is None and not transaction.nested:
        # Runs after `after_commit`, so a rolled-back transaction's rows are
        # forgotten without waking anyone.
        session.info.pop(_STAGED_KEY, None)
