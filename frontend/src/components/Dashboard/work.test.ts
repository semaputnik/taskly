import { describe, expect, test } from "bun:test"

import { handoverLine, MY_WORK_GROUPS, myWorkSearch } from "./work"

describe("My work's groups", () => {
  test("run in the order work moves, Waiting last, Backlog never", () => {
    expect(MY_WORK_GROUPS.map((group) => group.label)).toEqual([
      "In progress",
      "Review",
      "To do",
      "Waiting",
    ])
  })

  test("each opens the list narrowed to its status and to the reader", () => {
    expect(myWorkSearch("review")).toEqual({
      status: ["review"],
      assignee: "me",
      sort: "priority",
    })
  })
})

describe("the hand-over line under a task in Review", () => {
  const now = new Date(2026, 9, 5, 15, 0)
  const at = (date: Date) => date.toISOString()

  test("names the bot user and the time of a hand-over made today", () => {
    expect(
      handoverLine(
        {
          bot_user: { id: "b", name: "research-agent", deleted: false },
          at: at(new Date(2026, 9, 5, 13, 46)),
        },
        now,
        "en-GB",
      ),
    ).toEqual({
      who: "research-agent",
      rest: "finished this at 13:46 and handed it to you",
    })
  })

  test("says yesterday, then the weekday, then the date, as it gets older", () => {
    const line = (date: Date) =>
      handoverLine(
        { bot_user: { id: "b", name: "a", deleted: false }, at: at(date) },
        now,
        "en-GB",
      ).rest
    expect(line(new Date(2026, 9, 4, 9, 5))).toBe(
      "finished this yesterday at 09:05 and handed it to you",
    )
    expect(line(new Date(2026, 9, 1, 9, 5))).toBe(
      "finished this on Thursday and handed it to you",
    )
    expect(line(new Date(2026, 7, 20, 9, 5))).toBe(
      "finished this on 20 Aug and handed it to you",
    )
  })

  test("still names a deleted bot user, and says it is gone", () => {
    expect(
      handoverLine(
        {
          bot_user: { id: "b", name: "research-agent", deleted: true },
          at: at(new Date(2026, 9, 5, 13, 46)),
        },
        now,
        "en-GB",
      ).who,
    ).toBe("research-agent (deleted)")
  })
})
