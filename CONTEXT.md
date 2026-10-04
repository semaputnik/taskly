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

**Status**:
Where a task stands: **Backlog**, **To do**, **In progress**, **Waiting**,
**Review** or **Done** — six fixed values, not user-defined. Every rule that
cares whether work is finished only asks whether the task is **open** or Done.
_Avoid_: "state", "stage", "column".

**Open** (task):
A task whose status is Backlog, To do, In progress, Waiting or Review —
anything but Done. Overdue, "has open subtasks" and "the open occurrence" all
mean this.
_Avoid_: "not completed", "incomplete", "active".

**Backlog**:
An open status for a task the user has written down but not yet decided to
do; To do is that decision. Open like any other: its due date counts, it keeps
its parent from Done, and a recurring task in it is its series' one open
occurrence. Every new task starts here unless it is created with another
status; the next occurrence of a recurring task starts in To do instead.
_Avoid_: "someday", "icebox", "not started" (To do is also not started).

**Waiting**:
An open status for a task whose next move belongs to someone or something
other than the owner: a reply, a delivery, the result of someone else's work.
It is still open — waiting on something is not the work being finished — but it
is not work the owner can move right now. When the next move is the owner's,
the task is in **Review** instead.
_Avoid_: "blocked", "on hold", "control".

**Review**:
An open status for a task whose doer has finished and whose next move is the
owner's: check the work and close it, or send it back. It is how a bot user
hands finished work over. Status and assignee are separate: nothing moves a
task onto the owner because it entered Review.
_Avoid_: "waiting" (that is the other direction), "QA", "in review" as a flag
beside the status.

**My work**:
The dashboard's view of what is on the user: their tasks in To do, In
progress, Review or Waiting whose assignee is the user themselves, grouped by
status in the order work moves. Tasks with no assignee or on a bot user are
not in it, and neither is Backlog; the Tasks page is where those are managed.
_Avoid_: "inbox" (that is a project), "queue".

**Recurring task**:
A task whose move to Done spawns its next occurrence as a new task, on a
fixed-interval schedule (daily/weekly/monthly/every N days). Each occurrence
is its own task, not a status of one persistent task. At most one occurrence
of a given recurring task is **open** at a time — the next one is
never created while the current one is still open.
_Avoid_: treating a recurring task as a single task that "resets" — it does
not; moving it to Done produces a new task.

**Series**:
The occurrences of one recurring task, in order, and the schedule they keep
to. The schedule is anchored to a due date, and each occurrence's due date is a
whole number of intervals from that anchor — never counted from when the
previous one was done. Moving one occurrence's due date "only this
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
it off every task and cannot be undone. Two spellings of one idea are put
together by a **merge**: the tasks carrying one tag carry the other instead, and
the first tag is gone — like a deletion, it cannot be undone. Tags whose names
differ only in form (case, separators, a plural) are offered as **likely
duplicates**; the user merges a group or keeps it apart, and nothing is merged
on their behalf. Only the user renames, merges or deletes tags.
_Avoid_: treating a tag as text copied onto each task, or as something scoped
to a project.

**Reporter**:
Who filed a task — the user, or one of their **bot users**. The interface
calls it **Created by**. Every task has exactly one, and it is never the
request's to choose: it is whoever made the request that created the task.
Nothing changes it afterwards, so it is the only field on a task that no
edit can reach. Each **occurrence** of a recurring task carries the reporter
of the one before it — the **series** was filed once, and its occurrences are
that same work recurring.
_Avoid_: "author" (a **comment** has one of those, and it is a different
question), "creator", and treating it as a second **assignee** — the assignee
is who owes the work and can be changed; the reporter is a record of how the
task got here.

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

**Passkey**:
The one kind of credential a human user signs in with. It is bound to this
installation's hostname, made and kept by the user's device or password
manager, and Taskly holds nothing of it but its public key. A user holds one
or more, manages them in Settings, and can never remove the last one. Adding
or removing one takes a fresh passkey confirmation; a session on its own is
not enough.
_Avoid_: "password" (there are none), and "token" — a token belongs to a
**bot user**.

**Recovery code**:
What the superuser hands a user who has lost every passkey. One per user at
a time, good for a day, spent by creating a new passkey, and burned after five
wrong tries. It never opens a session by itself and never removes the passkeys
the user already has. The superuser's own code comes from the server's command
line, never from the interface.
_Avoid_: "reset", "temporary password".

**Sign out everywhere**:
Ending every session a user holds at once, on every device. Done by the user
from Settings, and done for them when a recovery code is spent. Removing a
passkey does not end sessions; this does.
_Avoid_: treating a passkey removal as a sign-out.

**Webhook** (of a bot user):
A URL the owner gives a bot user, which Taskly calls when something the bot
should act on has happened. A bot user has two, each optional and empty until
set: one for tasks that become **ready** for it, one for comments on tasks it
is **involved** in. Only the owner sets them, in the interface; a bot user
cannot read or change its own.
_Avoid_: "callback", "subscription", "notification".

**Ready** (task, for a bot user):
The moment a task comes to be in To do with that bot user as its assignee, by
anyone's change but the bot's own: created so, assigned while in To do, or
moved to To do while assigned. Leaving the state is not an event, and neither
is a restore or an unarchive that makes such a task visible again.
_Avoid_: "assigned" alone (assignment in another status is not it),
"triggered".

**Involved** (bot user, in a task):
A bot user is involved in a task when it is the task's assignee or reporter,
or has commented on it. A comment by anyone else on such a task reaches the
bot user's comment webhook.
_Avoid_: "subscribed", "watching".

**Delivery**:
One event on its way to one webhook: tried at once, then on a fixed schedule
for about two hours, then failed. Signed with the bot user's webhook secret.
The last delivery of each webhook is shown to the owner.
_Avoid_: "message", "notification".

**Paperless connection**:
A user's link to their own Paperless-ngx instance: its address and an API
token Taskly keeps but never shows again. Optional, off until set, one per
user. From the moment it is set, the user's PDF attachments are **kept in**
Paperless; unsetting it leaves them where they are, out of reach until it is
set again.
_Avoid_: "integration" (that is a bot user's word), "sync".

**Kept in** (attachment):
Where an attachment's bytes live: in Taskly, the default and the only place
for anything but a PDF, or in Paperless. A PDF on its way to Paperless is kept
in Taskly until Paperless has it, and stays there, saying why, if Paperless
would not take it. Taskly never deletes a document from Paperless: removing
an attachment kept there only drops the link.
_Avoid_: "uploaded to", "synced", "backend" (that is the code's word).
