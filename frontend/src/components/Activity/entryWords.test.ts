import { describe, expect, test } from "bun:test"

import type { ActivityAction, ActivityEntryPublic } from "@/client"
import { type EntryWords, entryWords } from "./entryWords"

/**
 * A row for every action, typed over `ActivityAction` itself rather than a
 * hand-kept count: a 25th action with no row here yet is a type error on
 * this object, in the same edit that adds the case `entryWords` demands for
 * it, not something a reviewer has to notice is missing.
 */
const COVERED: Record<ActivityAction, true> = {
  task_created: true,
  task_changed: true,
  tasks_bulk_changed: true,
  task_completed: true,
  task_reopened: true,
  task_status_changed: true,
  task_deleted: true,
  task_restored: true,
  task_moved: true,
  task_assigned: true,
  task_unassigned: true,
  project_created: true,
  project_changed: true,
  project_deleted: true,
  project_restored: true,
  comment_added: true,
  comment_edited: true,
  comment_deleted: true,
  attachment_added: true,
  attachment_deleted: true,
  tag_created: true,
  tag_renamed: true,
  tag_deleted: true,
  tag_merged: true,
}

/**
 * `details.kind` as the real API would set it (`app.activity_details.
 * public_kind`): an action's own spelling, except `task_deleted`/
 * `task_restored`, split into `..._batch` by the one thing a batch's own
 * shape never carries — here, by whether `task_count` is the field this
 * fixture set, the same test the pre-union code used to run on `details`
 * by hand.
 */
function kindOf(
  action: ActivityEntryPublic["action"],
  details: Record<string, unknown>,
) {
  if (
    (action === "task_deleted" || action === "task_restored") &&
    "task_count" in details
  ) {
    return `${action}_batch`
  }
  return action
}

function entry(
  action: ActivityEntryPublic["action"],
  details: Record<string, unknown> = {},
  extra: Partial<ActivityEntryPublic> = {},
): ActivityEntryPublic {
  return {
    id: action,
    action,
    entity_type: "task",
    entity_id: "entity",
    details: {
      ...details,
      kind: kindOf(action, details),
    } as ActivityEntryPublic["details"],
    created_at: null,
    entity_exists: true,
    ...extra,
  }
}

interface Case {
  name: string
  entry: ActivityEntryPublic
  currentUserId?: string
  /** What the log page says: it names every one of the 24 actions. */
  names: EntryWords
  /** What the task panel says, or `null` for an action it does not speak. */
  implicit: EntryWords | null
}

const cases: Case[] = [
  {
    name: "task_created, in a project",
    entry: entry("task_created", {
      task: { project: { id: "p1", name: "Family Budget" } },
    }),
    names: { verb: "Created", subject: true, after: " in Family Budget" },
    implicit: {
      verb: "created this in Family Budget",
      subject: false,
      after: "",
    },
  },
  {
    name: "task_created, no project",
    entry: entry("task_created", { task: { project: null } }),
    names: { verb: "Created", subject: true, after: "" },
    implicit: { verb: "created this", subject: false, after: "" },
  },
  {
    // The two voices disagree here: `names-its-subject` only knows the
    // project reference is there and falls back to "a project that no
    // longer exists" because it is unnamed, while `subject-implicit` checks
    // the name directly and says nothing about a project at all. Existing
    // behaviour, preserved rather than reconciled.
    name: "task_created, project reference with no name",
    entry: entry("task_created", {
      task: { project: { id: "p1", name: null } },
    }),
    names: {
      verb: "Created",
      subject: true,
      after: " in a project that no longer exists",
    },
    implicit: { verb: "created this", subject: false, after: "" },
  },
  {
    name: "task_changed, several fields",
    entry: entry("task_changed", {
      changes: {
        due_date: { from: "2026-10-01", to: null },
        priority: { from: null, to: "P1" },
        tags: { from: ["a"], to: ["a", "b"] },
      },
    }),
    names: {
      verb: "Changed the due date, priority, tags of",
      subject: true,
      after: "",
    },
    implicit: {
      verb: "cleared the due date, set the priority to P1 and tagged it b",
      subject: false,
      after: "",
    },
  },
  {
    // A field `subject-implicit` does not recognise says nothing in that
    // voice, even though `names-its-subject` still lists its raw key.
    name: "task_changed, an unrecognised field",
    entry: entry("task_changed", {
      changes: { custom_field: { from: 1, to: 2 } },
    }),
    names: { verb: "Changed the custom_field of", subject: true, after: "" },
    implicit: null,
  },
  {
    name: "task_completed",
    entry: entry("task_completed"),
    names: { verb: "Completed", subject: true, after: "" },
    implicit: { verb: "completed it", subject: false, after: "" },
  },
  {
    name: "task_reopened",
    entry: entry("task_reopened"),
    names: { verb: "Reopened", subject: true, after: "" },
    implicit: { verb: "reopened it", subject: false, after: "" },
  },
  {
    name: "task_status_changed, to a known status",
    entry: entry("task_status_changed", { to: "in_progress" }),
    names: { verb: "Moved", subject: true, after: " to In progress" },
    implicit: { verb: "moved it to In progress", subject: false, after: "" },
  },
  {
    name: "task_status_changed, no status on the entry",
    entry: entry("task_status_changed", {}),
    names: { verb: "Moved", subject: true, after: " to another status" },
    implicit: { verb: "moved it", subject: false, after: "" },
  },
  {
    name: "task_deleted, with subtasks",
    entry: entry("task_deleted", { subtask_count: 2 }),
    names: { verb: "Deleted", subject: true, after: " and 2 subtasks" },
    implicit: { verb: "deleted it", subject: false, after: "" },
  },
  {
    // A batch names no single task, so `names-its-subject` speaks a count
    // instead of a subject; `subject-implicit` ignores the batch shape
    // entirely, because the task panel is always about one task.
    name: "task_deleted, a batch",
    entry: entry("task_deleted", { task_count: 3 }),
    names: { verb: "Deleted 3 tasks", subject: false, after: "" },
    implicit: { verb: "deleted it", subject: false, after: "" },
  },
  {
    name: "task_restored, with one subtask",
    entry: entry("task_restored", { subtask_count: 1 }),
    names: { verb: "Restored", subject: true, after: " and 1 subtask" },
    implicit: { verb: "restored it", subject: false, after: "" },
  },
  {
    name: "task_moved, between two named projects",
    entry: entry("task_moved", {
      from_project: { id: "a", name: "A" },
      to_project: { id: "b", name: "B" },
    }),
    names: { verb: "Moved", subject: true, after: " from A to B" },
    // Only the destination: the panel is already open on the task's own
    // history, read in order, so it already knows where it came from.
    implicit: { verb: "moved it to B", subject: false, after: "" },
  },
  {
    name: "task_moved, destination gone",
    entry: entry("task_moved", {
      from_project: { id: "a", name: "A" },
      to_project: { id: "b", name: null },
    }),
    names: {
      verb: "Moved",
      subject: true,
      after: " from A to a project that no longer exists",
    },
    implicit: {
      verb: "moved it to another project",
      subject: false,
      after: "",
    },
  },
  {
    name: "task_assigned, to a bot user",
    entry: entry("task_assigned", {
      assignee: { type: "bot_user", id: "bot1", name: "release-bot" },
    }),
    names: {
      verb: "Assigned",
      subject: true,
      after: " to the bot user release-bot",
    },
    implicit: { verb: "assigned it to release-bot", subject: false, after: "" },
  },
  {
    name: "task_assigned, a human to themselves",
    entry: entry(
      "task_assigned",
      { assignee: { type: "user", id: "me" } },
      { actor_id: "me" },
    ),
    currentUserId: "me",
    names: { verb: "Assigned", subject: true, after: " to you" },
    implicit: { verb: "assigned it to yourself", subject: false, after: "" },
  },
  {
    name: "task_assigned, viewed by someone other than the assignee",
    entry: entry("task_assigned", { assignee: { type: "user", id: "me" } }),
    currentUserId: "someone-else",
    names: { verb: "Assigned", subject: true, after: " to someone" },
    implicit: { verb: "assigned it to yourself", subject: false, after: "" },
  },
  {
    name: "task_assigned, a bot user assigning it to the owner",
    entry: entry(
      "task_assigned",
      { assignee: { type: "user", id: "me" } },
      { actor_id: null, actor_bot_user_id: "bot1" },
    ),
    currentUserId: "me",
    names: { verb: "Assigned", subject: true, after: " to you" },
    implicit: { verb: "assigned it to you", subject: false, after: "" },
  },
  {
    name: "task_unassigned, no previous assignee recorded",
    entry: entry("task_unassigned"),
    names: { verb: "Removed the assignee from", subject: true, after: "" },
    implicit: { verb: "removed the assignee", subject: false, after: "" },
  },
  {
    // Another divergence kept as-is: `names-its-subject` names the bot user
    // that was removed; `subject-implicit` says only "removed the
    // assignee" regardless of who it was.
    name: "task_unassigned, a bot user was the previous assignee",
    entry: entry("task_unassigned", {
      previous_assignee: { type: "bot_user", id: "bot1", name: "release-bot" },
    }),
    names: {
      verb: "Removed the bot user release-bot from",
      subject: true,
      after: "",
    },
    implicit: { verb: "removed the assignee", subject: false, after: "" },
  },
  {
    name: "tasks_bulk_changed, with other changes",
    entry: entry("tasks_bulk_changed", {
      task_count: 3,
      changes: { status: "done", priority: "P2" },
    }),
    names: {
      verb: "Changed 3 tasks: completed, priority P2",
      subject: false,
      after: "",
    },
    implicit: {
      verb: "changed it along with 2 other tasks",
      subject: false,
      after: "",
    },
  },
  {
    name: "tasks_bulk_changed, no other tasks named",
    entry: entry("tasks_bulk_changed", { task_count: 1, changes: {} }),
    names: { verb: "Changed 1 task", subject: false, after: "" },
    implicit: { verb: "changed it", subject: false, after: "" },
  },
  {
    name: "attachment_added",
    entry: entry("attachment_added", { filename: "notes.pdf" }),
    names: { verb: "Attached “notes.pdf” to", subject: true, after: "" },
    implicit: { verb: "attached “notes.pdf”", subject: false, after: "" },
  },
  {
    name: "attachment_deleted",
    entry: entry("attachment_deleted", { filename: "notes.pdf" }),
    names: { verb: "Removed “notes.pdf” from", subject: true, after: "" },
    implicit: { verb: "removed “notes.pdf”", subject: false, after: "" },
  },
  {
    name: "comment_added",
    entry: entry("comment_added"),
    names: { verb: "Commented on", subject: true, after: "" },
    implicit: null,
  },
  {
    name: "comment_edited",
    entry: entry("comment_edited"),
    names: { verb: "Edited a comment on", subject: true, after: "" },
    implicit: null,
  },
  {
    name: "comment_deleted",
    entry: entry("comment_deleted"),
    names: { verb: "Deleted a comment on", subject: true, after: "" },
    implicit: null,
  },
  {
    name: "project_created",
    entry: entry("project_created"),
    names: { verb: "Created the project", subject: true, after: "" },
    implicit: null,
  },
  {
    name: "project_changed",
    entry: entry("project_changed", { changes: { name: "x", color: "blue" } }),
    names: {
      verb: "Changed the name, color of the project",
      subject: true,
      after: "",
    },
    implicit: null,
  },
  {
    name: "project_deleted, with tasks",
    entry: entry("project_deleted", { task_count: 5 }),
    names: {
      verb: "Deleted the project",
      subject: true,
      after: " and 5 tasks",
    },
    implicit: null,
  },
  {
    name: "project_deleted, empty",
    entry: entry("project_deleted", { task_count: 0 }),
    names: { verb: "Deleted the project", subject: true, after: "" },
    implicit: null,
  },
  {
    name: "project_restored, with one task",
    entry: entry("project_restored", { task_count: 1 }),
    names: {
      verb: "Restored the project",
      subject: true,
      after: " and 1 task",
    },
    implicit: null,
  },
  {
    name: "tag_created",
    entry: entry("tag_created"),
    names: { verb: "Created the tag", subject: true, after: "" },
    implicit: null,
  },
  {
    name: "tag_renamed",
    entry: entry("tag_renamed", { changes: { name: { from: "Old" } } }),
    names: { verb: "Renamed the tag “Old” to", subject: true, after: "" },
    implicit: null,
  },
  {
    name: "tag_merged, moving tasks onto it",
    entry: entry("tag_merged", { sources: ["Urgent", "ASAP"], task_count: 4 }),
    names: {
      verb: "Merged “Urgent”, “ASAP” into",
      subject: true,
      after: ", moving 4 tasks onto it",
    },
    implicit: null,
  },
  {
    name: "tag_merged, no tasks carried either source",
    entry: entry("tag_merged", { sources: ["Urgent"], task_count: 0 }),
    names: { verb: "Merged “Urgent” into", subject: true, after: "" },
    implicit: null,
  },
  {
    name: "tag_deleted, taking it off some tasks",
    entry: entry("tag_deleted", { task_count: 2 }),
    names: {
      verb: "Deleted the tag",
      subject: true,
      after: ", taking it off 2 tasks",
    },
    implicit: null,
  },
]

describe("entryWords", () => {
  test.each(cases)("$name — names-its-subject", (c) => {
    expect(entryWords(c.entry, "names-its-subject", c.currentUserId)).toEqual(
      c.names,
    )
  })

  test.each(cases)("$name — subject-implicit", (c) => {
    expect(entryWords(c.entry, "subject-implicit")).toEqual(c.implicit)
  })

  test("every action in COVERED has at least one case in this table", () => {
    const actions = new Set(cases.map((c) => c.entry.action))
    for (const action of Object.keys(COVERED) as ActivityAction[]) {
      expect(actions.has(action)).toBe(true)
    }
  })
})
