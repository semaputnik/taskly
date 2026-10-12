"""
Attachments: files on a task, kept in Taskly or handed over to Paperless
(FR-04).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime
from sqlmodel import Field, SQLModel

from .paperless import PaperlessHandoverPublic
from .shared import get_datetime_utc


class AttachmentBase(SQLModel):
    filename: str = Field(max_length=255)
    content_type: str = Field(max_length=255)
    # A plain Integer caps out at 2 GiB, well within reach once
    # ATTACHMENT_MAX_SIZE_BYTES is raised for a deployment that wants larger
    # files.
    size: int = Field(sa_type=BigInteger)


class Attachment(AttachmentBase, table=True):
    """
    A file attached to a task (FR-04.1). Only the metadata lives here; the
    bytes sit behind the storage interface (ADR-0002), keyed by this row's
    id, so nothing here assumes where or how they are actually stored.

    Deleting the task this points at only soft-deletes the task (FR-01.8):
    this row and the bytes it names are left alone, so a restored task comes
    back with its files.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    task_id: uuid.UUID = Field(
        foreign_key="task.id", nullable=False, ondelete="CASCADE", index=True
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # The document in the owner's Paperless that holds this file, once it has
    # been handed over and Taskly has released its own copy (ADR-0010). Set
    # means the file is kept in Paperless and nowhere else; unset means the
    # bytes are in Taskly's storage.
    paperless_document_id: int | None = Field(
        default=None,
        sa_type=BigInteger,
    )


class AttachmentLocation(StrEnum):
    """Where an attachment is kept (FR-04.11)."""

    TASKLY = "taskly"
    PAPERLESS = "paperless"


class AttachmentPublic(AttachmentBase):
    id: uuid.UUID
    task_id: uuid.UUID
    created_at: datetime | None = None
    # Where the file is kept (FR-04.11).
    kept_in: AttachmentLocation = AttachmentLocation.TASKLY
    # For a file kept in Paperless: its document there, and the address of that
    # document. The address is null while the owner has no connection, which
    # is when the file is out of reach (FR-04.8).
    paperless_document_id: int | None = None
    paperless_url: str | None = None
    # Set while a PDF is being handed to Paperless, or when that failed.
    paperless_handover: PaperlessHandoverPublic | None = None


class AttachmentsPublic(SQLModel):
    data: list[AttachmentPublic]
    count: int
