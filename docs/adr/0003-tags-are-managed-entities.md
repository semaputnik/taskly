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
