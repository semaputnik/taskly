# Taskly

A personal task tracker where a user's tasks can also be operated on by AI
agents and other integrations acting as bot users through a REST API.

## Language

**Archived project**:
A project a human user has hidden from daily use without deleting it.
Read-only for the human, invisible and inaccessible to any bot user, and
hidden from default task views. Toggled directly and instantly by the user —
not part of the deletion/restore flow. Archiving a project archives its tasks
with it.
_Avoid_: using "archived" as a synonym for "deleted" — they are different
states that can't overlap.

**Deleted** (task or project):
Soft-deleted: removed from normal views, recorded in the activity log, and
restorable from there. Deleting a task or project also deletes everything it
contains (subtasks, or a project's tasks).
_Avoid_: "archived" for this state.

**Recurring task**:
A task whose completion spawns its next occurrence as a new task, on a
fixed-interval schedule (daily/weekly/monthly/every N days). Each occurrence
is its own task, not a status of one persistent task. At most one occurrence
of a given recurring task is open (not completed) at a time — the next one is
never created while the current one is still open.
_Avoid_: treating a recurring task as a single task that "resets" — it does
not; completing it produces a new task.

**Series**:
The occurrences of one recurring task, in order, and the schedule they keep
to. The schedule is anchored to a due date, and each occurrence's due date is a
whole number of intervals from that anchor — never counted from when the
previous one was completed. Moving one occurrence's due date "only this
occurrence" leaves the anchor where it was; "this and all following" moves it.
Only the latest occurrence of a series can be open.
_Avoid_: "template" or "parent" for the series — no occurrence is special, and
none of them is the pattern the others are stamped from.

**Activity log**:
The record of every change in Taskly. Each user sees only their own log —
including the superuser, who has no visibility into other users' logs.
_Avoid_: "audit log" (implies cross-user oversight, which does not exist here).

**Subtask**:
A task that is a child of another task, nestable to any depth. A subtask is
a full task — every field, and everything a task supports — never a reduced
checklist item. It holds no project of its own: it belongs to the project of
its **root task**, so a subtask can never sit in a different project from
its parent, and moving the root moves the whole tree.
_Avoid_: "checklist item", or treating a subtask as a lesser kind of task.

**Root task**:
The task at the top of a tree — the one with no parent. The only task in a
tree that records a project; every subtask below it derives that project.
_Avoid_: "parent task" for this — any task with subtasks is a parent, but
only the topmost one is the root.

**Deletion event**:
One act of deleting, and everything it took down. Deleting cascades — a task
takes its subtasks, a project takes its tasks — and every row that went down
together points at the same event, so restoring brings back exactly those
rows. A subtask deleted on its own earlier belongs to its own event and stays
deleted when its parent is restored.
_Avoid_: reading a row's deleted state as a bare flag — it is always tied to
the event that caused it.

**Tag**:
A free-text label a user puts on a task. A tag comes into being by being
typed onto a task and belongs to the **user**, not to a project, so it means
the same thing across their whole account and can gather work that crosses
projects. Applying, removing and autocompleting is all the management there
is: a tag no task carries any more simply stops existing.
_Avoid_: treating tags as a taxonomy to be set up in advance, or as something
scoped to a project.
