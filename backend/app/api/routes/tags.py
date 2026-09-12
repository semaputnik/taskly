from typing import Any

from fastapi import APIRouter

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import TagsPublic

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/", response_model=TagsPublic)
def read_tags(
    session: SessionDep,
    current_user: CurrentUser,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve the tags the current user has used, for autocomplete.

    Tags are applied and removed on tasks themselves (FR-01.20), so this is the
    only tag endpoint there is: a list to offer while the user types.
    """
    tags, count = crud.get_tags(
        session=session, owner_id=current_user.id, q=q, skip=skip, limit=limit
    )
    return TagsPublic(data=tags, count=count)
