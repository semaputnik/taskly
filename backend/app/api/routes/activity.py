from typing import Any

from fastapi import APIRouter, Query
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    ActivityEntriesPublic,
    ActivityEntry,
    ActivityEntryPublic,
)

router = APIRouter(prefix="/activity-log", tags=["activity"])


@router.get("/", response_model=ActivityEntriesPublic)
def read_activity_log(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> Any:
    """
    Retrieve the current user's activity log, newest first.

    Always the requesting user's own entries and nothing wider: there is no
    parameter or role that reaches another user's log, the superuser's
    included (FR-10.7).
    """
    count = session.exec(
        select(func.count())
        .select_from(ActivityEntry)
        .where(ActivityEntry.owner_id == current_user.id)
    ).one()
    entries = session.exec(
        select(ActivityEntry)
        .where(ActivityEntry.owner_id == current_user.id)
        .order_by(col(ActivityEntry.position).desc())
        .offset(skip)
        .limit(limit)
    ).all()

    # The tasks that can still be opened, and where: deleted ones are left out
    # of this map, so their entries carry no link.
    task_projects = crud.get_task_project_ids(session=session, owner_id=current_user.id)
    return ActivityEntriesPublic(
        data=[
            ActivityEntryPublic.model_validate(
                entry,
                update={
                    "entity_exists": entry.entity_id in task_projects,
                    "entity_project_id": task_projects.get(entry.entity_id),
                },
            )
            for entry in entries
        ],
        count=count,
    )
