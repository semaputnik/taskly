"""
The Task access module: one question — this task, for this caller, to do
this action — answered against the real test database.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session

from app import crud, deletions
from app.api import access
from app.api.access import TaskAction
from app.api.deps import Caller
from app.models import (
    BotPermissions,
    BotScope,
    BotUserCreate,
    Project,
    ProjectCreate,
    Task,
    TaskCreate,
    UserCreate,
)
from tests.utils.bot import API, create_task, create_user_headers
from tests.utils.utils import random_email, random_lower_string


@dataclass
class World:
    owner: Caller
    stranger: Caller
    project: Project
    archived: Project
    outside: Project
    root: Task
    deep: Task
    archived_task: Task
    outside_task: Task
    deleted: Task
    under_deleted: Task


def _task(
    db: Session,
    owner_id: uuid.UUID,
    *,
    project: Project | None = None,
    parent: Task | None = None,
    title: str = "T",
) -> Task:
    return crud.create_task(
        session=db,
        task_create=TaskCreate(title=title, parent_id=parent.id if parent else None),
        project_id=project.id if project else None,
        owner_id=owner_id,
    )


@pytest.fixture
def world(db: Session) -> World:
    owner = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )
    stranger = crud.create_user(
        session=db,
        user_create=UserCreate(email=random_email(), password=random_lower_string()),
    )

    def project(name: str) -> Project:
        return crud.create_project(
            session=db, project_create=ProjectCreate(name=name), owner_id=owner.id
        )

    live, archived, outside = project("Live"), project("Frozen"), project("Outside")
    root = _task(db, owner.id, project=live, title="Root")
    child = _task(db, owner.id, parent=root)
    deep = _task(db, owner.id, parent=child, title="Deep")
    archived_task = _task(db, owner.id, project=archived, title="Frozen task")
    crud.set_project_archived(session=db, project=archived, archived=True)
    outside_task = _task(db, owner.id, project=outside)

    deleted = _task(db, owner.id, project=live)
    deletions.delete_task(db, deleted)
    # A live-looking task under a deleted ancestor: the ancestor was deleted
    # on its own, after its subtask had been restored from an earlier event.
    doomed = _task(db, owner.id, project=live)
    under_deleted = _task(db, owner.id, parent=doomed)
    deletions.delete_task(db, doomed)
    under_deleted.deletion_id = None
    db.add(under_deleted)
    db.commit()

    return World(
        owner=Caller(owner_id=owner.id),
        stranger=Caller(owner_id=stranger.id),
        project=live,
        archived=archived,
        outside=outside,
        root=root,
        deep=deep,
        archived_task=archived_task,
        outside_task=outside_task,
        deleted=deleted,
        under_deleted=under_deleted,
    )


def _bot(db: Session, world: World, **permissions: bool) -> Caller:
    owner_id = world.owner.owner_id
    projects = [world.project.id, world.archived.id]
    bot = crud.create_bot_user(
        session=db,
        bot_user_create=BotUserCreate(
            name="Agent",
            scope=BotScope(
                project_ids=projects, permissions=BotPermissions(**permissions)
            ),
        ),
        owner_id=owner_id,
    )
    return Caller(owner_id=owner_id, bot=bot, project_ids=frozenset(projects))


def _refused(call: object) -> tuple[int, object]:
    assert isinstance(call, HTTPException)
    detail = call.detail
    return call.status_code, detail.get("code") if isinstance(detail, dict) else detail


def _raises(fn: object, *args: object) -> tuple[int, object]:
    with pytest.raises(HTTPException) as refused:
        fn(*args)  # type: ignore[operator]
    return _refused(refused.value)


# A single task


def test_the_owner_gets_the_task_with_its_project(db: Session, world: World) -> None:
    resolved = access.get_task(db, world.owner, world.root.id, TaskAction.READ)

    assert resolved.task.id == world.root.id
    assert resolved.project.id == world.project.id


def test_a_deep_subtask_resolves_to_its_root_project(db: Session, world: World) -> None:
    resolved = access.get_task(db, world.owner, world.deep.id, TaskAction.UPDATE)

    assert resolved.task.id == world.deep.id
    assert resolved.project.id == world.project.id


@pytest.mark.parametrize("action", list(TaskAction))
def test_a_strangers_missing_or_deleted_task_is_not_found(
    db: Session, world: World, action: TaskAction
) -> None:
    for caller, task_id in [
        (world.stranger, world.root.id),
        (world.owner, uuid.uuid4()),
        (world.owner, world.deleted.id),
        (world.owner, world.under_deleted.id),
    ]:
        assert _raises(access.get_task, db, caller, task_id, action) == (
            404,
            "Task not found",
        )


def test_a_missing_task_is_not_found_for_a_bot_too(db: Session, world: World) -> None:
    bot = _bot(db, world, read_tasks=True)

    assert _raises(
        access.get_task, db, bot, world.under_deleted.id, TaskAction.READ
    ) == (404, "Task not found")


def test_a_human_reads_an_archived_task_but_cannot_write_it(
    db: Session, world: World
) -> None:
    resolved = access.get_task(db, world.owner, world.archived_task.id, TaskAction.READ)
    assert resolved.project.id == world.archived.id

    for action in (
        TaskAction.CREATE,
        TaskAction.UPDATE,
        TaskAction.DELETE,
        TaskAction.COMMENT,
    ):
        assert _raises(
            access.get_task, db, world.owner, world.archived_task.id, action
        ) == (409, "project_archived")


def test_a_bot_never_reaches_an_archived_task(db: Session, world: World) -> None:
    bot = _bot(db, world, read_tasks=True, update_tasks=True)

    for action in (TaskAction.READ, TaskAction.UPDATE):
        assert _raises(access.get_task, db, bot, world.archived_task.id, action) == (
            403,
            "project_archived",
        )


def test_a_bot_is_refused_outside_its_scope(db: Session, world: World) -> None:
    bot = _bot(db, world, read_tasks=True)

    assert _raises(
        access.get_task, db, bot, world.outside_task.id, TaskAction.READ
    ) == (403, "outside_scope")


def test_a_bot_is_refused_without_the_permission(db: Session, world: World) -> None:
    bot = _bot(db, world, read_tasks=True)

    assert access.get_task(db, bot, world.deep.id, TaskAction.READ)
    assert _raises(access.get_task, db, bot, world.deep.id, TaskAction.UPDATE) == (
        403,
        "permission_not_granted",
    )


# A batch


def test_a_batch_resolves_what_it_can_and_refuses_the_rest(
    db: Session, world: World
) -> None:
    missing = uuid.uuid4()
    resolved, refusals = access.get_tasks(
        db,
        world.owner,
        [
            world.root.id,
            world.deep.id,
            world.archived_task.id,
            world.deleted.id,
            world.under_deleted.id,
            missing,
            world.root.id,
        ],
        TaskAction.UPDATE,
    )

    assert [(r.task.id, r.project.id) for r in resolved] == [
        (world.root.id, world.project.id),
        (world.deep.id, world.project.id),
    ]
    assert {(r.task_id, r.code) for r in refusals} == {
        (world.archived_task.id, "project_archived"),
        (world.deleted.id, "not_found"),
        (world.under_deleted.id, "not_found"),
        (missing, "not_found"),
    }


def test_a_batch_read_keeps_archived_tasks(db: Session, world: World) -> None:
    resolved, refusals = access.get_tasks(
        db, world.owner, [world.archived_task.id], TaskAction.READ
    )

    assert [r.task.id for r in resolved] == [world.archived_task.id]
    assert refusals == []


def test_a_strangers_batch_is_all_not_found(db: Session, world: World) -> None:
    resolved, refusals = access.get_tasks(
        db, world.stranger, [world.root.id, world.deep.id], TaskAction.READ
    )

    assert resolved == []
    assert {r.code for r in refusals} == {"not_found"}


def test_a_bots_batch_is_refused_per_task_by_its_scope(
    db: Session, world: World
) -> None:
    bot = _bot(db, world, update_tasks=True)

    resolved, refusals = access.get_tasks(
        db,
        bot,
        [world.root.id, world.archived_task.id, world.outside_task.id],
        TaskAction.UPDATE,
    )

    assert [r.task.id for r in resolved] == [world.root.id]
    assert {(r.task_id, r.code) for r in refusals} == {
        (world.archived_task.id, "project_archived"),
        (world.outside_task.id, "outside_scope"),
    }
    assert _raises(access.get_tasks, db, bot, [world.root.id], TaskAction.DELETE) == (
        403,
        "permission_not_granted",
    )


# Cost


@pytest.fixture
def ancestry_walks(db: Session) -> Iterator[list[str]]:
    statements: list[str] = []
    engine = db.get_bind()

    def record(*args: object) -> None:
        statement = str(args[2])
        if "task_ancestry" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    yield statements
    event.remove(engine, "before_cursor_execute", record)


def test_resolving_a_task_walks_its_tree_once(
    db: Session, world: World, ancestry_walks: list[str]
) -> None:
    db.expire_all()
    access.get_task(db, world.owner, world.deep.id, TaskAction.UPDATE)

    assert len(ancestry_walks) == 1


def test_patching_a_subtask_walks_its_tree_once(
    client: TestClient, db: Session, ancestry_walks: list[str]
) -> None:
    headers = create_user_headers(client, db)
    root = create_task(client, headers)
    child = create_task(client, headers, parent_id=root)
    deep = create_task(client, headers, parent_id=child)
    ancestry_walks.clear()

    r = client.patch(f"{API}/tasks/{deep}", headers=headers, json={"title": "Moved"})

    assert r.status_code == 200, r.text
    assert len(ancestry_walks) == 1
