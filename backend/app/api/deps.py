import uuid
from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.core.storage import AttachmentStorage, LocalAttachmentStorage
from app.models import Attachment, Comment, Project, Task, TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except InvalidTokenError, ValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        # A token can outlive the account it names — the user was recreated
        # with a new id, or removed. That is a credentials problem, not a
        # missing resource: 401 lets the frontend's existing "clear the token
        # and go to /login" handling recover on its own, rather than getting
        # stuck replaying a 404 against every authenticated request.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def get_owned_project(
    session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Project:
    project = session.get(Project, project_id)
    if (
        not project
        or project.owner_id != current_user.id
        # A deleted project is invisible until it is restored (FR-05.8).
        or project.deletion_id is not None
    ):
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_owned_task(
    session: SessionDep, current_user: CurrentUser, task_id: uuid.UUID
) -> Task:
    task = session.get(Task, task_id)
    if not task or task.owner_id != current_user.id or task.deletion_id is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _require_task_visible(session: Session, task_id: uuid.UUID, detail: str) -> None:
    """
    A row that hangs off a task (a comment, an attachment) is only visible
    while its task is: once the task is soft-deleted, reading the row through
    the task is refused (`get_owned_task`), so reaching it directly has to be
    refused the same way.
    """
    task = session.get(Task, task_id)
    if not task or task.deletion_id is not None:
        raise HTTPException(status_code=404, detail=detail)


def get_owned_comment(
    session: SessionDep, current_user: CurrentUser, comment_id: uuid.UUID
) -> Comment:
    comment = session.get(Comment, comment_id)
    if not comment or comment.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Comment not found")
    _require_task_visible(session, comment.task_id, "Comment not found")
    return comment


def get_owned_attachment(
    session: SessionDep, current_user: CurrentUser, attachment_id: uuid.UUID
) -> Attachment:
    attachment = session.get(Attachment, attachment_id)
    if not attachment or attachment.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    _require_task_visible(session, attachment.task_id, "Attachment not found")
    return attachment


@lru_cache
def _local_attachment_storage() -> LocalAttachmentStorage:
    return LocalAttachmentStorage(Path(settings.ATTACHMENTS_DIR))


def get_attachment_storage() -> AttachmentStorage:
    return _local_attachment_storage()


AttachmentStorageDep = Annotated[AttachmentStorage, Depends(get_attachment_storage)]
