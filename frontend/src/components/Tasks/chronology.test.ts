import { describe, expect, test } from "bun:test"

import type { ActivityEntryPublic, CommentPublic } from "@/client"
import { dateInWords } from "@/lib/dates"
import { chronology } from "./chronology"
import { describeTaskEvent } from "./taskEvents"

function entry(
  action: ActivityEntryPublic["action"],
  at: string,
  details: Record<string, unknown> = {},
  extra: Partial<ActivityEntryPublic> = {},
): ActivityEntryPublic {
  return {
    id: `${action}-${at}`,
    action,
    entity_type: "task",
    entity_id: "task",
    details,
    created_at: at,
    entity_exists: true,
    actor_id: "me",
    ...extra,
  }
}

function comment(id: string, at: string): CommentPublic {
  return {
    id,
    body: id,
    created_at: at,
    task_id: "task",
  } as CommentPublic
}

describe("what an entry says about its task", () => {
  test("a move between statuses names where it went", () => {
    expect(
      describeTaskEvent(
        entry("task_status_changed", "2026-10-05T09:00:00Z", {
          from: "todo",
          to: "in_progress",
        }),
      ),
    ).toBe("moved it to In progress")
  })

  test("several changed fields are one line", () => {
    expect(
      describeTaskEvent(
        entry("task_changed", "2026-10-05T09:00:00Z", {
          changes: {
            priority: { from: null, to: "P1" },
            due_date: { from: "2026-10-01", to: null },
            tags: { from: ["a"], to: ["a", "b"] },
          },
        }),
      ),
    ).toBe("cleared the due date, set the priority to P1 and tagged it b")
  })

  test("assigning to oneself reads differently from a bot user doing it", () => {
    const assigned = { assignee: { type: "user", id: "me" } }
    expect(
      describeTaskEvent(
        entry("task_assigned", "2026-10-05T09:00:00Z", assigned),
      ),
    ).toBe("assigned it to yourself")
    expect(
      describeTaskEvent(
        entry("task_assigned", "2026-10-05T09:00:00Z", assigned, {
          actor_id: null,
          actor_bot_user_id: "bot",
        }),
      ),
    ).toBe("assigned it to you")
  })

  test("a comment has no line of its own: it is shown as the comment", () => {
    for (const action of [
      "comment_added",
      "comment_edited",
      "comment_deleted",
    ] as const) {
      expect(
        describeTaskEvent(entry(action, "2026-10-05T09:00:00Z")),
      ).toBeNull()
    }
  })
})

describe("the chronology", () => {
  const now = new Date("2026-10-05T12:00:00")

  test("reads oldest first, events and comments interleaved", () => {
    const days = chronology(
      [
        entry("task_status_changed", "2026-10-05T10:00:00", { to: "done" }),
        entry("comment_added", "2026-10-05T09:30:00"),
        entry("task_created", "2026-10-05T09:00:00", { task: {} }),
      ],
      [
        comment("a", "2026-10-05T09:30:00"),
        comment("b", "2026-10-05T10:30:00"),
      ],
      now,
    )

    expect(days).toHaveLength(1)
    expect(days[0].moments.map((m) => m.id)).toEqual([
      "task_created-2026-10-05T09:00:00",
      "a",
      "task_status_changed-2026-10-05T10:00:00",
      "b",
    ])
  })

  test("starts a new day under its own heading", () => {
    const days = chronology(
      [
        entry("task_completed", "2026-10-05T08:00:00"),
        entry("task_created", "2026-10-04T08:00:00", { task: {} }),
        entry("task_reopened", "2026-09-01T08:00:00"),
      ].reverse(),
      [],
      now,
    )

    expect(days.map((d) => d.heading)).toEqual([
      dateInWords(new Date("2026-09-01T08:00:00"), now),
      "Yesterday",
      "Today",
    ])
  })

  test("is empty when nothing is known", () => {
    expect(chronology([], [], now)).toEqual([])
  })
})
