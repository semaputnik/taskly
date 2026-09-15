import uuid
from typing import Any

from fastapi import APIRouter

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_owned_comment,
    get_owned_task,
    require_task_writable,
)
from app.models import (
    CommentCreate,
    CommentPublic,
    CommentsPublic,
    CommentUpdate,
    Message,
)

router = APIRouter(tags=["comments"])


@router.get("/tasks/{task_id}/comments/", response_model=CommentsPublic)
def read_comments(
    *, session: SessionDep, current_user: CurrentUser, task_id: uuid.UUID
) -> Any:
    """
    Retrieve a task's comments, oldest first, so the thread reads as a
    narrative (FR-03.1).
    """
    get_owned_task(session, current_user, task_id)
    comments, count = crud.get_comments(session=session, task_id=task_id)
    return CommentsPublic(data=comments, count=count)


@router.post("/tasks/{task_id}/comments/", response_model=CommentPublic)
def create_comment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    task_id: uuid.UUID,
    comment_in: CommentCreate,
) -> Any:
    """
    Add a comment to a task, including a subtask (FR-03.1).
    """
    get_owned_task(session, current_user, task_id)
    require_task_writable(session, task_id)
    return crud.create_comment(
        session=session,
        comment_create=comment_in,
        task_id=task_id,
        owner_id=current_user.id,
    )


@router.patch("/comments/{comment_id}", response_model=CommentPublic)
def update_comment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    comment_id: uuid.UUID,
    comment_in: CommentUpdate,
) -> Any:
    """
    Edit a comment. A user can only edit their own (FR-03.2).
    """
    comment = get_owned_comment(session, current_user, comment_id)
    require_task_writable(session, comment.task_id)
    return crud.update_comment(
        session=session, db_comment=comment, comment_in=comment_in
    )


@router.delete("/comments/{comment_id}")
def delete_comment(
    *, session: SessionDep, current_user: CurrentUser, comment_id: uuid.UUID
) -> Message:
    """
    Delete a comment. A user can only delete their own (FR-03.2).
    """
    comment = get_owned_comment(session, current_user, comment_id)
    require_task_writable(session, comment.task_id)
    crud.delete_comment(session=session, comment=comment)
    return Message(message="Comment deleted successfully")
