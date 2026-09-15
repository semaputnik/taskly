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
The record of every change in Taskly. Each entry names who made the change:
the user, or the one of their **bot users** that made it — a bot user's change
is never recorded as its owner's. Each user sees only their own log —
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
A named label a user puts on tasks. It belongs to the **user**, not to a
project, so it means the same thing across their whole account and can gather
work that crosses projects. A tag is created on the Tags page or by typing a
new name onto a task, and it stays until the user deletes it, whether or not
any task carries it. Renaming a tag renames it on every task; deleting it takes
it off every task and cannot be undone. Only the user renames or deletes tags.
_Avoid_: treating a tag as text copied onto each task, or as something scoped
to a project.

**Bot user**:
An identity a user creates for an AI agent or other integration, deliberately
far weaker than a human user. It works only through the REST API with its
**token**, and only inside its **scope**. It is not a kind of user account: it
has no email or password, cannot log in, register or reset a password, and
does not appear among the accounts the superuser can list. Creating and
configuring bot users is a human action in the web UI — a bot user can never
create or configure another bot user, or itself. A task can be assigned to one
of its owner's bot users, to show which integration is responsible for it. A
deleted bot user is kept, not removed, and deleting one cannot be undone: its
token stops working at once, it stays assigned to what it had and takes nothing
new, and what it did still names it. A bot
user's comments name it as their author and are append-only: nobody, its owner
included, can edit or delete them.
_Avoid_: "service account", "API key", "integration user".

**Owner** (of a bot user):
The one user who created a bot user. A bot user reaches only its owner's data,
and never more of it than its scope allows; there is no way for it to reach
another user's.
_Avoid_: using "owner" for who can see a task or project — for those, the user
they belong to is simply the user.

**Scope**:
What a bot user may reach and do: an explicit list of the owner's projects,
each named one by one with no "all projects" value, and the permissions it
holds there — create, read, update and delete on tasks, adding comments, and
creating tags.
Anything a bot user can never do has no permission to grant at all. An
archived project is out of reach whatever the scope says, and a subtask is in
scope exactly when its root task's project is. The user can change a scope at
any time, and it holds from the bot user's next request. A deleted project
drops out of every scope while it is deleted and is back where it was if it is
restored.
_Avoid_: "role" — a scope is set per bot user, not picked from shared roles.

**Token** (of a bot user):
The bearer credential a bot user sends with every request. A bot user holds at
most one. It is shown once, when it is issued, and stored only as a digest, so
it can never be shown again. It may carry an expiry, and the user can revoke
it at any moment; replacing it is always a revoke followed by a fresh issue,
never an overwrite. An expired or revoked token is refused exactly like one
that never existed. When it was last used is recorded approximately. Not interchangeable with a human's session: a
human session is not a bot token, and a bot token opens no endpoint that only a
human may call.
_Avoid_: "password", "session" for a bot user's credential.
