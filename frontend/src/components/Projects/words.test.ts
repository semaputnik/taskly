import { describe, expect, test } from "bun:test"

import {
  botsInWords,
  counts,
  deletionReach,
  metaFacts,
  tasksInWords,
} from "./words"

const project = (patch = {}) => ({
  name: "Inbox",
  open_count: 0,
  overdue_count: 0,
  backlog_count: 0,
  review_count: 0,
  done_count: 0,
  ...patch,
})

describe("counts", () => {
  test("names where the overdue tasks are", () => {
    const sentence = counts([
      project({ open_count: 6, overdue_count: 1 }),
      project({ name: "Website", open_count: 9, overdue_count: 1 }),
      project({ name: "Home", open_count: 3 }),
    ])
    expect(sentence.lead).toBe("3 projects, 18 open tasks.")
    expect(sentence.rest).toBe("2 are overdue, in Inbox and Website.")
  })

  test("says when nothing is late, and counts one in the singular", () => {
    expect(counts([project({ open_count: 1 })])).toEqual({
      lead: "1 project, 1 open task.",
      rest: "Nothing is overdue.",
    })
    expect(counts([project({ overdue_count: 1 })]).rest).toBe(
      "1 is overdue, in Inbox.",
    )
  })
})

describe("a line's facts", () => {
  test("late first, then Backlog, Review and the bot users", () => {
    expect(
      metaFacts(
        project({ overdue_count: 1, backlog_count: 3, review_count: 1 }),
        ["inbox-triage"],
      ),
    ).toEqual([
      { text: "1 overdue", late: true },
      { text: "3 in Backlog" },
      { text: "1 in Review" },
      { text: "inbox-triage works here" },
    ])
  })

  test("a project with nothing to say has no facts", () => {
    expect(metaFacts(project(), [])).toEqual([])
  })

  test("bot users agree with their verb", () => {
    expect(botsInWords(["a", "b"])).toBe("a, b work here")
    expect(botsInWords([])).toBeNull()
  })
})

test("the column says what the project holds", () => {
  expect(
    tasksInWords(project({ open_count: 9, overdue_count: 1, done_count: 6 })),
  ).toBe("9 open · 1 overdue · 6 done")
  expect(tasksInWords(project({ open_count: 2 }))).toBe("2 open · 0 done")
})

test("deleting names how many tasks go", () => {
  expect(deletionReach(0)).toBe("It holds no tasks.")
  expect(deletionReach(1)).toBe("Its task goes with it.")
  expect(deletionReach(4)).toBe("Its 4 tasks go with it.")
})
