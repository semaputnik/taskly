"""
One rule, independently written three times (#321): a `tasks_bulk_changed`
entry whose `changes.status` is `done` counts as a completion rather than a
plain status move. `app.activity_log._BULK_COMPLETION` is what the log's
own `kind=completed` filter narrows by; `app.mcp.tools.search_activity.
_describe_batch_changes` decides whether the MCP tool's narration calls the
same entry "completed"; `frontend/src/components/Activity/entryWords.ts`'s
own `describeBatch` decides it a third time, for the web UI. Nothing ties
the three together, and a shared constant cannot cross the Python/
TypeScript line here — see `_describe_batch_changes`'s own docstring for
why the generated client carries the shape (`TasksBulkChangedDetailsPublic`,
`TaskStatus`) but not the rule itself, which is a function, not a schema.

So this is the fix the issue itself calls the cheapest honest one: a test
that fails the moment the filter and a narration disagree, rather than an
abstraction that only discourages drift. It builds one real batch entry per
status Taskly has (plus one batch that changes something else entirely),
reads it back through the real `kind=completed` filter, and runs the real
MCP narration over the entry's own stored `changes` dict — never a
hand-built one either side could get subtly wrong in the same way.

The third site, the frontend narration, cannot run from a Python test at
all — no Python process can import a TypeScript module.
`frontend/src/components/Activity/entryWords.test.ts`'s own
`tasks_bulk_changed` cases are what stand guard there, and `describeBatch`'s
own docstring points back here, the way this file's functions point at it.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.mcp.tools.search_activity import _describe_batch_changes
from app.models import TaskStatus
from tests.utils.accounts import create_project, create_task, create_user_headers

API = settings.API_V1_STR

# Every status Taskly has, plus `None` standing for a batch that changed
# something else entirely (no `status` key at all) — the one case the
# predicate and the narration both have to leave out of "completed" too.
_CASES: list[TaskStatus | None] = [*TaskStatus, None]


@pytest.mark.parametrize("status", _CASES, ids=lambda s: s.value if s else "no_status")
def test_the_completed_filter_and_the_mcp_narration_agree(
    client: TestClient, db: Session, status: TaskStatus | None
) -> None:
    owner = create_user_headers(client, db)
    project_id = create_project(client, owner)
    ids = [
        create_task(client, owner, project_id=project_id, title=f"T{n}")
        for n in range(2)
    ]
    if status is not None:
        # Every task starts in Backlog. A batch that "changes" a task to the
        # status it is already in writes no entry at all (`app.activity._write`
        # only logs a transaction that actually changed something) — which
        # would make this test pass for the wrong reason, by finding no entry
        # rather than finding one both sides agree about. An intermediate move
        # to some other status first guarantees the batch under test is a
        # real transition, whatever status it targets.
        intermediate = (
            TaskStatus.TODO if status is not TaskStatus.TODO else TaskStatus.WAITING
        )
        r = client.post(
            f"{API}/tasks/bulk",
            headers=owner,
            json={"task_ids": ids, "status": intermediate.value},
        )
        assert r.status_code == 200, r.text
        body: dict[str, Any] = {"task_ids": ids, "status": status.value}
    else:
        body = {"task_ids": ids, "priority": "P1"}
    r = client.post(f"{API}/tasks/bulk", headers=owner, json=body)
    assert r.status_code == 200, r.text

    completed = client.get(
        f"{API}/activity-log/", headers=owner, params={"kind": "completed"}
    ).json()
    filter_says_completion = any(
        e["action"] == "tasks_bulk_changed" for e in completed["data"]
    )

    # Newest first (the feed's default order): the batch under test, not the
    # intermediate move also made above for statuses other than `None`.
    everything = client.get(f"{API}/activity-log/", headers=owner).json()["data"]
    [raw_entry, *_] = [e for e in everything if e["action"] == "tasks_bulk_changed"]
    narrated = _describe_batch_changes(raw_entry["details"]["changes"])
    narration_says_completion = "completed" in narrated

    assert filter_says_completion == narration_says_completion, (
        f"status={status}: kind=completed filter said {filter_says_completion}, "
        f"but the MCP narration ({narrated!r}) said {narration_says_completion}"
    )
