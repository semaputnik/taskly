"""
The task read model: tasks as the API shows them, assembled in one place and
in a fixed number of queries.
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session

from app.models import Task
from app.read_models import task_publics
from tests.utils.bot import (
    ALL_PERMISSIONS,
    API,
    create_bot_user,
    create_project,
    create_task,
    create_user_headers,
)

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _task(client: TestClient, headers: Headers, **body: Any) -> dict[str, Any]:
    r = client.post(f"{API}/tasks/", headers=headers, json={"title": "T", **body})
    assert r.status_code == 200, r.text
    task: dict[str, Any] = r.json()
    return task


def _as_api_shows(client: TestClient, headers: Headers, task_id: str) -> Any:
    r = client.get(f"{API}/tasks/{task_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _modelled(db: Session, task_ids: list[str]) -> list[Any]:
    db.expire_all()
    tasks = [db.get_one(Task, uuid.UUID(task_id)) for task_id in task_ids]
    return [public.model_dump(mode="json") for public in task_publics(db, tasks)]


def test_the_model_shows_tasks_as_the_api_does(
    client: TestClient, db: Session, owner: Headers
) -> None:
    project_id = create_project(client, owner, name="Home")
    root = create_task(client, owner, project_id=project_id, title="Root")
    child = create_task(client, owner, parent_id=root, title="Child")
    deep = create_task(client, owner, parent_id=child, title="Deep")
    recurring = _task(
        client,
        owner,
        title="Bins",
        due_date="2030-01-07",
        recurrence={"frequency": "weekly"},
    )["id"]
    tagged = _task(client, owner, title="Tagged", tags=["zeta", "Alpha"])["id"]
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    assigned = _task(
        client, owner, project_id=project_id, title="Bot's", assignee_id=bot["id"]
    )["id"]
    r = client.delete(f"{API}/bot-users/{bot['id']}", headers=owner)
    assert r.status_code == 200, r.text

    ids = [root, deep, recurring, tagged, assigned]
    shown = [_as_api_shows(client, owner, task_id) for task_id in ids]

    assert _modelled(db, ids) == shown
    by_id = {task["id"]: task for task in shown}
    assert by_id[deep]["project_id"] == project_id
    assert by_id[recurring]["recurrence"]["frequency"] == "weekly"
    assert by_id[tagged]["tags"] == ["Alpha", "zeta"]
    assert by_id[assigned]["assignee_bot_user"]["deleted"] is True


def test_known_projects_and_recurrences_are_not_looked_up_again(
    client: TestClient, db: Session, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    parent = create_task(client, owner, project_id=project_id)
    child = create_task(client, owner, parent_id=parent)
    task = db.get_one(Task, uuid.UUID(child))

    with _counting(db) as statements:
        [public] = task_publics(
            db,
            [task],
            projects={task.id: uuid.UUID(project_id)},
            recurrences={task.id: None},
        )

    assert str(public.project_id) == project_id
    assert not [s for s in statements if "task_ancestry" in s or "series" in s]


class _counting:
    def __init__(self, db: Session) -> None:
        self.engine = db.get_bind()
        self.statements: list[str] = []

    def _record(self, *args: Any) -> None:
        self.statements.append(str(args[2]))

    def __enter__(self) -> list[str]:
        event.listen(self.engine, "before_cursor_execute", self._record)
        return self.statements

    def __exit__(self, *_: object) -> None:
        event.remove(self.engine, "before_cursor_execute", self._record)


def test_serialising_costs_the_same_for_one_task_and_fifty(
    client: TestClient, db: Session, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = create_bot_user(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )

    def alike() -> str:
        task_id: str = _task(
            client,
            owner,
            project_id=project_id,
            due_date="2030-01-07",
            recurrence={"frequency": "daily"},
            tags=["chores"],
            assignee_id=bot["id"],
        )["id"]
        return task_id

    ids = [alike() for _ in range(51)]

    def cost(task_ids: list[str]) -> int:
        db.expire_all()
        tasks = [db.get_one(Task, uuid.UUID(task_id)) for task_id in task_ids]
        with _counting(db) as recorded:
            task_publics(db, tasks)
        return len(recorded)

    assert cost(ids[:1]) == cost(ids[1:])


def test_a_task_counts_its_own_subtasks_and_how_many_are_done(
    client: TestClient, db: Session, owner: Headers
) -> None:
    root = create_task(client, owner, title="Root")
    done = create_task(client, owner, parent_id=root, title="Done")
    open_child = create_task(client, owner, parent_id=root, title="Open")
    # A grandchild is its parent's subtask, not the root's.
    create_task(client, owner, parent_id=open_child, title="Grandchild")
    deleted = create_task(client, owner, parent_id=root, title="Deleted")
    lone = create_task(client, owner, title="Lone")

    r = client.patch(f"{API}/tasks/{done}", headers=owner, json={"status": "done"})
    assert r.status_code == 200, r.text
    r = client.delete(f"{API}/tasks/{deleted}", headers=owner)
    assert r.status_code == 200, r.text

    shown = {
        task_id: _as_api_shows(client, owner, task_id)
        for task_id in (root, open_child, lone)
    }

    assert (shown[root]["subtask_count"], shown[root]["subtasks_done"]) == (2, 1)
    assert (shown[open_child]["subtask_count"], shown[open_child]["subtasks_done"]) == (
        1,
        0,
    )
    assert (shown[lone]["subtask_count"], shown[lone]["subtasks_done"]) == (0, 0)
    assert _modelled(db, list(shown)) == list(shown.values())
