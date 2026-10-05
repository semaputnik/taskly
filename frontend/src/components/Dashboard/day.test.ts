import { describe, expect, test } from "bun:test"

import { dayHeading, lede, type VisitStore, visitSince } from "./day"

describe("the date at the top of the day page", () => {
  test("is the day of the month, two digits, and the rest beside it", () => {
    // Local parts: the page is read in the reader's own calendar.
    expect(dayHeading(new Date(2026, 9, 5), "en-US")).toEqual({
      day: "05",
      rest: "Monday, October 2026",
    })
    expect(dayHeading(new Date(2026, 11, 31), "en-US")).toEqual({
      day: "31",
      rest: "Thursday, December 2026",
    })
  })
})

describe("the sentence under the date", () => {
  test("counts what needs the reader, in the number it is", () => {
    expect(lede({ needYou: 0, changes: 0, window: "visit" }).needs).toBe(
      "Nothing needs you today.",
    )
    expect(lede({ needYou: 1, changes: 0, window: "visit" }).needs).toBe(
      "1 needs you.",
    )
    expect(lede({ needYou: 3, changes: 0, window: "visit" }).needs).toBe(
      "3 need you.",
    )
  })

  test("counts the agents' changes since the last visit", () => {
    expect(lede({ needYou: 0, changes: 0, window: "visit" }).changes).toBe(
      "Your agents made no changes since your last visit.",
    )
    expect(lede({ needYou: 0, changes: 1, window: "visit" }).changes).toBe(
      "Your agents made 1 change since your last visit.",
    )
    expect(lede({ needYou: 0, changes: 6, window: "visit" }).changes).toBe(
      "Your agents made 6 changes since your last visit.",
    )
  })

  test("on a first visit there is no last one to count from", () => {
    expect(lede({ needYou: 0, changes: 0, window: "ever" }).changes).toBe(
      "Your agents have made no changes yet.",
    )
    expect(lede({ needYou: 0, changes: 1, window: "ever" }).changes).toBe(
      "Your agents have made 1 change so far.",
    )
    expect(lede({ needYou: 0, changes: 4, window: "ever" }).changes).toBe(
      "Your agents have made 4 changes so far.",
    )
  })
})

/** Two in-memory storages standing in for the browser's. */
function stores(): VisitStore & { dump: () => Record<string, unknown> } {
  const local = new Map<string, string>()
  const session = new Map<string, string>()
  const wrap = (map: Map<string, string>) => ({
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => void map.set(key, value),
  })
  return {
    local: wrap(local),
    session: wrap(session),
    dump: () => ({
      local: Object.fromEntries(local),
      session: Object.fromEntries(session),
    }),
  }
}

describe("the last visit", () => {
  const MONDAY = new Date("2026-10-05T08:00:00Z")
  const LATER = new Date("2026-10-05T08:30:00Z")
  const TUESDAY = new Date("2026-10-06T09:00:00Z")

  test("a first visit has none, and is remembered as the next one's", () => {
    const store = stores()
    expect(visitSince(store, MONDAY)).toBeNull()

    const nextSession = { ...stores(), local: store.local }
    expect(visitSince(nextSession, TUESDAY)).toBe(MONDAY.toISOString())
  })

  test("holds still for the rest of the session, through reloads", () => {
    const store = stores()
    visitSince(store, MONDAY)
    const tuesday = { ...stores(), local: store.local }
    expect(visitSince(tuesday, TUESDAY)).toBe(MONDAY.toISOString())
    // Reading the page again in the same session does not reset the count.
    expect(visitSince(tuesday, new Date("2026-10-06T09:05:00Z"))).toBe(
      MONDAY.toISOString(),
    )
  })

  test("a first visit stays a first visit for its whole session", () => {
    const store = stores()
    expect(visitSince(store, MONDAY)).toBeNull()
    expect(visitSince(store, LATER)).toBeNull()
  })

  test("the next session counts from the latest look, not the first", () => {
    const store = stores()
    visitSince(store, MONDAY)
    visitSince(store, LATER)
    const tuesday = { ...stores(), local: store.local }
    expect(visitSince(tuesday, TUESDAY)).toBe(LATER.toISOString())
  })

  test("storage that refuses is a first visit, not a failure", () => {
    const refusing = {
      getItem: () => {
        throw new Error("blocked")
      },
      setItem: () => {
        throw new Error("blocked")
      },
    }
    expect(visitSince({ local: refusing, session: refusing }, MONDAY)).toBe(
      null,
    )
  })
})
