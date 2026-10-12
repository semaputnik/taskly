"""
Reads over the activity log that answer a question about a task rather than
listing the log itself: who, if anyone, handed a task over by moving it into
Review.
"""

import uuid
from collections.abc import Collection
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import ARRAY, Text, and_, literal, or_
from sqlmodel import Session, col, select

from app.models import ActivityAction, ActivityEntityType, ActivityEntry, TaskStatus


class ReviewMove(NamedTuple):
    """The bot user that moved a task into Review, and when."""

    bot_user_id: uuid.UUID
    at: datetime


# Every entry that names one task and can say its status: a task filed in
# one, a move between open statuses, and a move into or out of done. A plain
# edit, an assignment or a restore leaves the status where it was, so it says
# nothing about how the task got there. Batches name their tasks in their
# details instead, and are matched there.
_STATUS_ACTIONS = (
    ActivityAction.TASK_CREATED,
    ActivityAction.TASK_STATUS_CHANGED,
    ActivityAction.TASK_REOPENED,
    ActivityAction.TASK_COMPLETED,
)


def _status_move(entry: ActivityEntry) -> tuple[list[str], str | None]:
    """
    The tasks `entry` set a status on, as the log writes their ids, and the
    status it left them in, or None if it set none. A batch names its tasks
    in its details; every other entry is about its own entity.
    """
    details = entry.details
    match entry.action:
        case ActivityAction.TASKS_BULK_CHANGED:
            changes = details.get("changes", {})
            return details.get("task_ids", []), changes.get("status")
        case ActivityAction.TASK_CREATED:
            status = details.get("task", {}).get("status")
        case ActivityAction.TASK_COMPLETED:
            status = TaskStatus.DONE
        case _:
            status = details.get("to")
    return [str(entry.entity_id)], status


def get_review_moves(
    *, session: Session, owner_id: uuid.UUID, task_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, ReviewMove]:
    """
    The hand-overs among the given tasks, keyed by task id: the bot user whose
    move put each one in Review, read off the activity log (ADR-0008). Pass
    only tasks that are in Review now.

    Only the latest move counts, so a task the owner moved out of Review and
    back again is the owner's, and one the owner moved there was handed over
    by nobody. A batch is always the owner's (the bulk endpoint is
    human-only), but it still counts as the latest move.
    """
    if not task_ids:
        return {}
    wanted = {str(task_id) for task_id in task_ids}
    statement = (
        select(ActivityEntry)
        .where(
            ActivityEntry.owner_id == owner_id,
            ActivityEntry.entity_type == ActivityEntityType.TASK,
            or_(
                and_(
                    col(ActivityEntry.action).in_(_STATUS_ACTIONS),
                    col(ActivityEntry.entity_id).in_(task_ids),
                ),
                and_(
                    col(ActivityEntry.action) == ActivityAction.TASKS_BULK_CHANGED,
                    col(ActivityEntry.details)["task_ids"].has_any(
                        literal(sorted(wanted), ARRAY(Text))
                    ),
                ),
            ),
        )
        .order_by(col(ActivityEntry.position).desc())
    )
    # Task ids as the log writes them, as text: a batch's are kept in JSON.
    latest: dict[str, tuple[ActivityEntry, str]] = {}
    for entry in session.exec(statement).all():
        named, status = _status_move(entry)
        if status is None:
            # A batch that changed something other than the status.
            continue
        for task_id in named:
            if task_id in wanted:
                latest.setdefault(task_id, (entry, status))

    return {
        uuid.UUID(task_id): ReviewMove(entry.actor_bot_user_id, entry.created_at)
        for task_id, (entry, status) in latest.items()
        if status == TaskStatus.REVIEW
        and entry.actor_bot_user_id is not None
        and entry.created_at is not None
    }
