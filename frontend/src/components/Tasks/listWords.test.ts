import { describe, expect, test } from "bun:test"

import { chooseOrder, counts, orderChoice, timeLabel } from "./listWords"

describe("the counts sentence", () => {
  test("leads with what is open and names what else is true of it", () => {
    expect(counts({ open: 23, backlog: 9, onBots: 4, overdue: 2 })).toEqual({
      lead: "23 open.",
      rest: "9 in Backlog, 4 on bot users, 2 overdue.",
    })
  })

  test("leaves out what there is none of", () => {
    expect(counts({ open: 5, backlog: 0, onBots: 1, overdue: 0 })).toEqual({
      lead: "5 open.",
      rest: "1 on a bot user.",
    })
    expect(counts({ open: 5, backlog: 0, onBots: 0, overdue: 0 })).toEqual({
      lead: "5 open.",
      rest: "",
    })
  })

  test("says plainly that nothing is open", () => {
    expect(counts({ open: 0, backlog: 0, onBots: 0, overdue: 0 })).toEqual({
      lead: "Nothing is open.",
      rest: "",
    })
  })
})

describe("the order menu", () => {
  test("opens on newest first, which is no order at all in the URL", () => {
    expect(orderChoice({})).toEqual({ label: "Newest first", reversed: false })
  })

  test("names each order in the direction it is running", () => {
    expect(orderChoice({ sort: "due_date" }).label).toBe("Due soonest first")
    expect(orderChoice({ sort: "due_date", order: "desc" }).label).toBe(
      "Due latest first",
    )
    expect(orderChoice({ sort: "priority" }).label).toBe("Priority, P1 first")
    expect(orderChoice({ sort: "priority", order: "desc" }).label).toBe(
      "Priority, P4 first",
    )
    expect(orderChoice({ sort: "created_at" }).label).toBe(
      "Filed, newest first",
    )
    expect(orderChoice({ sort: "created_at", order: "asc" }).label).toBe(
      "Filed, oldest first",
    )
  })

  test("a direction that is the natural one is not a reversal", () => {
    expect(orderChoice({ sort: "due_date", order: "asc" }).reversed).toBe(false)
    expect(orderChoice({ sort: "created_at", order: "desc" }).reversed).toBe(
      false,
    )
    expect(orderChoice({ sort: "created_at", order: "asc" }).reversed).toBe(
      true,
    )
  })
})

describe("choosing an order", () => {
  test("gives an order its natural direction", () => {
    expect(chooseOrder({}, "due_date")).toEqual({
      sort: "due_date",
      order: undefined,
    })
    expect(chooseOrder({ sort: "priority" }, "created_at")).toEqual({
      sort: "created_at",
      order: undefined,
    })
  })

  test("reverses an order chosen again, and turns it back the third time", () => {
    const once = chooseOrder({}, "due_date")
    const twice = chooseOrder(once, "due_date")
    expect(twice).toEqual({ sort: "due_date", order: "desc" })
    expect(chooseOrder(twice, "due_date")).toEqual({
      sort: "due_date",
      order: undefined,
    })
    expect(chooseOrder({ sort: "created_at" }, "created_at")).toEqual({
      sort: "created_at",
      order: "asc",
    })
  })

  test("choosing the list's own order drops the sort and any reversal", () => {
    expect(chooseOrder({ sort: "priority", order: "desc" }, undefined)).toEqual(
      { sort: undefined, order: undefined },
    )
  })
})

describe("the time filter's label", () => {
  test("says nothing is set as any time", () => {
    expect(timeLabel({})).toBeUndefined()
  })

  test("names overdue, a range, or one open end of it", () => {
    expect(timeLabel({ overdue: true })).toBe("Overdue")
    expect(timeLabel({ due_from: "2026-10-01" })).toMatch(/^From /)
    expect(timeLabel({ due_to: "2026-10-09" })).toMatch(/^To /)
    expect(timeLabel({ due_from: "2026-10-01", due_to: "2026-10-09" })).toMatch(
      / – /,
    )
  })

  test("keeps overdue beside a range rather than hiding it", () => {
    expect(timeLabel({ overdue: true, due_to: "2026-10-09" })).toMatch(
      /^Overdue, to /,
    )
  })
})
