import { describe, expect, test } from "bun:test"

import {
  dayHeading,
  lede,
  markSeen,
  peekVisitSince,
  type VisitStore,
  visitSince,
} from "./day"

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

  test("counts the bot users' changes since the last visit", () => {
    const visit = (changes: number) =>
      lede({ needYou: 0, changes, window: "visit" }).changes
    expect(visit(1)).toBe("Your bot users made 1 change since your last visit.")
    expect(visit(6)).toBe(
      "Your bot users made 6 changes since your last visit.",
    )
  })

  test("on a first visit there is no last one to count from", () => {
    const ever = (changes: number) =>
      lede({ needYou: 0, changes, window: "ever" }).changes
    expect(ever(1)).toBe("Your bot users have made 1 change so far.")
    expect(ever(4)).toBe("Your bot users have made 4 changes so far.")
  })

  // The count is the bot users' alone: the reader's own changes are not part
  // of it, so there is no share of a total to name and no zero to say.
  test("says plainly that no bot user has changed anything", () => {
    expect(lede({ needYou: 0, changes: 0, window: "visit" }).changes).toBe(
      "No bot user has changed anything yet.",
    )
    expect(lede({ needYou: 0, changes: 0, window: "ever" }).changes).toBe(
      "No bot user has changed anything yet.",
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

  test("leaving moves the next session's start, not this one's", () => {
    const store = stores()
    const EVENING = new Date("2026-10-05T19:00:00Z")
    visitSince(store, MONDAY)
    markSeen(store, EVENING)
    expect(visitSince(store, EVENING)).toBeNull()
    const tuesday = { ...stores(), local: store.local }
    expect(visitSince(tuesday, TUESDAY)).toBe(EVENING.toISOString())
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

  test("can be read ahead of the page without moving anything", () => {
    const first = stores()
    expect(peekVisitSince(first)).toBeNull()
    expect(first.dump()).toEqual({ local: {}, session: {} })
    expect(visitSince(first, MONDAY)).toBeNull()

    const tuesday = { ...stores(), local: first.local }
    const before = tuesday.dump()
    // What the page will count from, said before the page fixes it.
    expect(peekVisitSince(tuesday)).toBe(MONDAY.toISOString())
    expect(tuesday.dump()).toEqual(before)
    expect(visitSince(tuesday, TUESDAY)).toBe(MONDAY.toISOString())
    // And once fixed, the same answer for the rest of the session.
    expect(peekVisitSince(tuesday)).toBe(MONDAY.toISOString())
  })

  test("read ahead from storage that refuses, is a first visit", () => {
    const refusing = {
      getItem: () => {
        throw new Error("blocked")
      },
      setItem: () => {
        throw new Error("blocked")
      },
    }
    expect(peekVisitSince({ local: refusing, session: refusing })).toBeNull()
  })
})
