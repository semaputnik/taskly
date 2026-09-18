import { describe, expect, test } from "bun:test"

import { describeDue, subtaskProgress } from "./compact"
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
