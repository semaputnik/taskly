# Tags are managed entities, and only humans rename or delete them

Tags started as free text: a tag came into being by being typed onto a task and
stopped existing when no task carried it. That left the tag permissions a bot
user was supposed to have (FR-08.9) with nothing to govern, since there was no
operation on a tag other than putting it on a task (Q-16). We considered
mapping create, read, update and delete onto what a bot does to tags through
tasks, but every such reading was a stretch of the verbs rather than a real
operation.

We decided a tag is an entity of its own that the user can create, rename and
delete, from a Tags page. Typing a new name onto a task still creates a tag, so
quick entry stays as it was, and a tag with no tasks stays until it is deleted.
Tasks refer to a tag by key in the database, so a rename shows on every task at
once. Deleting a tag takes it off every task and is permanent: it is not a
deletion event and cannot be restored from the activity log, because bringing
back exactly the tasks it was on would pull the whole deletion-event machinery
into tags for little gain.

Renaming and deleting are for the user only. A tag belongs to the user, not to
a project, so renaming or deleting one changes tasks in every project, including
those outside a bot user's scope; no scope could allow it without breaking the
rule that a bot user never acts outside its projects. A bot user can be allowed
to create tags. It applies and removes them as part of creating or updating a
task, under the task permissions.

We accepted one departure from "a bot user learns nothing outside its scope":
a bot user reads its owner's whole tag vocabulary, with the number of tasks
each tag is on. Hiding tags that live only outside the scope would make the
same tag exist for one caller and not another, and the user preferred an
integration that can reuse their vocabulary to one that has to guess at it.

## Amendment (2026-09-16): counts split, merging, and who made a tag

The count a bot user reads is now two numbers rather than one: the live tasks
carrying a tag, which is what the task list filtered by it shows, and those
archived with their project (FR-01.26). The split tells a bot user nothing it
can act on — archived tasks stay out of its reach (FR-05.13) — and keeping one
answer for every caller mattered more than hiding it.

Merging tags (FR-01.27) joins renaming and deleting as an act only the user
performs, for the same reason: it rewrites tasks in every project. Names stay
case-sensitive and unique; merging is an operation over that model, not a
loosening of it.

Which bot user created a tag (FR-01.28) is reported to the user only. A bot
user reading the vocabulary gets no word about which of its owner's other
integrations added what.
