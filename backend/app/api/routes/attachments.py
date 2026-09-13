import uuid
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response

from app import crud
from app.api.deps import (
    AttachmentStorageDep,
    CurrentUser,
    SessionDep,
    get_owned_attachment,
    get_owned_task,
)
from app.core.config import settings
from app.models import AttachmentPublic, AttachmentsPublic, Message

router = APIRouter(tags=["attachments"])

# The upload is rejected outright rather than truncated, so the client learns
# the limit it needs to work with instead of silently getting a cut-off file
# (FR-04.2).
ATTACHMENT_TOO_LARGE_STATUS = 413
ATTACHMENT_TOO_LARGE_CODE = "attachment_too_large"


def _reject_if_too_large(size: int | None) -> None:
    if size is not None and size > settings.ATTACHMENT_MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=ATTACHMENT_TOO_LARGE_STATUS,
            detail={
                "code": ATTACHMENT_TOO_LARGE_CODE,
                "message": (
                    "This file is larger than the "
                    f"{settings.ATTACHMENT_MAX_SIZE_BYTES}-byte limit."
                ),
                "limit": settings.ATTACHMENT_MAX_SIZE_BYTES,
            },
        )


def _content_disposition(filename: str) -> str:
    """
    A Content-Disposition header that survives whatever the original filename
    was. Headers are Latin-1 on the wire, so a name outside that range (a
    Cyrillic one, say) would otherwise crash the response outright; control
    characters would corrupt the header. `filename*` carries the exact name
    for clients that understand it (RFC 6266), `filename` is a plain fallback.
    """
    printable = "".join(c for c in filename if c.isprintable()) or "attachment"
    # `\` and `"` are the two characters a quoted-string has to escape; giving
    # either of them special meaning here instead just keeps the fallback out
    # of that business entirely.
    fallback = (
        printable.encode("ascii", "replace")
        .decode("ascii")
        .replace("\\", "_")
        .replace('"', "'")
    )
    # `quote`'s default `safe="/"` leaves a slash unescaped, which the
    # `attr-char` grammar for this value (RFC 5987) does not allow.
    encoded = quote(printable, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def _safe_media_type(content_type: str) -> str:
    """
    A Content-Type value safe to put on the wire as-is. Headers are Latin-1
    only and a raw newline would inject an extra header line, so anything
    outside plain printable ASCII falls back to a generic type rather than
    crashing or corrupting the response — the exact content type stays
    available as the attachment's metadata regardless.
    """
    if content_type.isascii() and content_type.isprintable():
        return content_type
    return "application/octet-stream"


@router.get("/tasks/{task_id}/attachments/", response_model=AttachmentsPublic)
def read_attachments(
    *, session: SessionDep, current_user: CurrentUser, task_id: uuid.UUID
) -> Any:
    """
    Retrieve a task's attachments (FR-04.1).
    """
    get_owned_task(session, current_user, task_id)
    attachments, count = crud.get_attachments(session=session, task_id=task_id)
    return AttachmentsPublic(data=attachments, count=count)


@router.post("/tasks/{task_id}/attachments/", response_model=AttachmentPublic)
def upload_attachment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    storage: AttachmentStorageDep,
    task_id: uuid.UUID,
    file: UploadFile,
) -> Any:
    """
    Attach a file to a task, including a subtask (FR-04.1). No file type is
    turned away and a task can carry any number of attachments — only the
    configured size limit is enforced (FR-04.2).
    """
    get_owned_task(session, current_user, task_id)

    # Checked against Starlette's own accounting first so an oversized upload
    # is turned away without also paying for a full in-memory copy of it.
    _reject_if_too_large(file.size)
    data = file.file.read()
    _reject_if_too_large(len(data))

    attachment = crud.create_attachment(
        session=session,
        task_id=task_id,
        owner_id=current_user.id,
        filename=(file.filename or "unnamed")[:255],
        content_type=(file.content_type or "application/octet-stream")[:255],
        size=len(data),
    )
    # The row exists before the bytes do, so a crash between the two leaves at
    # worst a metadata row with nothing to download rather than orphaned bytes
    # nothing points at.
    storage.put(str(attachment.id), data)
    return attachment


@router.get("/attachments/{attachment_id}")
def download_attachment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    storage: AttachmentStorageDep,
    attachment_id: uuid.UUID,
) -> Response:
    """
    Download an attachment's exact bytes.
    """
    attachment = get_owned_attachment(session, current_user, attachment_id)
    try:
        data = storage.get(str(attachment.id))
    except FileNotFoundError:
        # The row exists but the bytes don't — a crash between creating one
        # and writing the other (see upload_attachment). Reported the same as
        # any other missing attachment rather than as a server error.
        raise HTTPException(status_code=404, detail="Attachment not found") from None
    return Response(
        content=data,
        media_type=_safe_media_type(attachment.content_type),
        headers={"Content-Disposition": _content_disposition(attachment.filename)},
    )


@router.delete("/attachments/{attachment_id}")
def delete_attachment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    storage: AttachmentStorageDep,
    attachment_id: uuid.UUID,
) -> Message:
    """
    Delete an attachment and release its bytes from storage.
    """
    attachment = get_owned_attachment(session, current_user, attachment_id)
    # The bytes go first: if that fails, the row is still there to retry
    # against. The other way round, a failure after the row is gone would
    # leave the bytes orphaned with nothing left to name them.
    storage.delete(str(attachment.id))
    crud.delete_attachment(session=session, attachment=attachment)
    return Message(message="Attachment deleted successfully")
