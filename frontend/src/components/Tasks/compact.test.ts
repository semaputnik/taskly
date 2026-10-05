import { describe, expect, test } from "bun:test"

import { describeDue, metaLine, subtaskProgress } from "./compact"
import { priorityTone } from "./priority"

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

  test("says subtasks, due day, recurrence, tags, then the project, in that order", () => {
    const items = metaLine(
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
    expect(items.map((item) => item.kind)).toEqual([
      "subtasks",
      "due",
      "recurrence",
      "tag",
      "tag",
      "project",
    ])
    expect(items.map((item) => item.text)).toEqual([
      "2/5",
      "Today",
      "Weekly",
      "copy",
      "web",
      "Website relaunch",
    ])
  })

  test("carries the due day's tone, so a late day can be red and today ink", () => {
    const [late] = metaLine(
      { ...bare, due_date: "2026-09-16" },
      { today: TODAY },
    )
    expect(late).toEqual({ kind: "due", text: "2 days late", tone: "late" })
    const [today] = metaLine(
      { ...bare, due_date: "2026-09-18" },
      { today: TODAY },
    )
    expect(today).toEqual({ kind: "due", text: "Today", tone: "today" })
  })

  test("reads a done task's due day plainly", () => {
    const [due] = metaLine(
      { ...bare, status: "done", due_date: "2026-09-16" },
      { today: TODAY },
    )
    expect(due).toMatchObject({ kind: "due", tone: "later" })
  })

  test("leaves out what the task does not have", () => {
    expect(
      metaLine(
        { ...bare, tags: ["home"] },
        { today: TODAY, projectName: "Home" },
      ).map((item) => item.kind),
    ).toEqual(["tag", "project"])
    expect(
      metaLine({ ...bare, subtask_count: 2 }, { today: TODAY }).map(
        (item) => item.kind,
      ),
    ).toEqual(["subtasks"])
  })

  test("is empty for a task with nothing to say, so its line is one line tall", () => {
    expect(metaLine(bare, { today: TODAY })).toEqual([])
    expect(metaLine({}, { today: TODAY })).toEqual([])
    expect(metaLine(bare, { today: TODAY, projectName: "" })).toEqual([])
  })
})
