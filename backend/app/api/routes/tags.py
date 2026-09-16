import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app import activity, crud
from app.api import authorization
from app.api.deps import CallerDep, CurrentUser, SessionDep
from app.models import (
    Message,
    Tag,
    TagCreate,
    TagMerge,
    TagMergePreview,
    TagPublic,
    TagsPublic,
    TagUpdate,
)

# Reading tags and creating them are open to a bot user; renaming and deleting
# take a human caller, since either changes tasks in every project and no bot
# scope could allow that (ADR-0003).
router = APIRouter(prefix="/tags", tags=["tags"])

# A name is unique among the user's tags (FR-01.22). Taking one that is in use
# is refused rather than merging the two tags behind the user's back.
TAG_EXISTS_STATUS = 409
TAG_EXISTS_CODE = "tag_exists"

# A tag merged into itself can only be a mistake, so it is refused rather than
# treated as nothing to do.
TAG_MERGE_INTO_ITSELF_CODE = "tag_merge_into_itself"


def _get_owned_tag(session: SessionDep, owner_id: uuid.UUID, tag_id: uuid.UUID) -> Tag:
    tag = session.get(Tag, tag_id)
    if not tag or tag.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


def _refuse_taken_name(session: SessionDep, owner_id: uuid.UUID, name: str) -> None:
    if crud.get_tag_by_name(session=session, owner_id=owner_id, name=name):
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
    caller: CallerDep,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve the caller's tags, each with the number of tasks carrying it
    (FR-01.26). Also what autocomplete offers while a tag is typed.

    A bot user reads its owner's whole vocabulary, counts included, whatever
    its scope: tags belong to the user rather than to a project, so a scope
    has nothing to narrow them by (ADR-0003). The counts are the owner's for
    every caller — narrowing them per caller would make one tag mean two
    different things, which is the split ADR-0003 refused. `task_count` is
    the live tasks, as the task list filtered by the tag shows them;
    `archived_task_count` is those archived with their project, which are
    counted but not reachable from here (FR-05.13).
    """
    tags, count = crud.get_tags(
        session=session, owner_id=caller.owner_id, q=q, skip=skip, limit=limit
    )
    return TagsPublic(data=tags, count=count)


@router.get("/{tag_id}", response_model=TagPublic)
def read_tag(*, session: SessionDep, caller: CallerDep, tag_id: uuid.UUID) -> Any:
    """
    Retrieve one tag by its id, with the number of tasks carrying it: what the
    tag's panel is addressed by, so a link opens a tag the list in view would
    exclude.
    """
    tag = _get_owned_tag(session, caller.owner_id, tag_id)
    return crud.tag_publics(session=session, tags=[tag])[0]


@router.post("/", response_model=TagPublic)
def create_tag(*, session: SessionDep, caller: CallerDep, tag_in: TagCreate) -> Any:
    """
    Create a tag on its own, before any task carries it (FR-01.20). It stays
    until it is deleted (FR-01.23).

    A bot user needs the permission to create tags (FR-08.9).
    """
    authorization.authorize_tag_creation(caller)
    _refuse_taken_name(session, caller.owner_id, tag_in.name)
    tag = crud.create_tag(session=session, owner_id=caller.owner_id, name=tag_in.name)
    return crud.tag_publics(session=session, tags=[tag])[0]


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
    tag = _get_owned_tag(session, current_user.id, tag_id)
    if tag_in.name != tag.name:
        _refuse_taken_name(session, current_user.id, tag_in.name)
        tag = crud.rename_tag(session=session, tag=tag, name=tag_in.name)
    return crud.tag_publics(session=session, tags=[tag])[0]


@router.delete("/{tag_id}")
def delete_tag(
    *, session: SessionDep, current_user: CurrentUser, tag_id: uuid.UUID
) -> Message:
    """
    Delete a tag and take it off every task carrying it (FR-01.25).

    There is no undoing it: a tag deletion is not a deletion event, so the
    activity log records it but cannot restore it.
    """
    tag = _get_owned_tag(session, current_user.id, tag_id)
    crud.delete_tag(session=session, tag=tag)
    return Message(message="Tag deleted successfully")


def _merge_sources(
    session: SessionDep, target: Tag, source_ids: list[uuid.UUID]
) -> list[Tag]:
    """
    The tags a merge folds into `target`, all of them the caller's. Any that is
    not refuses the whole merge, before anything has moved.
    """
    unique = list(dict.fromkeys(source_ids))
    if target.id in unique:
        raise HTTPException(
            status_code=422,
            detail={
                "code": TAG_MERGE_INTO_ITSELF_CODE,
                "message": f"“{target.name}” cannot be merged into itself.",
            },
        )
    return [_get_owned_tag(session, target.owner_id, tag_id) for tag_id in unique]


@router.get("/{tag_id}/merge-preview", response_model=TagMergePreview)
def preview_tag_merge(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tag_id: uuid.UUID,
    source_ids: Annotated[list[uuid.UUID], Query(min_length=1)],
) -> Any:
    """
    How many tasks merging `source_ids` into this tag would change, each
    counted once, with those archived with their project apart: what the
    merge confirmation says before anything happens (semaputnik/taskly#69).
    """
    target = _get_owned_tag(session, current_user.id, tag_id)
    sources = _merge_sources(session, target, source_ids)
    live, archived = crud.tag_merge_counts(
        session=session,
        owner_id=current_user.id,
        source_ids=[source.id for source in sources],
    )
    return TagMergePreview(task_count=live, archived_task_count=archived)


@router.post("/{tag_id}/merge", response_model=TagPublic)
def merge_tags(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tag_id: uuid.UUID,
    merge_in: TagMerge,
) -> Any:
    """
    Fold other tags into this one: every task carrying one of them carries
    this tag instead, once, and they are deleted (semaputnik/taskly#69).

    Renaming a tag to a name in use stays refused; this is the separate,
    deliberate act for putting two spellings together. It keeps names as they
    are — case-sensitive and unique per user — and, like deleting a tag,
    cannot be undone: the activity log records it without being able to
    restore it. Only a human merges, as only a human renames or deletes a tag
    (ADR-0003).
    """
    target = _get_owned_tag(session, current_user.id, tag_id)
    sources = _merge_sources(session, target, merge_in.source_ids)
    source_ids = [source.id for source in sources]
    live, archived = crud.tag_merge_counts(
        session=session, owner_id=current_user.id, source_ids=source_ids
    )
    activity.set_tag_merge(
        session,
        target=target,
        source_ids=source_ids,
        sources=sorted((source.name for source in sources), key=str.lower),
        task_count=live + archived,
    )
    crud.merge_tags(session=session, target=target, sources=sources)
    return crud.tag_publics(session=session, tags=[target])[0]
