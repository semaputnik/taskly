# Recurring tasks spawn a new task per occurrence

Recurring tasks need to produce successive occurrences without breaking the
two-state completion model (FR-01.4: a task is either completed or not, with
no other workflow status). We considered resetting a single persistent task
back to not-completed with a new due date, but that would either violate
FR-01.4 (by needing a "completed, but recurs" pseudo-state) or destroy the
completion history each time it resets.

We decided that completing a recurring task instead creates a new task as the
next occurrence, copying its fields and subtask tree. The completed task stays
completed permanently, preserving history in the activity log. At most one
occurrence of a given recurring task is open at a time — the next one is only
created once the current one is completed, even if its due date has passed.
