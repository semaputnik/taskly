import { describe, expect, test } from "bun:test"

import type { ActivityEntryPublic } from "@/client"
import {
  emptyMessage,
  lede,
  logDays,
  ME,
  PAGE_SIZE,
  pagerLabels,
  pagerText,
} from "./words"

const at = (created_at: string) =>
  ({ id: created_at, created_at }) as ActivityEntryPublic

describe("lede", () => {
  test("counts the entries and how many are the bot users'", () => {
    expect(lede(29, 20, "newest")).toEqual({
      lead: "Every change in your account, newest first.",
      rest: "29 entries, 20 of them by your bot users.",
    })
  })

  test("follows the order", () => {
    expect(lede(2, 0, "oldest").lead).toBe(
      "Every change in your account, oldest first.",
    )
  })

  test("says when none, one or all are the bot users'", () => {
    expect(lede(3, 0, "newest").rest).toBe(
      "3 entries, none of them by your bot users.",
    )
    expect(lede(1, 1, "newest").rest).toBe("1 entry, by one of your bot users.")
    expect(lede(4, 4, "newest").rest).toBe("4 entries, all by your bot users.")
  })

  test("leaves out a count that could not be read", () => {
    expect(lede(null, null, "newest").rest).toBe("")
    expect(lede(5, null, "newest").rest).toBe("5 entries.")
    expect(lede(0, 0, "newest").rest).toBe("Nothing has happened yet.")
  })
})

describe("emptyMessage", () => {
  test("names what the log was narrowed to", () => {
    expect(emptyMessage(undefined, undefined)).toBe(
      "Nothing has happened in your account yet.",
    )
    expect(emptyMessage(undefined, "completed")).toBe(
      "Nothing has been completed yet.",
    )
    expect(emptyMessage("bot", undefined)).toBe(
      "This bot user has not changed anything yet.",
    )
    expect(emptyMessage("bot", "tags")).toBe(
      "This bot user has nothing under “Tags”.",
    )
    expect(emptyMessage(ME, undefined)).toBe(
      "You have not changed anything yet.",
    )
    expect(emptyMessage(ME, "deleted")).toBe(
      "You have nothing under “Deleted & restored”.",
    )
  })
})

describe("logDays", () => {
  const now = new Date(2026, 9, 6, 12, 0)

  test("groups consecutive lines by day, in the order given", () => {
    const days = logDays(
      [
        at(new Date(2026, 9, 6, 9, 0).toISOString()),
        at(new Date(2026, 9, 6, 8, 0).toISOString()),
        at(new Date(2026, 9, 5, 22, 0).toISOString()),
        at(new Date(2026, 9, 1, 10, 0).toISOString()),
      ],
      now,
    )
    expect(days.map((d) => [d.heading, d.entries.length])).toEqual([
      ["Today", 2],
      ["Yesterday", 1],
      [
        new Date(2026, 9, 1).toLocaleDateString(undefined, {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        }),
        1,
      ],
    ])
  })

  test("reads oldest first as well", () => {
    const days = logDays(
      [
        at(new Date(2026, 9, 5, 22, 0).toISOString()),
        at(new Date(2026, 9, 6, 8, 0).toISOString()),
      ],
      now,
    )
    expect(days.map((d) => d.heading)).toEqual(["Yesterday", "Today"])
  })
})

describe("pager", () => {
  test("says the page only when there is more than one", () => {
    expect(pagerText(29, 1, 1)).toBe("29 entries")
    expect(pagerText(1, 1, 1)).toBe("1 entry")
    expect(pagerText(PAGE_SIZE + 1, 1, 2)).toBe(
      `${PAGE_SIZE + 1} entries · page 1 of 2`,
    )
  })

  test("calls a page further on older or newer by the order", () => {
    expect(pagerLabels("newest")).toEqual({ back: "Newer", on: "Older" })
    expect(pagerLabels("oldest")).toEqual({ back: "Older", on: "Newer" })
  })
})
