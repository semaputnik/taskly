# A bot user may read the activity log, narrowed to its scope

"Bot users reading the activity log" was out of scope until now (`docs/features.md`,
§6). The reason to open it is not a preference for symmetry with human users:
it is that the owner wants an integration to analyse finished work — what got
closed last week, how long tasks sit before they are done — and a task has
nowhere to answer from. A task records `created_at` and a current status, and
nothing else; there is no `completed_at`. The only row that says a task moved
to Done, and when, is the activity log: a `task_completed` entry, or a batch
entry naming `done` as the new status.

We had already ruled out giving a bot user the log at all, on the general
principle that it is far weaker than its owner and the log is the owner's own
history. We reopen that decision rather than work around it, because the
workaround was worse: denormalising a `completed_at` column onto `Task` would
duplicate a fact the log already keeps, for ever, by design (FR-10.5). Every
place that writes a task to Done would have to also set and clear that
column correctly through every path that moves a task in and out of Done —
batches, recurrence, restores — and the two records could drift. The log is
already append-only and authoritative; teaching a second place to agree with
it is the wrong fix for "a bot user cannot read the first place."

## Decision

A new grant, `read_activity`, added to a bot user's permissions by #250
(migration `366dff4941fb`), off by default like every other permission.
`GET /activity-log/` moves onto the shared caller dependency, the way tasks,
comments and tags already are: a human session reads exactly what it always
has, byte for byte, and a bot user with the grant reads the same endpoint
narrowed to its scope. The narrowing lives in `app.api.access`, the one place
a bot user's reach is decided, in the order that module already checks
things in: the archive, then the scope, then the permission.

A bot user's view of the log is not simply "entries about tasks in scope." It
also includes:

- the projects of its scope themselves;
- comments and attachments on tasks in scope;
- a task's deletion and restore, which the entry locates by the project it
  carries in its `details` rather than by a live task row, so a deleted
  task's history still reads;
- tag entries (`tag_created`, `tag_renamed`, `tag_deleted`, `tag_merged`),
  because a bot user already reads its owner's whole tag vocabulary
  whatever its scope (ADR-0003), so these leak nothing new;
- entries made by any actor — the owner, the bot user itself, or another of
  the owner's bot users — because the point is to read the owner's work, not
  only the bot's own.

And it excludes:

- anything touching an archived project, whatever the scope lists
  (FR-05.13), checked before the scope itself is even read;
- a batch entry (`tasks_bulk_changed`) unless every task it names is in
  scope. Closing several tasks at once is logged as the one act it was, not
  one entry per task (FR-10.9), so there is no way to show "the part of this
  act that happened in scope" without describing a batch that never
  happened. It is shown whole or not at all.

A bot user's response also omits `restorable` and the deletion id that a
human's carries. Restoring stays a human-only action (`POST
/activity-log/{entry_id}/restore` is untouched); a field a bot user cannot
act on is a handle worth removing, not a dead one worth keeping.

## Built once over the scope

The existing single-project narrowing (`project_id`) builds its condition by
reaching for the one project named. A scope has several projects, and the log
is kept for ever (FR-10.5), so the obvious shape — OR the single-project
filter once per project in the scope — would mean a query whose cost grows
with the size of the scope, running forever against a table that only grows.
Instead, the scope's condition is built once, over the whole set of projects
at once (their ids, and the tasks of all of them from one recursive walk),
and rides the same indexes a human's read already does: the base owner
filter on `ix_activityentry_owner_id_position`, and the entity and task
lookups on `ix_activityentry_owner_id_entity_id` and
`ix_activityentry_owner_id_task`.

## Consequence

Narrowing the log by a task or project id a bot user cannot reach — missing,
someone else's, archived, or simply outside the scope — answers 404, the same
as a missing one, never a 403 that would confirm the id is real and never an
empty feed that would look like a history with nothing in it. This is
narrower than how a direct fetch of that task or project behaves elsewhere in
the API (a 403 naming the scope or the archive); the log's own narrowing is a
read of a listing, not a fetch of a resource, and the choice here is to tell
a bot nothing about ids it cannot use rather than to explain why.
