import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import Message, Tag, TagCreate, TagPublic, TagsPublic, TagUpdate

# Every endpoint here takes a human caller. Renaming or deleting a tag changes
# tasks in every project, so no bot scope could allow it (ADR-0003).
router = APIRouter(prefix="/tags", tags=["tags"])

# A name is unique among the user's tags (FR-01.22). Taking one that is in use
# is refused rather than merging the two tags behind the user's back.
TAG_EXISTS_STATUS = 409
TAG_EXISTS_CODE = "tag_exists"


def _get_owned_tag(
    session: SessionDep, current_user: CurrentUser, tag_id: uuid.UUID
) -> Tag:
    tag = session.get(Tag, tag_id)
    if not tag or tag.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


def _refuse_taken_name(
    session: SessionDep, current_user: CurrentUser, name: str
) -> None:
    if crud.get_tag_by_name(session=session, owner_id=current_user.id, name=name):
        raise HTTPException(
            status_code=TAG_EXISTS_STATUS,
            detail={
                "code": TAG_EXISTS_CODE,
                "message": f"You already have a tag named “{name}”.",
            },
        )


@router.get("/", response_model=TagsPublic)
def read_tags(
    session: SessionDep,
    current_user: CurrentUser,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve the current user's tags, each with the number of tasks carrying
    it (FR-01.26). Also what autocomplete offers while a tag is typed.
    """
    tags, count = crud.get_tags(
        session=session, owner_id=current_user.id, q=q, skip=skip, limit=limit
    )
    return TagsPublic(data=tags, count=count)


@router.post("/", response_model=TagPublic)
def create_tag(
    *, session: SessionDep, current_user: CurrentUser, tag_in: TagCreate
) -> Any:
    """
    Create a tag on its own, before any task carries it (FR-01.20). It stays
    until it is deleted (FR-01.23).
    """
    _refuse_taken_name(session, current_user, tag_in.name)
    tag = crud.create_tag(session=session, owner_id=current_user.id, name=tag_in.name)
    return crud.tag_public(tag)


@router.patch("/{tag_id}", response_model=TagPublic)
def rename_tag(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tag_id: uuid.UUID,
    tag_in: TagUpdate,
) -> Any:
    """
    Rename a tag: every task carrying it shows the new name (FR-01.24). Names
    are case-sensitive, so changing only the case is a rename like any other.
    Renaming a tag to the name it already has changes nothing.
    """
    tag = _get_owned_tag(session, current_user, tag_id)
    if tag_in.name != tag.name:
        _refuse_taken_name(session, current_user, tag_in.name)
        tag = crud.rename_tag(session=session, tag=tag, name=tag_in.name)
    task_counts = crud.get_tag_task_counts(session=session, tag_ids=[tag.id])
    return crud.tag_public(tag, task_counts.get(tag.id, 0))


@router.delete("/{tag_id}")
def delete_tag(
    *, session: SessionDep, current_user: CurrentUser, tag_id: uuid.UUID
) -> Message:
    """
    Delete a tag and take it off every task carrying it (FR-01.25).

    There is no undoing it: a tag deletion is not a deletion event, so the
    activity log records it but cannot restore it.
    """
    tag = _get_owned_tag(session, current_user, tag_id)
    crud.delete_tag(session=session, tag=tag)
    return Message(message="Tag deleted successfully")
