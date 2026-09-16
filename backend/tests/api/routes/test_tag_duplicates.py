"""
Likely duplicate tags, offered for merging and never merged on their own
(semaputnik/taskly#69).
"""

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


def _groups(client: TestClient, headers: Headers) -> list[list[str]]:
    r = client.get(f"{API}/tags/duplicates", headers=headers)
    assert r.status_code == 200, r.text
    return [sorted(tag["name"] for tag in group["tags"]) for group in r.json()["data"]]


def _dismiss(client: TestClient, headers: Headers, tag_ids: list[str]) -> Any:
    return client.post(
        f"{API}/tags/duplicates/dismiss", headers=headers, json={"tag_ids": tag_ids}
    )


@pytest.mark.parametrize(
    "names",
    [
        # Letter case.
        ["deploy", "Deploy", "DEPLOY"],
        # Separators: hyphens, underscores and spaces read as one.
        ["deploy-bot", "deploy_bot", "deploy bot"],
        # Repeated whitespace inside a name.
        ["deploy  bot", "deploy bot"],
        # A trailing plural.
        ["deploy", "deploys"],
        # All of it at once.
        ["Deploy-Bots", "deploy bot"],
    ],
)
def test_names_that_differ_only_in_form_are_offered_together(
    client: TestClient, owner: Headers, names: list[str]
) -> None:
    for name in names:
        _tag(client, owner, name)
    _tag(client, owner, "release")

    assert _groups(client, owner) == [sorted(names)]


def test_distinct_names_are_not_grouped(client: TestClient, owner: Headers) -> None:
    for name in ("deploy", "deployment", "bus", "bu", "release"):
        _tag(client, owner, name)

    assert _groups(client, owner) == []


def test_a_group_carries_each_tags_counts(client: TestClient, owner: Headers) -> None:
    client.post(f"{API}/tasks/", headers=owner, json={"title": "T", "tags": ["Deploy"]})
    _tag(client, owner, "deploy")

    r = client.get(f"{API}/tags/duplicates", headers=owner)
    tags = {tag["name"]: tag for tag in r.json()["data"][0]["tags"]}
    assert tags["Deploy"]["task_count"] == 1
    assert tags["deploy"]["task_count"] == 0


def test_the_whole_vocabulary_is_searched(client: TestClient, owner: Headers) -> None:
    # Far more tags than a page of the tag list holds, with the pair at
    # opposite ends of it.
    _tag(client, owner, "aaa deploy")
    for i in range(120):
        _tag(client, owner, f"filler {i:03}")
    _tag(client, owner, "zzz")
    _tag(client, owner, "AAA-deploys")

    assert _groups(client, owner) == [["AAA-deploys", "aaa deploy"]]


def test_a_dismissed_group_stops_being_offered(
    client: TestClient, owner: Headers
) -> None:
    deploy = _tag(client, owner, "deploy")
    deploys = _tag(client, owner, "deploys")
    _tag(client, owner, "Release")
    _tag(client, owner, "release")

    r = _dismiss(client, owner, [deploy["id"], deploys["id"]])
    assert r.status_code == 200, r.text

    assert _groups(client, owner) == [["Release", "release"]]
    # Nothing was merged: dismissing only stops the suggestion.
    names = {t["name"] for t in client.get(f"{API}/tags/", headers=owner).json()["data"]}
    assert {"deploy", "deploys"} <= names


def test_a_dismissed_group_is_offered_again_once_a_member_is_renamed(
    client: TestClient, owner: Headers
) -> None:
    deploy = _tag(client, owner, "deploy")
    deploys = _tag(client, owner, "deploys")
    _dismiss(client, owner, [deploy["id"], deploys["id"]])

    client.patch(
        f"{API}/tags/{deploys['id']}", headers=owner, json={"name": "Deploys"}
    )

    assert _groups(client, owner) == [["Deploys", "deploy"]]


def test_a_dismissed_group_is_offered_again_when_another_spelling_joins(
    client: TestClient, owner: Headers
) -> None:
    deploy = _tag(client, owner, "deploy")
    deploys = _tag(client, owner, "deploys")
    _dismiss(client, owner, [deploy["id"], deploys["id"]])

    _tag(client, owner, "Deploy")

    assert _groups(client, owner) == [["Deploy", "deploy", "deploys"]]


def test_only_a_whole_current_group_can_be_dismissed(
    client: TestClient, db: Session, owner: Headers
) -> None:
    deploy = _tag(client, owner, "deploy")
    deploys = _tag(client, owner, "deploys")
    Deploy = _tag(client, owner, "Deploy")
    release = _tag(client, owner, "release")
    theirs = _tag(client, create_user_headers(client, db), "deploys")

    for tag_ids in (
        [deploy["id"], deploys["id"]],  # a part of the group
        [deploy["id"], release["id"]],  # not a group at all
        [deploy["id"]],  # one tag
        [deploy["id"], theirs["id"]],  # another user's tag
    ):
        assert _dismiss(client, owner, tag_ids).status_code in (404, 422), tag_ids

    assert _groups(client, owner) == [["Deploy", "deploy", "deploys"]]
    assert _dismiss(
        client, owner, [Deploy["id"], deploys["id"], deploy["id"]]
    ).status_code == 200
    assert _groups(client, owner) == []


def test_groups_are_the_callers_own(
    client: TestClient, db: Session, owner: Headers
) -> None:
    _tag(client, owner, "deploy")
    other = create_user_headers(client, db)
    _tag(client, other, "deploys")

    assert _groups(client, owner) == []
    assert _groups(client, other) == []


def test_a_bot_user_neither_reads_nor_dismisses_groups(
    client: TestClient, owner: Headers
) -> None:
    project_id = create_project(client, owner)
    bot = issue_bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    deploy = _tag(client, owner, "deploy")
    deploys = _tag(client, owner, "deploys")

    for r in (
        client.get(f"{API}/tags/duplicates", headers=bot),
        _dismiss(client, bot, [deploy["id"], deploys["id"]]),
    ):
        assert r.status_code == 403
        assert error_code(r) == "human_only"
    assert _groups(client, owner) == [["deploy", "deploys"]]
