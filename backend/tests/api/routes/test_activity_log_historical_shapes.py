"""
The log is kept for ever (FR-10.5), so `details` holds rows written under
shapes `app.activity_details` (#299) did not exist to declare. These two are
taken verbatim from `git show bf776bf^:backend/app/activity.py` — the commit
that replaced a plain `completed: bool` with four task statuses and gave
`task_reopened` a destination (#99) — written straight into the table rather
than produced by the current writer, which cannot produce them any more.

Both `GET /activity-log/` and `search_activity` must still answer over a log
that contains them: a reader built only from shapes the current writer
produces would never catch a decode failure this real, and the whole point
of #299's historical-compatibility fix (`extra="ignore"`, the two optional
late fields, `to_public`'s own fallback) is that one old row never costs the
page it would otherwise 500.
"""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.mcp.tools.search_activity import search_activity_body
from app.models import ActivityAction, ActivityEntityType, ActivityEntry
from tests.utils.accounts import (
    ALL_PERMISSIONS,
    create_project,
    create_task_record,
    create_user_headers,
    my_id,
)
from tests.utils.mcp import bot_headers
from tests.utils.mcp_body import caller_for

API = settings.API_V1_STR

# The exact two historical shapes (`git show bf776bf^:backend/app/activity.py`):
# a `task_created` snapshot recording `completed` rather than `status`, and a
# `task_reopened` entry with no destination at all.
_OLD_SNAPSHOT = {
    "title": "Call the bank",
    "description": None,
    "due_date": None,
    "priority": None,
    "completed": False,
    "project": None,
    "assignee_id": None,
    "assignee": None,
    "tags": [],
    "recurrence": None,
}


def _insert(
    db: Session, owner_id: uuid.UUID, entity_id: uuid.UUID, action: str, details: dict
) -> None:
    db.add(
        ActivityEntry(
            owner_id=owner_id,
            actor_id=owner_id,
            action=action,
            entity_type=ActivityEntityType.TASK,
            entity_id=entity_id,
            details=details,
        )
    )


def test_get_activity_log_answers_over_pre_statuses_rows(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    owner_id = uuid.UUID(my_id(client, owner))
    project_id = create_project(client, owner, "Errands")
    task = create_task_record(client, owner, "Call the bank", project_id=project_id)
    task_id = uuid.UUID(task["id"])

    _insert(
        db,
        owner_id,
        task_id,
        ActivityAction.TASK_CREATED,
        {"title": "Call the bank", "task": _OLD_SNAPSHOT},
    )
    _insert(
        db, owner_id, task_id, ActivityAction.TASK_REOPENED, {"title": "Call the bank"}
    )
    db.commit()

    r = client.get(f"{API}/activity-log/", headers=owner)
    assert r.status_code == 200, r.text
    actions = [entry["action"] for entry in r.json()["data"]]
    assert "task_created" in actions
    assert "task_reopened" in actions


def test_search_activity_answers_over_pre_statuses_rows(
    client: TestClient, db: Session
) -> None:
    owner = create_user_headers(client, db)
    owner_id = uuid.UUID(my_id(client, owner))
    project_id = create_project(client, owner, "Errands")
    task = create_task_record(client, owner, "Call the bank", project_id=project_id)
    task_id = uuid.UUID(task["id"])
    headers = bot_headers(
        client, owner, project_ids=[project_id], permissions=ALL_PERMISSIONS
    )
    caller = caller_for(db, headers)

    _insert(
        db,
        owner_id,
        task_id,
        ActivityAction.TASK_CREATED,
        {"title": "Call the bank", "task": _OLD_SNAPSHOT},
    )
    _insert(
        db, owner_id, task_id, ActivityAction.TASK_REOPENED, {"title": "Call the bank"}
    )
    db.commit()

    result = search_activity_body(db, caller)
    whats = [row["what"] for row in result["entries"]]
    assert "Created" in whats
    assert "Reopened" in whats
