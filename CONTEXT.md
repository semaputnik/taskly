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

**Activity log**:
The record of every change in Taskly. Each user sees only their own log —
including the superuser, who has no visibility into other users' logs.
_Avoid_: "audit log" (implies cross-user oversight, which does not exist here).
