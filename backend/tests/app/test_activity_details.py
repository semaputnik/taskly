"""
`app.activity_details` (#299): the activity log's one decoded shape, pure —
no database, since `encode`/`decode` round-trip a Pydantic model through the
same dict `ActivityEntry.details` stores, with nothing but Python types in
between.
"""

import uuid

from app.activity_details import (
    _DETAIL_MODELS,
    _PUBLIC_DETAIL_MODELS,
    DETAILS_TASK_IDS,
    AssigneeRef,
    FieldChange,
    ProjectRef,
    TaskCreatedDetails,
    TaskDeletedBatch,
    TaskDeletedSingle,
    TaskReopenedDetails,
    TasksBulkChangedDetails,
    TaskSnapshot,
    decode,
    encode,
    named_task_ids,
    to_public,
)
from app.models import ActivityAction, ActorKind, TaskStatus


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


def test_decode_ignores_a_key_this_shape_no_longer_declares() -> None:
    """
    The log is kept for ever (FR-10.5), so `details` holds rows written
    under shapes this module's own history no longer matches — `extra=
    "ignore"` drops a retired key rather than refusing the whole row over
    it (a stricter `"forbid"` would make `decode` reject the user's own
    history, confirmed below against the two real pre-statuses shapes).
    """
    decoded = decode(ActivityAction.TAG_CREATED, {"name": "urgent", "mystery": True})
    assert decoded.name == "urgent"


def test_assignee_ref_omits_name_for_a_user_through_a_full_round_trip() -> None:
    """
    A user assignee's `name` is never written at all — the one asymmetry
    this shape preserves (`AssigneeRef`'s own docstring) — through storage
    and back, not just at construction: `decode` then `encode` again must
    not reintroduce the key `model_dump` would otherwise default in.
    """
    ref = AssigneeRef(type=ActorKind.USER, id=uuid.uuid4())
    stored = encode(ref)  # type: ignore[arg-type]
    assert "name" not in stored

    decoded = decode(
        ActivityAction.TASK_ASSIGNED,
        {"title": "Ship it", "assignee_id": str(ref.id), "assignee": stored},
    )
    assert "name" not in encode(decoded).get("assignee", {})


# --- History: the log is kept for ever, and these two shapes predate this
# module by several years (#299's historical-compatibility fix). Taken
# verbatim from `git show bf776bf^:backend/app/activity.py` — the commit
# that replaced `completed: bool` with `status` and gave `task_reopened` a
# destination (#99) — rather than from memory.


def test_a_pre_statuses_task_created_snapshot_still_decodes() -> None:
    """
    Before #99, `_snapshot` wrote `"completed": state.completed` and no
    `"status"` key at all. `extra="ignore"` drops the retired key;
    `TaskSnapshot.status` being optional means the row still decodes with
    nothing to say about a status it was never given.
    """
    old_snapshot = {
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
    decoded = decode(
        ActivityAction.TASK_CREATED,
        {"title": "Call the bank", "task": old_snapshot},
    )
    assert isinstance(decoded, TaskCreatedDetails)
    assert decoded.task.status is None
    assert decoded.task.title == "Call the bank"


def test_a_pre_statuses_task_reopened_entry_still_decodes() -> None:
    """Before #99, `task_reopened` carried only a title — no `to` at all,
    since there was only the one open status to go back to."""
    decoded = decode(ActivityAction.TASK_REOPENED, {"title": "Call the bank"})
    assert isinstance(decoded, TaskReopenedDetails)
    assert decoded.to is None


def test_to_public_degrades_a_pre_statuses_entry_rather_than_raising() -> None:
    """
    `to_public` is the boundary a malformed or historically-drifted row
    must not cross uncaught: a row this module cannot make sense of hands
    back `UnrecognizedDetailsPublic` rather than failing the whole page it
    would otherwise take down with it. (These two old shapes in particular
    decode fine today — see the two tests above — so this exercises the
    fallback directly with a shape that deliberately moves further than
    even `extra="ignore"` tolerates: a `task_reopened` with a `to` that is
    not a real status value at all.)
    """
    public = to_public(
        ActivityAction.TASK_REOPENED, {"title": "x", "to": "not-a-status"}
    )
    assert public == {"kind": "unrecognized"}


def test_every_internal_model_has_a_public_counterpart_with_the_same_fields() -> None:
    """
    `*DetailsPublic` subclasses its `*Details` counterpart purely to add
    `kind` — a field added to one and forgotten on the other (the likely
    edit, since a deletion and its restore describe the same thing) would
    otherwise only surface as a generated-client type that silently lacks
    a field, not as a test failure.
    """
    for action, internal in _DETAIL_MODELS.items():
        internals = internal if isinstance(internal, tuple) else (internal,)
        publics = _PUBLIC_DETAIL_MODELS[action]
        assert len(internals) == len(publics), action
        for internal_model, public_model in zip(internals, publics, strict=True):
            assert set(public_model.model_fields) - {"kind"} == set(
                internal_model.model_fields
            ), (internal_model, public_model)


def test_the_two_deletion_twins_and_the_two_project_twins_share_their_fields() -> None:
    """
    `TaskDeletedSingle`/`TaskRestoredSingle`, `TaskDeletedBatch`/
    `TaskRestoredBatch` and `ProjectDeletedDetails`/`ProjectRestoredDetails`
    are each field-for-field identical on purpose — a deletion and its
    restore describe the same thing — kept as distinct classes because
    their names are what the generated client's discriminated union is
    keyed on, not aliased into one. A field added to one of a pair and
    forgotten on the other is the likely edit this guards against.
    """
    from app.activity_details import (
        ProjectDeletedDetails,
        ProjectRestoredDetails,
        TaskRestoredBatch,
        TaskRestoredSingle,
    )

    for left, right in (
        (TaskDeletedSingle, TaskRestoredSingle),
        (TaskDeletedBatch, TaskRestoredBatch),
        (ProjectDeletedDetails, ProjectRestoredDetails),
    ):
        assert set(left.model_fields) == set(right.model_fields), (left, right)


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
