"""
`app.activity_log.read_activity` (#298): the reader three callers compose,
answered against the real test database the way `tests/access/
test_activity_log_scope.py` answers the scope rule it rides on — direct
`crud` calls and a hand-built `Caller`, never an HTTP round trip. The scope
narrowing itself (which entries a bot user's scope lets through) is already
pinned there; these tests are about the reader's own job: the value object's
other fields (kind, task, project, actor, period, order, page), the
task/project refusals, and the shape it hands back.
"""

import uuid
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from app import activity, crud
from app.activity_log import ActivityNarrowing, read_activity
from app.api.deps import Caller
from app.models import (
    ActivityAction,
    ActivityKind,
    ActivityOrder,
    BotPermissions,
    BotScope,
    BotUserCreate,
    Project,
    ProjectCreate,
    Task,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
    UserCreate,
)
from tests.utils.utils import random_email


@dataclass
class World:
    owner_id: uuid.UUID
    project: Project
    other_project: Project
    task: Task
    other_task: Task


def _project(db: Session, owner_id: uuid.UUID, name: str) -> Project:
    return crud.create_project(
        session=db, project_create=ProjectCreate(name=name), owner_id=owner_id
    )


def _task(db: Session, owner_id: uuid.UUID, project: Project, title: str) -> Task:
    return crud.create_task(
        session=db,
        task_create=TaskCreate(title=title),
        project_id=project.id,
        owner_id=owner_id,
        reporter=crud.Reporter(user_id=owner_id),
    )


@pytest.fixture
def world(db: Session) -> World:
    owner = crud.create_user(session=db, user_create=UserCreate(email=random_email()))
    project = _project(db, owner.id, "Work")
    other_project = _project(db, owner.id, "Elsewhere")
    task = _task(db, owner.id, project, "Write the report")
    other_task = _task(db, owner.id, other_project, "Unrelated")
    return World(
        owner_id=owner.id,
        project=project,
        other_project=other_project,
        task=task,
        other_task=other_task,
    )


def _human(world: World) -> Caller:
    return Caller(owner_id=world.owner_id)


def _bot(db: Session, world: World, project_ids: list[uuid.UUID]) -> Caller:
    bot = crud.create_bot_user(
        session=db,
        bot_user_create=BotUserCreate(
            name="Agent",
            scope=BotScope(
                project_ids=project_ids,
                permissions=BotPermissions(read_activity=True),
            ),
        ),
        owner_id=world.owner_id,
    )
    return Caller(owner_id=world.owner_id, bot=bot, project_ids=frozenset(project_ids))


def _complete(db: Session, task: Task) -> None:
    crud.update_task(
        session=db, db_task=task, task_in=TaskUpdate(status=TaskStatus.DONE)
    )


# --- the grant, checked first --------------------------------------------


def test_a_bot_without_the_grant_is_refused_by_name(db: Session, world: World) -> None:
    bot = crud.create_bot_user(
        session=db,
        bot_user_create=BotUserCreate(
            name="Agent",
            scope=BotScope(
                project_ids=[world.project.id],
                permissions=BotPermissions(read_activity=False),
            ),
        ),
        owner_id=world.owner_id,
    )
    caller = Caller(
        owner_id=world.owner_id, bot=bot, project_ids=frozenset([world.project.id])
    )

    with pytest.raises(HTTPException) as exc_info:
        read_activity(db, caller, ActivityNarrowing())

    detail = exc_info.value.detail
    assert exc_info.value.status_code == 403
    assert isinstance(detail, dict) and detail["code"] == "permission_not_granted"


def test_a_human_has_no_grant_to_check(db: Session, world: World) -> None:
    page = read_activity(db, _human(world), ActivityNarrowing())
    assert page.total >= 1


# --- kind ------------------------------------------------------------------


def test_kind_narrows_to_one_group_of_changes(db: Session, world: World) -> None:
    _complete(db, world.task)

    completed = read_activity(
        db, _human(world), ActivityNarrowing(kind=ActivityKind.COMPLETED)
    )
    created = read_activity(
        db, _human(world), ActivityNarrowing(kind=ActivityKind.CREATED)
    )

    assert any(e.action == ActivityAction.TASK_COMPLETED for e in completed.entries)
    assert not any(e.action == ActivityAction.TASK_CREATED for e in completed.entries)
    assert any(e.action == ActivityAction.TASK_CREATED for e in created.entries)


# --- task and project narrowing, and their refusals ------------------------


def test_task_id_narrows_to_one_tasks_history(db: Session, world: World) -> None:
    page = read_activity(db, _human(world), ActivityNarrowing(task_id=world.task.id))

    entity_ids = {e.entity_id for e in page.entries}
    assert world.task.id in entity_ids
    assert world.other_task.id not in entity_ids


def test_task_id_not_the_callers_own_is_a_404(db: Session, world: World) -> None:
    stranger = crud.create_user(
        session=db, user_create=UserCreate(email=random_email())
    )
    stranger_project = _project(db, stranger.id, "Theirs")
    stranger_task = _task(db, stranger.id, stranger_project, "Not yours")

    with pytest.raises(HTTPException) as exc_info:
        read_activity(db, _human(world), ActivityNarrowing(task_id=stranger_task.id))
    assert exc_info.value.status_code == 404


def test_project_id_outside_a_bots_scope_is_a_404(db: Session, world: World) -> None:
    bot = _bot(db, world, [world.project.id])

    with pytest.raises(HTTPException) as exc_info:
        read_activity(db, bot, ActivityNarrowing(project_id=world.other_project.id))
    assert exc_info.value.status_code == 404


def test_project_id_narrows_to_one_projects_chronology(
    db: Session, world: World
) -> None:
    page = read_activity(
        db, _human(world), ActivityNarrowing(project_id=world.project.id)
    )

    entity_ids = {e.entity_id for e in page.entries}
    assert world.task.id in entity_ids
    assert world.other_task.id not in entity_ids


# --- actor -------------------------------------------------------------


def test_actor_bot_user_id_narrows_to_one_bots_own_changes(
    db: Session, world: World
) -> None:
    bot = _bot(db, world, [world.project.id])
    assert bot.bot is not None
    activity.set_bot_actor(db, bot.bot.id)
    _complete(db, world.task)

    page = read_activity(
        db,
        _human(world),
        ActivityNarrowing(actor_bot_user_id=bot.bot.id),
    )

    assert all(e.actor_bot_user_id == bot.bot.id for e in page.entries)
    assert any(e.action == ActivityAction.TASK_COMPLETED for e in page.entries)


def test_by_user_and_by_bots_are_the_two_sides_of_who_acted(
    db: Session, world: World
) -> None:
    bot = _bot(db, world, [world.project.id])
    assert bot.bot is not None
    activity.set_bot_actor(db, bot.bot.id)
    _complete(db, world.task)

    by_bots = read_activity(db, _human(world), ActivityNarrowing(by_bots=True))
    by_user = read_activity(db, _human(world), ActivityNarrowing(by_user=True))

    assert all(e.actor_bot_user_id is not None for e in by_bots.entries)
    assert all(e.actor_bot_user_id is None for e in by_user.entries)


# --- period --------------------------------------------------------------


def test_since_and_until_are_exclusive_and_inclusive(db: Session, world: World) -> None:
    newest = read_activity(db, _human(world), ActivityNarrowing()).entries[0]
    moment = newest.created_at
    assert moment is not None

    excluded = read_activity(db, _human(world), ActivityNarrowing(since=moment))
    included = read_activity(db, _human(world), ActivityNarrowing(until=moment))

    assert newest.id not in {e.id for e in excluded.entries}
    assert newest.id in {e.id for e in included.entries}


# --- order and page --------------------------------------------------------


def test_order_turns_the_log_around(db: Session, world: World) -> None:
    newest_first = read_activity(
        db, _human(world), ActivityNarrowing(order=ActivityOrder.NEWEST)
    )
    oldest_first = read_activity(
        db, _human(world), ActivityNarrowing(order=ActivityOrder.OLDEST)
    )

    assert [e.id for e in newest_first.entries] == list(
        reversed([e.id for e in oldest_first.entries])
    )


def test_limit_none_asks_for_every_match(db: Session, world: World) -> None:
    _complete(db, world.task)

    paged = read_activity(db, _human(world), ActivityNarrowing(limit=1))
    unbounded = read_activity(db, _human(world), ActivityNarrowing(limit=None))

    assert len(paged.entries) == 1
    assert len(unbounded.entries) == unbounded.total
    assert unbounded.total > 1


# --- the located side data --------------------------------------------------


def test_locations_places_a_task_entry_in_its_project(
    db: Session, world: World
) -> None:
    page = read_activity(db, _human(world), ActivityNarrowing(task_id=world.task.id))

    assert page.locations[world.task.id] == world.project.id
