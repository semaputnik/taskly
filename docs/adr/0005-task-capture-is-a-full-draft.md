# Task capture is a full draft, committed in one request

Capture (semaputnik/taskly#63) replaced the Add Task dialog with the task's own
panel, opened before the record exists and showing only the title. Everything
else appeared after Enter had created the task, and each property was then
its own save. That held back three guarantees: a half-written task is never
visible to a bot user, a created task is one entry in the activity log, and an
accidental open leaves nothing behind. It also made a user who already knew
the date, priority or project wait for a second step, and the panel jumped
from one row to nine at the moment of creation (semaputnik/taskly#94).

We decided the new-task panel opens in the task's full layout as a **draft**.
Every property a task has at creation is editable at once. The draft is held
in the browser and nothing is sent while it is filled in. It is committed by
one explicit, visible act — Enter in the title, or a **Create task** button —
and that act sends one create request with the whole draft, which the API
already accepted. ⌘/Ctrl+Enter commits and starts another draft, carrying the
properties over. A single commit closes the panel and leaves a notice with an
**Open** action for the new task, rather than turning the panel into the new
record: the reader was writing something down, not starting to edit it.

This keeps #63's guarantees without its restriction. No request means no
half-written task for a bot user to see and nothing left by an accidental
open. One request means one creation entry, with the date, priority and tags
inside it rather than as edits after it.

The earlier argument against this was that a panel of buffered controls is
"a form with the Save button hidden". The answer is to not hide it: the
commit is a labelled button in a pinned footer, and there is no other commit.
The one thing a buffered draft adds is a way to lose it, so closing a draft
that holds anything asks **Discard this task?** first. That covers every
way the panel can close, Back included, because the panel is addressed by the
URL and the question is asked when the URL would change.

Projects and tags keep one-field capture: a name is all they have at creation.
A subtask added from its parent's Subtasks tab also stays one field, because
the reader is working through a list there, not describing one task.
