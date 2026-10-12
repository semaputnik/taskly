"""
Comments and attachments on a task: creating, reading, updating and deleting
either. Grouped together rather than split in two because neither reaches
into the other or into anything outside itself.
"""

import uuid
from collections.abc import Sequence

from sqlmodel import Session, col, select

from app.models import Attachment, Comment, CommentCreate, CommentUpdate


def create_comment(
    *,
    session: Session,
    comment_create: CommentCreate,
    task_id: uuid.UUID,
    owner_id: uuid.UUID,
    author_bot_user_id: uuid.UUID | None = None,
) -> Comment:
    db_obj = Comment.model_validate(
        comment_create,
        update={
            "task_id": task_id,
            "owner_id": owner_id,
            "author_bot_user_id": author_bot_user_id,
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_comments(
    *, session: Session, task_id: uuid.UUID
) -> tuple[Sequence[Comment], int]:
    """
    A task's comments, oldest first, so the thread reads as a narrative
    (FR-03.1) rather than a feed.
    """
    statement = (
        select(Comment)
        .where(Comment.task_id == task_id)
        .order_by(col(Comment.created_at))
    )
    comments = session.exec(statement).all()
    return comments, len(comments)


def update_comment(
    *, session: Session, db_comment: Comment, comment_in: CommentUpdate
) -> Comment:
    comment_data = comment_in.model_dump(exclude_unset=True)
    db_comment.sqlmodel_update(comment_data)
    session.add(db_comment)
    session.commit()
    session.refresh(db_comment)
    return db_comment


def delete_comment(*, session: Session, comment: Comment) -> None:
    session.delete(comment)
    session.commit()


def create_attachment(
    *,
    session: Session,
    task_id: uuid.UUID,
    owner_id: uuid.UUID,
    filename: str,
    content_type: str,
    size: int,
) -> Attachment:
    db_obj = Attachment(
        task_id=task_id,
        owner_id=owner_id,
        filename=filename,
        content_type=content_type,
        size=size,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_attachments(
    *, session: Session, task_id: uuid.UUID
) -> tuple[Sequence[Attachment], int]:
    statement = (
        select(Attachment)
        .where(Attachment.task_id == task_id)
        .order_by(col(Attachment.created_at))
    )
    attachments = session.exec(statement).all()
    return attachments, len(attachments)


def get_owner_attachment_ids(
    *, session: Session, owner_id: uuid.UUID
) -> Sequence[uuid.UUID]:
    """
    Every attachment id a user owns, so their bytes can be released from
    storage before the account's rows are gone — deleting the user cascades
    at the database level (FK `ondelete=CASCADE`), which drops these rows
    without ever calling into the storage backend.
    """
    statement = select(Attachment.id).where(Attachment.owner_id == owner_id)
    return session.exec(statement).all()


def delete_attachment(*, session: Session, attachment: Attachment) -> None:
    session.delete(attachment)
    session.commit()
