import { describe, expect, test } from "bun:test"

import { byDay, clock, windowLabel } from "./log"

// Local parts throughout: the log is read in the reader's own calendar.
const NOW = new Date(2026, 9, 5, 10, 30) // Monday 5 October 2026, 10:30

describe("what the Changes heading says it covers", () => {
  test("a first visit has no last one, so the log is everything so far", () => {
    expect(windowLabel(null, NOW, "en-GB")).toBe("so far")
  })

  test("a visit earlier today is named by its time alone", () => {
    expect(windowLabel(new Date(2026, 9, 5, 9, 12), NOW, "en-GB")).toBe(
      "since 09:12",
    )
  })

  test("yesterday is named as yesterday", () => {
    expect(windowLabel(new Date(2026, 9, 4, 17, 0), NOW, "en-GB")).toBe(
      "since yesterday 17:00",
    )
  })

  test("earlier this week by its weekday", () => {
    expect(windowLabel(new Date(2026, 9, 1, 14, 5), NOW, "en-GB")).toBe(
      "since Thursday 14:05",
    )
  })

  test("further back by its date, the year only when it is another", () => {
    expect(windowLabel(new Date(2026, 8, 28, 8, 0), NOW, "en-GB")).toMatch(
      // ICU versions differ on September's short name.
      /^since 28 Sept?$/,
    )
    expect(windowLabel(new Date(2025, 11, 30, 8, 0), NOW, "en-GB")).toBe(
      "since 30 Dec 2025",
    )
  })
})

describe("the time a line was written", () => {
  test("is the time to the minute", () => {
    expect(clock(new Date(2026, 9, 5, 7, 4), "en-GB")).toBe("07:04")
    expect(clock(new Date(2026, 9, 5, 16, 54), "en-GB")).toBe("16:54")
  })
})

describe("the lines, by the day they were written", () => {
  const at = (day: number, hour: number) => ({
    id: `${day}-${hour}`,
    created_at: new Date(2026, 9, day, hour).toISOString(),
  })

  test("today's lines need no label; earlier days are named", () => {
    const groups = byDay(
      [at(5, 10), at(5, 8), at(4, 22), at(4, 18), at(2, 9), at(1, 9)],
      NOW,
      "en-GB",
    )
    expect(
      groups.map((group) => [
        group.label,
        group.entries.map((entry) => entry.id),
      ]),
    ).toEqual([
      [null, ["5-10", "5-8"]],
      ["Yesterday", ["4-22", "4-18"]],
      ["Friday", ["2-9"]],
      ["Thursday", ["1-9"]],
    ])
  })

  test("a log that starts before today labels its first day too", () => {
    const groups = byDay([at(4, 9)], NOW, "en-GB")
    expect(groups.map((group) => group.label)).toEqual(["Yesterday"])
  })

  test("a week back and more is named by its date", () => {
    const groups = byDay(
      [
        at(1, 9),
        { id: "old", created_at: new Date(2026, 8, 20, 9).toISOString() },
      ],
      NOW,
      "en-GB",
    )
    expect(groups.map((group) => group.label)).toEqual([
      "Thursday",
      expect.stringMatching(/^20 Sept?$/),
    ])
  })

  test("an empty log has no days", () => {
    expect(byDay([], NOW)).toEqual([])
  })
})
