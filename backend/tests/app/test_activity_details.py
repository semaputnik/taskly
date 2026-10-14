"""
`app.activity_details` (#299): the activity log's one decoded shape, pure —
no database, since `encode`/`decode` round-trip a Pydantic model through the
same dict `ActivityEntry.details` stores, with nothing but Python types in
between.
"""

import uuid

import pytest
from pydantic import ValidationError

from app.activity_details import (
    AssigneeRef,
    DETAILS_TASK_IDS,
    FieldChange,
    ProjectRef,
    TaskCreatedDetails,
    TaskDeletedBatch,
    TaskDeletedSingle,
    TaskSnapshot,
    TasksBulkChangedDetails,
    decode,
    encode,
    named_task_ids,
)
from app.models import ActivityAction, TaskStatus


def test_encode_decode_round_trips_a_task_created_entry() -> None:
    details = TaskCreatedDetails(
        title="Ship it",
        task=TaskSnapshot(
            title="Ship it",
            status=TaskStatus.TODO,
            project=ProjectRef(id=uuid.uuid4(), name="Launch"),
            assignee=AssigneeRef(type="bot_user", id=uuid.uuid4(), name="Shipper"),
        ),
    )
    stored = encode(details)

    # The stored shape is plain JSON: a project's id is a string, not a UUID.
    assert isinstance(stored["task"]["project"]["id"], str)

    decoded = decode(ActivityAction.TASK_CREATED, stored)
    assert decoded == details


def test_field_change_round_trips_the_reserved_word_key() -> None:
    """`from` is a Python keyword; the stored dict still spells it that way."""
    change = FieldChange(**{"from": "To do", "to": "Done"})
    stored = encode(change)  # type: ignore[arg-type]
    assert stored == {"from": "To do", "to": "Done"}

    decoded = FieldChange.model_validate(stored)
    assert decoded.from_ == "To do"
    assert decoded.to == "Done"


def test_decode_tells_a_single_task_deletion_from_a_batch_by_title() -> None:
    """
    ADR-0011's all-or-nothing batch, made checkable: a batch's own shape
    (`TaskDeletedBatch`) has no `title` field to declare at all, so the two
    shapes that share `task_deleted`'s action can only be told apart by the
    one thing the data itself says.
    """
    single = decode(
        ActivityAction.TASK_DELETED,
        {"title": "Ship it", "project": None, "parent_id": None, "subtask_count": 0},
    )
    assert isinstance(single, TaskDeletedSingle)

    batch = decode(ActivityAction.TASK_DELETED, {"task_count": 3})
    assert isinstance(batch, TaskDeletedBatch)


def test_task_deleted_single_carries_its_project() -> None:
    """ADR-0011's other checkable assumption: a deleted task's own entry
    carries the project it was in, since the live row is gone."""
    project_id = uuid.uuid4()
    details = decode(
        ActivityAction.TASK_DELETED,
        {
            "title": "Ship it",
            "project": {"id": str(project_id), "name": "Launch"},
            "parent_id": None,
            "subtask_count": 0,
        },
    )
    assert isinstance(details, TaskDeletedSingle)
    assert details.project == ProjectRef(id=project_id, name="Launch")


def test_decode_rejects_an_undeclared_field() -> None:
    """A field that reaches `details` without being declared on its action's
    model fails loudly at decode time, rather than reading as silently
    absent in whichever reader happens to look for it."""
    with pytest.raises(ValidationError):
        decode(ActivityAction.TAG_CREATED, {"name": "urgent", "mystery": True})


def test_named_task_ids_reads_a_bulk_change_batch() -> None:
    task_ids = [uuid.uuid4(), uuid.uuid4()]
    details = encode(
        TasksBulkChangedDetails(
            task_count=2,
            task_ids=tuple(str(t) for t in task_ids),
            changes={"status": "done"},
        )
    )
    assert details[DETAILS_TASK_IDS] == [str(t) for t in task_ids]
    assert named_task_ids(ActivityAction.TASKS_BULK_CHANGED, details) == task_ids


def test_named_task_ids_is_empty_for_actions_that_name_only_their_own_entity() -> None:
    assert named_task_ids(ActivityAction.TASK_COMPLETED, {"title": "Ship it"}) == []
