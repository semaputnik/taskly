import { describe, expect, test } from "bun:test"

import {
  describeStatusFilter,
  isOpenFilter,
  markName,
  markTone,
  OPEN_STATUSES,
  STATUS_LABELS,
  STATUSES,
} from "./statuses"

describe("the six statuses", () => {
  test("are listed in the order the interface uses everywhere", () => {
    expect(STATUSES.map((status) => STATUS_LABELS[status])).toEqual([
      "Backlog",
      "To do",
      "In progress",
      "Review",
      "Waiting",
      "Done",
    ])
  })

  test("are open whenever they are not done", () => {
    expect(OPEN_STATUSES).toEqual([
      "backlog",
      "todo",
      "in_progress",
      "review",
      "waiting",
    ])
  })
})

describe("the open baseline of the task list", () => {
  test("is every open status, in any order", () => {
    expect(isOpenFilter([...OPEN_STATUSES].reverse())).toBe(true)
    expect(describeStatusFilter(OPEN_STATUSES)).toBeUndefined()
  })

  test("is not the three open statuses there used to be", () => {
    const old = ["todo", "in_progress", "waiting"] as const
    expect(isOpenFilter(old)).toBe(false)
    expect(describeStatusFilter(old)).toBe("To do, In progress, Waiting")
  })

  test("is not any one open status", () => {
    expect(describeStatusFilter(["review"])).toBe("Review")
    expect(describeStatusFilter(["backlog"])).toBe("Backlog")
  })
})

describe("a status mark", () => {
  test("takes the priority's colour while the task is open", () => {
    expect(markTone("backlog", "P1")).toBe("p1")
    expect(markTone("review", "P2")).toBe("p2")
    expect(markTone("waiting", "P3")).toBe("p3")
  })

  test("stays ink for P4 and no priority", () => {
    expect(markTone("todo", "P4")).toBeNull()
    expect(markTone("in_progress", null)).toBeNull()
    expect(markTone("in_progress", undefined)).toBeNull()
  })

  test("is done's green whatever the priority was", () => {
    expect(markTone("done", "P1")).toBe("done")
    expect(markTone("done", null)).toBe("done")
  })

  test("names its status, and its priority when one is set", () => {
    expect(markName("review")).toBe("Review")
    expect(markName("review", "P1")).toBe("Review, priority P1")
    expect(markName("todo", "P4")).toBe("To do, priority P4")
    expect(markName("todo", null)).toBe("To do")
  })
})
