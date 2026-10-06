import { describe, expect, test } from "bun:test"

import {
  counts,
  createdBy,
  deletionReach,
  groupCounts,
  nameList,
  suggestedSurvivor,
  tasksInWords,
} from "./words"

const tag = (name: string, task_count = 0, archived_task_count = 0) => ({
  id: name,
  name,
  task_count,
  archived_task_count,
})

describe("counts", () => {
  test("says how many tags and how many look alike", () => {
    expect(counts(7, 2)).toEqual({
      lead: "7 tags.",
      rest: "2 look alike. Tags are created by typing them onto a task, too.",
    })
    expect(counts(1, 0).lead).toBe("1 tag.")
    expect(counts(3, 0).rest).toStartWith("None look alike.")
  })

  test("says what to do with no tags", () => {
    expect(counts(0, 0).lead).toBe("No tags yet.")
  })
})

describe("createdBy", () => {
  test("names the bot user, or the reader", () => {
    expect(createdBy({})).toBe("created by you")
    expect(
      createdBy({
        created_by_bot_user: { id: "b", name: "inbox-triage", deleted: false },
      }),
    ).toBe("created by inbox-triage")
    expect(
      createdBy({
        created_by_bot_user: { id: "b", name: "old", deleted: true },
      }),
    ).toBe("created by old (deleted)")
  })
})

describe("a look-alike group", () => {
  test("lists names and counts in the same order", () => {
    expect(nameList(["urgent", "Urgent"])).toBe("urgent and Urgent")
    expect(nameList(["a", "b", "c"])).toBe("a, b and c")
    expect(groupCounts([tag("urgent", 3), tag("Urgent", 1)])).toBe(
      "3 and 1 tasks",
    )
  })

  test("suggests the most used spelling, the first on a tie", () => {
    expect(suggestedSurvivor([tag("a", 1), tag("b", 3)]).name).toBe("b")
    expect(suggestedSurvivor([tag("a", 2), tag("b", 2)]).name).toBe("a")
    // Archived tasks move too, so they weigh in.
    expect(suggestedSurvivor([tag("a", 1), tag("b", 0, 4)]).name).toBe("b")
  })
})

describe("the column's words", () => {
  test("the Tasks row says what the open count leaves out", () => {
    expect(tasksInWords(tag("x", 4, 2))).toBe("4 open · 2 in archived projects")
    expect(tasksInWords(tag("x", 1, 1))).toBe(
      "1 open · 1 in an archived project",
    )
    expect(tasksInWords(tag("x", 0))).toBe("0 open")
  })

  test("deleting names every task it reaches", () => {
    expect(deletionReach(tag("x", 3, 1))).toBe(
      "Deleting takes it off 4 tasks, 1 of them in an archived project. This can't be undone.",
    )
    expect(deletionReach(tag("x"))).toBe(
      "No task carries it. Deleting can't be undone.",
    )
  })
})
