"""
`GET /caller`: the one endpoint a human session and a bot token both call to
find out who they are (spec #245).

It answers four questions a caller cannot otherwise answer about itself: who
is making this request, whose data it reaches, what it may reach and do, and
what today's date is here. Read-only, so nothing is logged (FR-10.1).
"""

from datetime import date
from typing import Any

from fastapi import APIRouter
from sqlmodel import Session

from app import crud
from app.api.deps import Caller, CallerDep, SessionDep
from app.models import (
    ActorKind,
    BotPermissions,
    CallerActor,
    CallerProject,
    CallerPublic,
)

router = APIRouter(tags=["caller"])

# Built once: every permission true, for a human (spec #245), derived from
# the model rather than listed here by hand (issue #264).
_HUMAN_PERMISSIONS = BotPermissions.all_granted()


def _bot_projects(session: Session, caller: Caller) -> list[CallerProject]:
    """
    The live, unarchived projects of a bot's scope, each with its open-task
    count, Inbox first then by name ignoring case — the same order the
    project list uses (FR-05.14), so the two never disagree. An archived
    project is left out whatever the scope says (FR-05.13), and so is a
    project that has since been deleted (CONTEXT.md, "Scope").

    The query itself is `crud.project_list_statement`, the one the project
    list route also runs (issue #264): the two cannot drift the way they once
    did when each kept its own copy.
    """
    statement = crud.project_list_statement(
        owner_id=caller.owner_id, archived=False, project_ids=caller.project_ids
    )
    projects = session.exec(statement).all()
    stats = crud.get_project_task_stats(
        session=session,
        owner_id=caller.owner_id,
        project_ids=[project.id for project in projects],
    )
    return [
        CallerProject(
            id=project.id,
            name=project.name,
            is_inbox=project.is_inbox,
            open_tasks=stats.get(project.id, crud.ProjectTaskStats()).open,
        )
        for project in projects
    ]


@router.get("/caller", response_model=CallerPublic)
def read_caller(session: SessionDep, caller: CallerDep) -> Any:
    """
    Who is calling, whose data the call reaches, what it may do there, and
    today's date (spec #245).

    A bot user gets its own id and name, its owner's id, exactly the grants
    its scope holds, and the projects of that scope. A human session gets its
    own id as both actor and owner, every permission true, and `projects` as
    `null` — a human's projects are the project list's, not a finite scope
    (FR-08.6).
    """
    if caller.bot is not None:
        bot = caller.bot
        return CallerPublic(
            actor=CallerActor(kind=ActorKind.BOT_USER, id=bot.id, name=bot.name),
            owner_id=caller.owner_id,
            permissions=BotPermissions.model_validate(bot),
            projects=_bot_projects(session, caller),
            today=date.today(),
        )

    user = caller.user
    assert user is not None  # a non-bot caller always resolves to a user
    return CallerPublic(
        actor=CallerActor(
            kind=ActorKind.USER, id=user.id, name=user.full_name or user.email
        ),
        owner_id=caller.owner_id,
        permissions=_HUMAN_PERMISSIONS,
        projects=None,
        today=date.today(),
    )
