import { describe, expect, test } from "bun:test"

import {
  dateInWords,
  dayHeading,
  formatDateTime,
  formatDay,
  formatDayOf,
  formatDayPlain,
} from "./dates"

// September is "Sept" in current browsers and "Sep" in older ICU data, so the
// tests accept both; everything else about the format is pinned.

// A Wednesday, in the afternoon: late enough that a UTC reading of a local
// midnight would land on the day before for anyone west of Greenwich.
const NOW = new Date(2026, 9, 7, 15, 30)

describe("a day in words", () => {
  test("names today, tomorrow and yesterday", () => {
    expect(formatDay("2026-10-07", NOW, "en-GB")).toBe("Today")
    expect(formatDay("2026-10-08", NOW, "en-GB")).toBe("Tomorrow")
    expect(formatDay("2026-10-06", NOW, "en-GB")).toBe("Yesterday")
  })

  test("writes any other day of this year as the day and a short month", () => {
    expect(formatDay("2026-09-24", NOW, "en-GB")).toMatch(/^24 Sept?$/)
    expect(formatDay("2026-10-09", NOW, "en-GB")).toBe("9 Oct")
  })

  test("adds the year when it is not this one", () => {
    expect(formatDay("2025-09-24", NOW, "en-GB")).toMatch(/^24 Sept? 2025$/)
    expect(formatDay("2027-01-04", NOW, "en-GB")).toBe("4 Jan 2027")
  })

  test("lets the reader's locale order the parts", () => {
    expect(formatDay("2026-09-24", NOW, "en-US")).toBe("Sep 24")
    expect(formatDay("2025-09-24", NOW, "en-US")).toBe("Sep 24, 2025")
  })

  test("counts calendar days, not hours, across the new year", () => {
    const lateNewYearsEve = new Date(2026, 11, 31, 23, 59)
    expect(formatDay("2027-01-01", lateNewYearsEve, "en-GB")).toBe("Tomorrow")
    const earlyNewYear = new Date(2027, 0, 1, 0, 1)
    expect(formatDay("2026-12-31", earlyNewYear, "en-GB")).toBe("Yesterday")
  })

  test("shows something that is not a day as it came", () => {
    expect(formatDay("soon", NOW, "en-GB")).toBe("soon")
  })

  test("keeps a stored day on its own calendar day", () => {
    // Parsed as UTC, midnight of the 24th would be the 23rd west of London.
    expect(formatDay("2026-09-24", NOW, "en-GB")).toMatch(/^24 Sept?$/)
  })

  test("the plain form never says Today", () => {
    expect(formatDayPlain("2026-10-07", NOW, "en-GB")).toBe("7 Oct")
    expect(dateInWords(new Date(2026, 9, 7), NOW, "en-GB")).toBe("7 Oct")
  })
})

describe("the day a moment falls on", () => {
  test("reads the local day of a timestamp", () => {
    const yesterday = new Date(2026, 9, 6, 23, 50).toISOString()
    expect(formatDayOf(yesterday, NOW, "en-GB")).toBe("Yesterday")
    const old = new Date(2025, 2, 3, 9, 0).toISOString()
    expect(formatDayOf(old, NOW, "en-GB")).toBe("3 Mar 2025")
  })

  test("a history separator is the same words", () => {
    const at = new Date(2026, 9, 1, 8, 0).toISOString()
    expect(dayHeading(at, NOW)).toBe(formatDayOf(at, NOW))
    expect(dayHeading(new Date(2026, 9, 7, 8, 0).toISOString(), NOW)).toBe(
      "Today",
    )
  })

  test("a moment adds its time to the minute", () => {
    const at = new Date(2026, 9, 7, 9, 5).toISOString()
    expect(formatDateTime(at, NOW, "en-GB")).toBe("Today, 09:05")
    const earlier = new Date(2026, 8, 24, 9, 5).toISOString()
    expect(formatDateTime(earlier, NOW, "en-GB")).toMatch(/^24 Sept?, 09:05$/)
  })
})
