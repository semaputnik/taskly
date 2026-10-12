"""
Operations over a comment (#275, #281): `comment`, the first and for now
only one — leaving a note on a task is the thinnest act this batch moves,
which is the point of moving it: after this, `app.mcp.tools.comment_task`
is argument translation and nothing else.

Lives in its own module, not `app.tasks`, the way the parent issue (#275)
settles it: a comment is its own aggregate (CONTEXT.md), not a task's own
property, even though every comment belongs to one.
"""

import uuid

from sqlmodel import Session

from app import activity, crud
from app.api import access
from app.api.access import TaskAction
from app.api.deps import Caller
from app.models import Comment, CommentCreate


def _set_actor(session: Session, caller: Caller) -> None:
    """
    Attribute whatever this transaction commits to the caller itself
    (FR-10.2): a bot user's comment is never recorded as its owner's.

    A near-duplicate of `app.tasks._set_actor` rather than a shared import
    of it: the two operation modules are siblings, and reaching into one
    private name from the other would be the same cross-module private
    reach this batch exists to remove, just moved rather than ended.
    """
    if caller.bot is not None:
        activity.set_bot_actor(session, caller.bot.id)
    else:
        activity.set_actor(session, caller.owner_id)


def comment(
    session: Session,
    caller: Caller,
    task_id: uuid.UUID,
    comment_in: CommentCreate,
) -> Comment:
    """
    Leave a comment on a task, including a subtask (FR-03.1).

    Decides access itself (`app.api.access.get_task`, `TaskAction.COMMENT`):
    a bot user needs the `add_comments` grant, not `update_tasks` — it can
    report on a task without being able to change it (FR-08.10).

    Append-only: this operation only ever adds a row. A comment a bot user
    wrote can never be edited or deleted by anyone, author included
    (FR-03.2, FR-08.10); nothing in this slice gives this module a
    counterpart that would change or remove one.
    """
    _set_actor(session, caller)
    access.get_task(session, caller, task_id, TaskAction.COMMENT)
    return crud.create_comment(
        session=session,
        comment_create=comment_in,
        task_id=task_id,
        owner_id=caller.owner_id,
        author_bot_user_id=caller.bot.id if caller.bot else None,
    )


__all__ = ["comment"]
