import { describe, expect, test } from "bun:test"

import { describeDue, metaLine, subtaskProgress } from "./compact"
import { priorityTone } from "./priorityTone"

// A Friday, so "this week" and "next week" are both a few days away.
const TODAY = "2026-09-18"

describe("a due date in a compact row", () => {
  test("names today and tomorrow in words", () => {
    expect(describeDue("2026-09-18", TODAY)).toEqual({
      text: "Today",
      tone: "today",
    })
    expect(describeDue("2026-09-19", TODAY)).toEqual({
      text: "Tomorrow",
      tone: "soon",
    })
  })

  test("says how late a missed day is, in the alert tone", () => {
    expect(describeDue("2026-09-17", TODAY)).toEqual({
      text: "Yesterday",
      tone: "late",
    })
    expect(describeDue("2026-09-15", TODAY)).toEqual({
      text: "3 days late",
      tone: "late",
    })
  })

  test("names the weekday within the coming week", () => {
    expect(describeDue("2026-09-23", TODAY).tone).toBe("soon")
    expect(describeDue("2026-09-23", TODAY).text).toBe(
      new Date(2026, 8, 23).toLocaleDateString(undefined, { weekday: "long" }),
    )
  })

  test("writes a day further out as a date", () => {
    expect(describeDue("2026-10-30", TODAY)).toEqual({
      text: new Date(2026, 9, 30).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
      }),
      tone: "later",
    })
  })

  test("adds the year only when it is not this year", () => {
    expect(describeDue("2027-01-04", TODAY).text).toBe(
      new Date(2027, 0, 4).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      }),
    )
  })
})

describe("a due date on a done task", () => {
  // A deadline that has been met is a fact, not a warning: no alert tone, and
  // no relative wording whose number would grow for as long as the task sits
  // in a list.
  test("reads as a plain date however long ago it passed", () => {
    expect(describeDue("2026-09-15", TODAY, { done: true })).toEqual({
      text: new Date(2026, 8, 15).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
      }),
      tone: "later",
    })
    expect(describeDue("2025-02-03", TODAY, { done: true })).toEqual({
      text: new Date(2025, 1, 3).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      }),
      tone: "later",
    })
  })

  test("never says Today, Tomorrow, Yesterday or a weekday", () => {
    for (const day of [
      "2026-09-17",
      "2026-09-18",
      "2026-09-19",
      "2026-09-23",
    ]) {
      const { text, tone } = describeDue(day, TODAY, { done: true })
      expect(text).not.toMatch(/Today|Tomorrow|Yesterday|late/)
      expect(tone).toBe("later")
    }
  })
})

describe("subtask progress", () => {
  test("is done over total, and absent for a task with no subtasks", () => {
    expect(subtaskProgress({ subtask_count: 3, subtasks_done: 1 })).toBe("1/3")
    expect(subtaskProgress({ subtask_count: 0, subtasks_done: 0 })).toBeNull()
    expect(subtaskProgress({})).toBeNull()
  })
})

describe("priority tone", () => {
  test("gives P1–P3 a hue and leaves P4 and no priority in ink", () => {
    expect(priorityTone("P1")).toBe("p1")
    expect(priorityTone("P2")).toBe("p2")
    expect(priorityTone("P3")).toBe("p3")
    expect(priorityTone("P4")).toBeNull()
    expect(priorityTone(null)).toBeNull()
    expect(priorityTone(undefined)).toBeNull()
  })
})

describe("the meta line", () => {
  const bare = {
    subtask_count: 0,
    subtasks_done: 0,
    due_date: null,
    recurrence: null,
    tags: [],
    status: "todo" as const,
  }

  const kinds = (line: ReturnType<typeof metaLine>) =>
    line.facts.map((fact) => fact.kind)

  test("says subtasks, due day, recurrence and tags in that order, then the project", () => {
    const line = metaLine(
      {
        ...bare,
        subtask_count: 5,
        subtasks_done: 2,
        due_date: "2026-09-18",
        recurrence: { frequency: "weekly" },
        tags: ["copy", "web"],
      },
      { today: TODAY, projectName: "Website relaunch" },
    )
    expect(kinds(line)).toEqual(["subtasks", "due", "recurrence", "tag", "tag"])
    expect(line.facts.map((fact) => fact.text)).toEqual([
      "2/5",
      "Today",
      "Weekly",
      "copy",
      "web",
    ])
    expect(line.project).toBe("Website relaunch")
  })

  test("carries the due day's tone, so a late day can be red and today ink", () => {
    const late = metaLine({ ...bare, due_date: "2026-09-16" }, { today: TODAY })
    expect(late.facts).toEqual([
      { kind: "due", text: "2 days late", tone: "late" },
    ])
    const today = metaLine(
      { ...bare, due_date: "2026-09-18" },
      { today: TODAY },
    )
    expect(today.facts).toEqual([{ kind: "due", text: "Today", tone: "today" }])
  })

  test("reads a done task's due day plainly", () => {
    const line = metaLine(
      { ...bare, status: "done", due_date: "2026-09-16" },
      { today: TODAY },
    )
    expect(line.facts[0]).toMatchObject({ kind: "due", tone: "later" })
  })

  test("leaves out what the task does not have", () => {
    const tagged = metaLine(
      { ...bare, tags: ["home"] },
      { today: TODAY, projectName: "Home" },
    )
    expect(kinds(tagged)).toEqual(["tag"])
    expect(tagged.project).toBe("Home")
    const split = metaLine({ ...bare, subtask_count: 2 }, { today: TODAY })
    expect(kinds(split)).toEqual(["subtasks"])
    expect(split.project).toBeNull()
  })

  test("is empty for a task with nothing to say, so its line is one line tall", () => {
    const empty = { facts: [], project: null }
    expect(metaLine(bare, { today: TODAY })).toEqual(empty)
    expect(metaLine({}, { today: TODAY })).toEqual(empty)
    expect(metaLine(bare, { today: TODAY, projectName: "" })).toEqual(empty)
  })

  describe("the assignee (FR-06.13)", () => {
    const release = { id: "b1", name: "release-bot", deleted: false }
    const assignee = (line: ReturnType<typeof metaLine>) =>
      line.facts.find((fact) => fact.kind === "assignee")

    test('says "you" for a task assigned to the owner', () => {
      const line = metaLine(
        { ...bare, assignee_id: "u1", assignee_bot_user: null },
        { today: TODAY },
      )
      expect(assignee(line)).toEqual({
        kind: "assignee",
        text: "you",
        handover: false,
      })
    })

    test("says the bot user's name for a task assigned to one", () => {
      // The payload carries a bot user's id as the assignee id too.
      const line = metaLine(
        { ...bare, assignee_id: "b1", assignee_bot_user: release },
        { today: TODAY },
      )
      expect(assignee(line)).toEqual({
        kind: "assignee",
        text: "release-bot",
        handover: false,
      })
    })

    test("still names a deleted bot user", () => {
      const line = metaLine(
        {
          ...bare,
          assignee_id: "b1",
          assignee_bot_user: { ...release, deleted: true },
        },
        { today: TODAY },
      )
      expect(assignee(line)?.text).toBe("release-bot")
    })

    test('says the bot user, an arrow and "you" for a task handed over in Review', () => {
      const line = metaLine(
        {
          ...bare,
          status: "review",
          assignee_id: "u1",
          assignee_bot_user: null,
          handover: { bot_user: release, at: "2026-09-17T10:00:00Z" },
        },
        { today: TODAY },
      )
      expect(assignee(line)).toEqual({
        kind: "assignee",
        text: "release-bot → you",
        handover: true,
        name: "release-bot",
      })
    })

    test("names the bot user it was handed over by even once deleted", () => {
      const line = metaLine(
        {
          ...bare,
          status: "review",
          assignee_id: "u1",
          assignee_bot_user: null,
          handover: {
            bot_user: { ...release, deleted: true },
            at: "2026-09-17T10:00:00Z",
          },
        },
        { today: TODAY },
      )
      expect(assignee(line)?.text).toBe("release-bot → you")
    })

    test('is plain "you" in Review when nobody handed it over', () => {
      const line = metaLine(
        {
          ...bare,
          status: "review",
          assignee_id: "u1",
          assignee_bot_user: null,
          handover: null,
        },
        { today: TODAY },
      )
      expect(assignee(line)).toMatchObject({ text: "you", handover: false })
    })

    test("names nobody when the task is unassigned", () => {
      const line = metaLine(
        { ...bare, assignee_id: null, assignee_bot_user: null },
        { today: TODAY },
      )
      expect(assignee(line)).toBeUndefined()
      expect(metaLine(bare, { today: TODAY }).facts).toEqual([])
    })

    test("comes after the due day and tags, before the project", () => {
      const line = metaLine(
        {
          ...bare,
          due_date: "2026-09-18",
          tags: ["web"],
          assignee_id: "u1",
          assignee_bot_user: null,
        },
        { today: TODAY, projectName: "Website relaunch" },
      )
      expect(kinds(line)).toEqual(["due", "tag", "assignee"])
      expect(line.project).toBe("Website relaunch")
    })
  })
})
