# A task has four fixed statuses, and Waiting is open

A task used to be completed or not (FR-01.4). That collapsed three different
open situations into one: work not started, work under way, and work whose
next move belongs to someone else. The dashboard nagged the owner about tasks
they could not move, and neither the owner nor a bot user could say "I am on
this" (semaputnik/taskly#97).

We replaced `completed` with a `status` of four values: `todo`,
`in_progress`, `waiting` and `done`.

**Fixed, not user-defined.** Every rule in the product — the subtasks prompt,
the next occurrence of a recurring task, the overdue filter, the one open
occurrence per series — only needs to know whether a task is finished. With a
fixed set, "open" is a property of the value, and each rule keeps one
condition. User-defined statuses would need a way to say which of a user's
statuses count as done, per user, and every rule would have to read that
mapping; bot integrations would also have to discover each installation's
vocabulary before they could set a status. A personal tracker does not need
that, so we took the smallest set that tells the owner's situations apart.

**Waiting is open.** A task someone else holds is not finished: it still has a
due date that matters, it still blocks closing its parent, and a recurring
task in it has not produced its next occurrence. Treating Waiting as closed
would let a task quietly drop out of view while nothing was happening to it.
What changes for Waiting is only where the dashboard shows it, which is a
matter for the interface, not the model.

**No `completed` alias.** Keeping `completed` beside `status` would give the
API two sources of truth that a client could set to contradict each other
(`completed: false, status: done`), and every write would need rules for which
wins. The installation belongs to its owner, who also owns the integrations
that call it, so we removed the field and updated the integrations rather than
carry the ambiguity. The error code `task_has_uncompleted_subtasks` and the
`leave_uncompleted` value are kept as they were, because clients match on them
and their meaning did not change.

Moves to and out of Done are still logged as `task_completed` and
`task_reopened`, so existing entries read as they always did. A move between
open statuses is a new `task_status_changed` entry that names both ends.
