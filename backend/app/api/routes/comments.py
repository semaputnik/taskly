import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api import authorization
from app.api.authorization import TaskAction
from app.api.deps import (
    CallerDep,
    CurrentUser,
    SessionDep,
    get_owned_comment,
    require_task_writable,
)
from app.models import (
    Comment,
    CommentCreate,
    CommentPublic,
    CommentsPublic,
    CommentUpdate,
    Message,
)

router = APIRouter(tags=["comments"])

# What a bot user said stays on the record: its comments are append-only for
# everyone, its owner included (FR-03.2, FR-08.10). Editing and deleting also
# take a human caller, so a bot user cannot reach them at all.
COMMENT_BY_BOT_STATUS = 403
COMMENT_BY_BOT_CODE = "comment_by_bot"


def _public(session: SessionDep, comments: Sequence[Comment]) -> list[CommentPublic]:
    authors = crud.get_bot_user_refs(
        session=session,
        bot_user_ids=[comment.author_bot_user_id for comment in comments],
    )
    return [
        CommentPublic.model_validate(
            comment,
            update={
                "author_bot_user": authors.get(comment.author_bot_user_id)
                if comment.author_bot_user_id
                else None
            },
        )
        for comment in comments
    ]


def _refuse_if_by_bot(comment: Comment) -> None:
    if comment.author_bot_user_id is not None:
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


@router.get("/tasks/{task_id}/comments/", response_model=CommentsPublic)
def read_comments(*, session: SessionDep, caller: CallerDep, task_id: uuid.UUID) -> Any:
    """
    Retrieve a task's comments, oldest first, so the thread reads as a
    narrative (FR-03.1). A bot user reads them wherever it can read the task.
    """
    authorization.get_task(session, caller, task_id, TaskAction.READ)
    comments, count = crud.get_comments(session=session, task_id=task_id)
    return CommentsPublic(data=_public(session, comments), count=count)


@router.post("/tasks/{task_id}/comments/", response_model=CommentPublic)
def create_comment(
    *,
    session: SessionDep,
    caller: CallerDep,
    task_id: uuid.UUID,
    comment_in: CommentCreate,
) -> Any:
    """
    Add a comment to a task, including a subtask (FR-03.1).

    A bot user needs the add-comments permission, and not update on tasks: it
    can report on a task without being able to change it (FR-08.10).
    """
    authorization.get_task(session, caller, task_id, TaskAction.COMMENT)
    require_task_writable(session, task_id)
    comment = crud.create_comment(
        session=session,
        comment_create=comment_in,
        task_id=task_id,
        owner_id=caller.owner_id,
        author_bot_user_id=caller.bot.id if caller.bot else None,
    )
    return _public(session, [comment])[0]


@router.patch("/comments/{comment_id}", response_model=CommentPublic)
def update_comment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    comment_id: uuid.UUID,
    comment_in: CommentUpdate,
) -> Any:
    """
    Edit a comment. A user can only edit their own (FR-03.2): not one a bot
    user wrote.
    """
    comment = get_owned_comment(session, current_user, comment_id)
    _refuse_if_by_bot(comment)
    require_task_writable(session, comment.task_id)
    comment = crud.update_comment(
        session=session, db_comment=comment, comment_in=comment_in
    )
    return _public(session, [comment])[0]


@router.delete("/comments/{comment_id}")
def delete_comment(
    *, session: SessionDep, current_user: CurrentUser, comment_id: uuid.UUID
) -> Message:
    """
    Delete a comment. A user can only delete their own (FR-03.2): not one a
    bot user wrote.
    """
    comment = get_owned_comment(session, current_user, comment_id)
    _refuse_if_by_bot(comment)
    require_task_writable(session, comment.task_id)
    crud.delete_comment(session=session, comment=comment)
    return Message(message="Comment deleted successfully")
