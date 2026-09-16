"""
Merging tags: every task on the sources ends up on the target, once, and the
sources are gone (semaputnik/taskly#69).

The assertions are about the vocabulary and the tasks afterwards, not about how
the association rows were moved.
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.bot import (
    ALL_PERMISSIONS,
    create_project,
    create_user_headers,
    error_code,
    issue_bot_headers,
)

API = settings.API_V1_STR

Headers = dict[str, str]


@pytest.fixture
def owner(client: TestClient, db: Session) -> Headers:
    return create_user_headers(client, db)


def _tag(client: TestClient, headers: Headers, name: str) -> dict[str, Any]:
    r = client.post(f"{API}/tags/", headers=headers, json={"name": name})
    assert r.status_code == 200, r.text
    tag: dict[str, Any] = r.json()
    return tag


def _tags(client: TestClient, headers: Headers) -> dict[str, dict[str, Any]]:
    r = client.get(f"{API}/tags/", headers=headers)
    return {tag["name"]: tag for tag in r.json()["data"]}


def _task(client: TestClient, headers: Headers, tags: list[str], **fields: Any) -> str:
    r = client.post(
        f"{API}/tasks/", headers=headers, json={"title": "T", "tags": tags, **fields}
    )
    assert r.status_code == 200, r.text
    task_id: str = r.json()["id"]
    return task_id


def _task_tags(client: TestClient, headers: Headers, task_id: str) -> list[str]:
    tags: list[str] = client.get(f"{API}/tasks/{task_id}", headers=headers).json()[
        "tags"
    ]
    return tags


def _merge(
    client: TestClient, headers: Headers, target: str, sources: list[str]
) -> Any:
    return client.post(
        f"{API}/tags/{target}/merge", headers=headers, json={"source_ids": sources}
    )


def _preview(
    client: TestClient, headers: Headers, target: str, sources: list[str]
) -> Any:
    return client.get(
        f"{API}/tags/{target}/merge-preview",
        headers=headers,
        params={"source_ids": sources},
    )


def _ids(*tags: dict[str, Any]) -> list[str]:
    return [tag["id"] for tag in tags]


def test_a_merge_moves_every_task_onto_the_target(
    client: TestClient, owner: Headers
) -> None:
    first = _task(client, owner, ["Deploy", "work"])
    second = _task(client, owner, ["Deploy"])
    tags = _tags(client, owner)
    target = _tag(client, owner, "deploy")

    r = _merge(client, owner, target["id"], _ids(tags["Deploy"]))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == target["id"]
    assert r.json()["name"] == "deploy"
    assert r.json()["task_count"] == 2

    assert _task_tags(client, owner, first) == ["deploy", "work"]
    assert _task_tags(client, owner, second) == ["deploy"]
    listed = client.get(f"{API}/tasks/", headers=owner, params={"tag": "deploy"})
    assert {task["id"] for task in listed.json()["data"]} == {first, second}


def test_a_task_carrying_both_ends_up_with_the_target_once(
    client: TestClient, owner: Headers
) -> None:
    both = _task(client, owner, ["deploy", "deploys"])
    tags = _tags(client, owner)

    r = _merge(client, owner, tags["deploy"]["id"], _ids(tags["deploys"]))
    assert r.status_code == 200, r.text

    assert _task_tags(client, owner, both) == ["deploy"]
    assert _tags(client, owner)["deploy"]["task_count"] == 1


def test_the_sources_are_gone_and_the_target_keeps_its_identity(
    client: TestClient, owner: Headers
) -> None:
    _task(client, owner, ["deploy", "deploy-bot", "deploy bot"])
    before = _tags(client, owner)

    r = _merge(
        client,
        owner,
        before["deploy"]["id"],
        _ids(before["deploy-bot"], before["deploy bot"]),
    )
    assert r.status_code == 200, r.text

    after = _tags(client, owner)
    assert set(after) == {"deploy"}
    assert after["deploy"]["id"] == before["deploy"]["id"]
    for gone in ("deploy-bot", "deploy bot"):
        tag_id = before[gone]["id"]
        assert client.get(f"{API}/tags/{tag_id}", headers=owner).status_code == 404
    # A source's name is free again once it is gone.
    assert _tag(client, owner, "deploy-bot")["task_count"] == 0


def test_several_sources_merge_in_one_call(client: TestClient, owner: Headers) -> None:
    tasks = [
        _task(client, owner, [name])
        for name in ("Deploy", "deploys", "deploy_bot", "deploy")
    ]
    tags = _tags(client, owner)

    r = _merge(
        client,
        owner,
        tags["deploy"]["id"],
        _ids(tags["Deploy"], tags["deploys"], tags["deploy_bot"]),
    )
    assert r.status_code == 200, r.text
    assert r.json()["task_count"] == 4
    assert [_task_tags(client, owner, task) for task in tasks] == [["deploy"]] * 4


def test_a_tag_of_another_user_refuses_the_whole_merge(
    client: TestClient, db: Session, owner: Headers
) -> None:
    task = _task(client, owner, ["deploy", "deploys"])
    mine = _tags(client, owner)
    other = create_user_headers(client, db)
    theirs = _tag(client, other, "ship")

    for target, sources in (
        (mine["deploy"]["id"], [mine["deploys"]["id"], theirs["id"]]),
        (theirs["id"], [mine["deploys"]["id"]]),
        (mine["deploy"]["id"], [str(uuid.uuid4())]),
    ):
        assert _merge(client, owner, target, sources).status_code == 404

    assert set(_tags(client, owner)) == {"deploy", "deploys"}
    assert _task_tags(client, owner, task) == ["deploy", "deploys"]
    assert set(_tags(client, other)) == {"ship"}


def test_a_bot_user_cannot_merge_tags(client: TestClient, owner: Headers) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    _task(client, owner, ["deploy", "deploys"])
    tags = _tags(client, owner)

    for r in (
        _merge(client, bot, tags["deploy"]["id"], _ids(tags["deploys"])),
        _preview(client, bot, tags["deploy"]["id"], _ids(tags["deploys"])),
    ):
        assert r.status_code == 403
        assert error_code(r) == "human_only"
    assert set(_tags(client, owner)) == {"deploy", "deploys"}


def test_merging_a_tag_into_itself_is_refused(
    client: TestClient, owner: Headers
) -> None:
    _task(client, owner, ["deploy", "deploys"])
    tags = _tags(client, owner)

    r = _merge(client, owner, tags["deploy"]["id"], _ids(tags["deploy"]))
    assert r.status_code == 422
    assert error_code(r) == "tag_merge_into_itself"
    r = _merge(
        client, owner, tags["deploy"]["id"], _ids(tags["deploys"], tags["deploy"])
    )
    assert r.status_code == 422
    assert set(_tags(client, owner)) == {"deploy", "deploys"}


def test_a_merge_needs_at_least_one_source(client: TestClient, owner: Headers) -> None:
    target = _tag(client, owner, "deploy")
    assert _merge(client, owner, target["id"], []).status_code == 422


def test_a_refused_merge_leaves_everything_as_it_was(
    client: TestClient, owner: Headers
) -> None:
    tasks = [_task(client, owner, ["a", "b"]), _task(client, owner, ["b", "c"])]
    before = _tags(client, owner)
    log_before = client.get(f"{API}/activity-log/", headers=owner).json()["count"]

    # One good source and one that is not a tag at all.
    r = _merge(client, owner, before["a"]["id"], [before["b"]["id"], str(uuid.uuid4())])
    assert r.status_code == 404

    assert _tags(client, owner) == before
    assert [_task_tags(client, owner, task) for task in tasks] == [
        ["a", "b"],
        ["b", "c"],
    ]
    log_after = client.get(f"{API}/activity-log/", headers=owner).json()["count"]
    assert log_after == log_before


def test_archived_tasks_are_merged_and_counted(
    client: TestClient, owner: Headers
) -> None:
    live = _task(client, owner, ["Deploy"])
    project_id = create_project(client, owner, "Old")
    archived = _task(client, owner, ["Deploy"], project_id=project_id)
    client.post(f"{API}/projects/{project_id}/archive", headers=owner)
    deleted = _task(client, owner, ["Deploy"])
    client.delete(f"{API}/tasks/{deleted}", headers=owner)
    target = _tag(client, owner, "deploy")
    source = _tags(client, owner)["Deploy"]

    preview = _preview(client, owner, target["id"], _ids(source))
    assert preview.status_code == 200, preview.text
    assert preview.json() == {"task_count": 1, "archived_task_count": 1}

    r = _merge(client, owner, target["id"], _ids(source))
    assert r.status_code == 200, r.text
    assert (r.json()["task_count"], r.json()["archived_task_count"]) == (1, 1)
    assert _task_tags(client, owner, live) == ["deploy"]
    archived_tasks = client.get(
        f"{API}/tasks/", headers=owner, params={"archived": True}
    ).json()["data"]
    assert [(t["id"], t["tags"]) for t in archived_tasks] == [(archived, ["deploy"])]
    # A deleted task moves too, so it comes back under the surviving name.
    entry = next(
        e
        for e in client.get(f"{API}/activity-log/", headers=owner).json()["data"]
        if e["action"] == "task_deleted"
    )
    client.post(f"{API}/activity-log/{entry['id']}/restore", headers=owner)
    assert _task_tags(client, owner, deleted) == ["deploy"]


def test_the_preview_counts_a_task_once_however_many_sources_it_carries(
    client: TestClient, owner: Headers
) -> None:
    _task(client, owner, ["deploy", "Deploy", "deploys"])
    _task(client, owner, ["deploys"])
    tags = _tags(client, owner)

    r = _preview(
        client, owner, tags["deploy"]["id"], _ids(tags["Deploy"], tags["deploys"])
    )
    assert r.json() == {"task_count": 2, "archived_task_count": 0}


def test_a_merge_is_one_activity_entry_naming_both_sides(
    client: TestClient, owner: Headers
) -> None:
    _task(client, owner, ["deploy", "deploys"])
    _task(client, owner, ["Deploy"])
    tags = _tags(client, owner)
    count_before = client.get(f"{API}/activity-log/", headers=owner).json()["count"]

    _merge(client, owner, tags["deploy"]["id"], _ids(tags["deploys"], tags["Deploy"]))

    log = client.get(f"{API}/activity-log/", headers=owner).json()
    assert log["count"] == count_before + 1
    entry = log["data"][0]
    assert entry["action"] == "tag_merged"
    assert entry["entity_type"] == "tag"
    assert entry["entity_id"] == tags["deploy"]["id"]
    assert entry["restorable"] is False
    assert entry["details"] == {
        "name": "deploy",
        "sources": ["Deploy", "deploys"],
        "task_count": 2,
    }


def test_renaming_to_a_taken_name_is_still_refused(
    client: TestClient, owner: Headers
) -> None:
    _task(client, owner, ["deploy", "deploys"])
    tags = _tags(client, owner)

    r = client.patch(
        f"{API}/tags/{tags['deploys']['id']}",
        headers=owner,
        json={"name": "deploy"},
    )
    assert r.status_code == 409
    assert error_code(r) == "tag_exists"
    assert set(_tags(client, owner)) == {"deploy", "deploys"}


def test_counts_are_right_after_a_merge(client: TestClient, owner: Headers) -> None:
    _task(client, owner, ["deploy", "deploys"])
    _task(client, owner, ["deploys"])
    _task(client, owner, ["deploy"])
    _task(client, owner, ["other"])
    tags = _tags(client, owner)

    _merge(client, owner, tags["deploy"]["id"], _ids(tags["deploys"]))

    after = _tags(client, owner)
    assert after["deploy"]["task_count"] == 3
    assert after["other"]["task_count"] == 1
