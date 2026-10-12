"""
The activity log's own scope rule: which of an owner's entries a bot user's
scope lets through, answered against the real test database the way
`test_task_access.py` answers task access — direct `crud` calls rather than
HTTP, so the fixture writes activity entries as a side effect of the global
session listener (`app.activity`) the same way the API does.
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlmodel import Session, col, select

from app import activity, crud
from app.api import access
from app.api.deps import Caller
from app.models import (
    ActivityAction,
    ActivityEntityType,
    ActivityEntry,
    BotPermissions,
    BotScope,
    BotUserCreate,
    Project,
    ProjectCreate,
    Task,
    TaskBulkUpdate,
    TaskCreate,
    TaskStatus,
    UserCreate,
)
from tests.utils.utils import random_email


@dataclass
class World:
    owner_id: uuid.UUID
    in_scope: Project
    out_of_scope: Project
    archived: Project
    inside_task: Task
    outside_task: Task
    archived_task: Task


def _project(db: Session, owner_id: uuid.UUID, name: str) -> Project:
    return crud.create_project(
        session=db, project_create=ProjectCreate(name=name), owner_id=owner_id
    )


def _task(db: Session, owner_id: uuid.UUID, project: Project, title: str = "T") -> Task:
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
    in_scope = _project(db, owner.id, "In scope")
    out_of_scope = _project(db, owner.id, "Elsewhere")
    archived = _project(db, owner.id, "Shelved")
    inside_task = _task(db, owner.id, in_scope, "Inside")
    outside_task = _task(db, owner.id, out_of_scope, "Outside")
    archived_task = _task(db, owner.id, archived, "Archived task")
    crud.set_project_archived(session=db, project=archived, archived=True)
    return World(
        owner_id=owner.id,
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        archived=archived,
        inside_task=inside_task,
        outside_task=outside_task,
        archived_task=archived_task,
    )


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


def _visible(db: Session, caller: Caller) -> list[ActivityEntry]:
    where = [ActivityEntry.owner_id == caller.owner_id]
    if (scope := access.activity_log_scope(caller)) is not None:
        where.append(scope)
    return list(db.exec(select(ActivityEntry).where(*where)).all())


def _task_entity_ids(entries: list[ActivityEntry]) -> set[uuid.UUID]:
    return {e.entity_id for e in entries if e.entity_type == ActivityEntityType.TASK}


def test_a_human_has_no_scope_filter_at_all(world: World) -> None:
    assert access.activity_log_scope(Caller(owner_id=world.owner_id)) is None


def test_a_bot_reads_only_the_tasks_in_its_scope(db: Session, world: World) -> None:
    bot = _bot(db, world, [world.in_scope.id])

    task_ids = _task_entity_ids(_visible(db, bot))

    assert world.inside_task.id in task_ids
    assert world.outside_task.id not in task_ids


def test_a_bot_reads_the_scopes_projects_themselves(db: Session, world: World) -> None:
    bot = _bot(db, world, [world.in_scope.id])

    entries = _visible(db, bot)

    assert any(
        e.entity_type == ActivityEntityType.PROJECT and e.entity_id == world.in_scope.id
        for e in entries
    )
    assert not any(
        e.entity_type == ActivityEntityType.PROJECT
        and e.entity_id == world.out_of_scope.id
        for e in entries
    )


def test_an_archived_project_is_excluded_even_when_the_scope_lists_it(
    db: Session, world: World
) -> None:
    bot = _bot(db, world, [world.in_scope.id, world.archived.id])

    entries = _visible(db, bot)

    assert world.archived_task.id not in _task_entity_ids(entries)
    assert not any(
        e.entity_type == ActivityEntityType.PROJECT and e.entity_id == world.archived.id
        for e in entries
    )
    # The rest of the scope is unaffected.
    assert world.inside_task.id in _task_entity_ids(entries)


def test_a_tag_entry_is_visible_whatever_the_scope(db: Session, world: World) -> None:
    bot = _bot(db, world, [world.in_scope.id])
    tag = crud.create_tag(session=db, owner_id=world.owner_id, name="Urgent")

    entries = _visible(db, bot)

    assert any(
        e.entity_type == ActivityEntityType.TAG and e.entity_id == tag.id
        for e in entries
    )


def _bulk_complete(db: Session, task_ids: list[uuid.UUID]) -> uuid.UUID:
    """
    A batch completion, logged the way the route logs it
    (`app.api.routes.tasks.bulk_update_tasks`): `activity.set_batch` before
    the write, so the one entry it produces names every task at once. Reads
    back the newest `tasks_bulk_changed` entry rather than guessing which
    task the log filed it under.
    """
    tasks = [db.get_one(Task, task_id) for task_id in task_ids]
    owner_id = tasks[0].owner_id
    activity.set_batch(
        db, ActivityAction.TASKS_BULK_CHANGED, task_ids, {"changes": {"status": "done"}}
    )
    crud.bulk_update_tasks(
        session=db,
        tasks=tasks,
        changes=TaskBulkUpdate(task_ids=task_ids, status=TaskStatus.DONE),
    )
    entry_id = db.exec(
        select(ActivityEntry.id)
        .where(
            ActivityEntry.owner_id == owner_id,
            ActivityEntry.action == ActivityAction.TASKS_BULK_CHANGED,
        )
        .order_by(col(ActivityEntry.position).desc())
        .limit(1)
    ).one()
    return entry_id


def test_a_batch_is_visible_only_when_every_task_it_names_is_in_scope(
    db: Session, world: World
) -> None:
    # Two fresh tasks each, so neither batch is a same-value no-op the ORM
    # might decide not to flush as a change.
    first_inside = _task(db, world.owner_id, world.in_scope, "First inside")
    second_inside = _task(db, world.owner_id, world.in_scope, "Second inside")
    third_inside = _task(db, world.owner_id, world.in_scope, "Third inside")
    bot = _bot(db, world, [world.in_scope.id])

    whole_entry_id = _bulk_complete(db, [first_inside.id, second_inside.id])
    assert whole_entry_id in {e.id for e in _visible(db, bot)}

    straddling_entry_id = _bulk_complete(db, [world.outside_task.id, third_inside.id])
    assert straddling_entry_id not in {e.id for e in _visible(db, bot)}
