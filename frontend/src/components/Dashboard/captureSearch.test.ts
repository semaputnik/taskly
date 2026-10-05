import { describe, expect, test } from "bun:test"

import {
  type Answer,
  matchesFor,
  opensUpward,
  searchTerm,
  stepActive,
  titleParts,
} from "./captureSearch"

const task = (title: string) => ({ id: title, title })

describe("what the line searches for", () => {
  test("is the typed text once it is two characters long", () => {
    expect(searchTerm("")).toBeNull()
    expect(searchTerm("r")).toBeNull()
    expect(searchTerm("re")).toBe("re")
    expect(searchTerm("redirect")).toBe("redirect")
  })

  test("leaves out the spaces around it, which are not part of a title", () => {
    expect(searchTerm("  r ")).toBeNull()
    expect(searchTerm("  re ")).toBe("re")
    expect(searchTerm("   ")).toBeNull()
  })

  test("keeps the spaces inside it", () => {
    expect(searchTerm("old url")).toBe("old url")
  })
})

describe("which matches are on show while a newer answer is awaited", () => {
  const answer = (
    text: string,
    ...titles: string[]
  ): Answer<{
    id: string
    title: string
  }> => ({ text, tasks: titles.map(task) })

  test("is nothing under two characters, whatever was answered before", () => {
    expect(matchesFor("r", answer("re", "Redo"))).toEqual({
      tasks: [],
      current: false,
    })
  })

  test("is nothing before the first answer", () => {
    expect(matchesFor("re", undefined)).toEqual({ tasks: [], current: false })
  })

  test("is the answer to the text typed, as it came", () => {
    // The server's case-folding is its own: what it sent is not second-guessed.
    expect(matchesFor("straße", answer("straße", "STRASSE"))).toEqual({
      tasks: [task("STRASSE")],
      current: true,
    })
  })

  test("is what an older answer still satisfies, while the newer one comes", () => {
    const older = answer("re", "Redirect map", "Rewrite copy", "Check the URL")
    expect(matchesFor("red", older)).toEqual({
      tasks: [task("Redirect map")],
      current: false,
    })
  })

  test("reads the older answer without regard to case", () => {
    expect(matchesFor("RED", answer("re", "Check the redirect"))).toEqual({
      tasks: [task("Check the redirect")],
      current: false,
    })
  })

  test("is never an answer to other text than was typed, once the line moved on", () => {
    // Backspacing from "redirect" to "re": the older answer is a subset of
    // the true one, and says so by not being current.
    const { current } = matchesFor("re", answer("redirect", "Redirect map"))
    expect(current).toBe(false)
  })
})

describe("the typed text, marked in a title", () => {
  test("splits a title around where the text occurs, in any case", () => {
    expect(titleParts("Check the Redirect map", "redirect")).toEqual([
      { text: "Check the ", match: false },
      { text: "Redirect", match: true },
      { text: " map", match: false },
    ])
  })

  test("marks every place it occurs", () => {
    expect(titleParts("a-b-a", "a")).toEqual([
      { text: "a", match: true },
      { text: "-b-", match: false },
      { text: "a", match: true },
    ])
  })

  test("is one plain part when the text is not in the title", () => {
    expect(titleParts("Pay rent", "visa")).toEqual([
      { text: "Pay rent", match: false },
    ])
  })

  test("reads what looks like a pattern as plain letters", () => {
    expect(titleParts("Save 50% (maybe)", "50% (")).toEqual([
      { text: "Save ", match: false },
      { text: "50% (", match: true },
      { text: "maybe)", match: false },
    ])
  })

  test("marks a title that is nothing but the text", () => {
    expect(titleParts("Redirect", "redirect")).toEqual([
      { text: "Redirect", match: true },
    ])
  })
})

describe("moving through the matches with the arrow keys", () => {
  test("starts on the line itself, where Enter still creates", () => {
    expect(stepActive(-1, 3, "ArrowDown")).toBe(0)
  })

  test("walks down through the list, then back to the line", () => {
    expect(stepActive(0, 3, "ArrowDown")).toBe(1)
    expect(stepActive(2, 3, "ArrowDown")).toBe(-1)
  })

  test("walks up from the line to the last match, and on to the line", () => {
    expect(stepActive(-1, 3, "ArrowUp")).toBe(2)
    expect(stepActive(2, 3, "ArrowUp")).toBe(1)
    expect(stepActive(0, 3, "ArrowUp")).toBe(-1)
  })

  test("stays on the line when there is nothing to move through", () => {
    expect(stepActive(-1, 0, "ArrowDown")).toBe(-1)
    expect(stepActive(-1, 0, "ArrowUp")).toBe(-1)
  })

  test("falls back to the line when the list shrank under the position", () => {
    expect(stepActive(5, 2, "ArrowDown")).toBe(0)
  })
})

describe("which way the matches open", () => {
  const needed = 360

  test("opens down when there is room below the line", () => {
    expect(opensUpward({ top: 100, bottom: 140 }, 800, needed)).toBe(false)
  })

  test("opens up when the line is low and the room is above it", () => {
    expect(opensUpward({ top: 700, bottom: 740 }, 800, needed)).toBe(true)
  })

  test("opens up for a line pinned just above the bottom of the screen", () => {
    expect(opensUpward({ top: 740, bottom: 780 }, 812, needed)).toBe(true)
  })

  test("opens toward the larger side when neither has the room", () => {
    expect(opensUpward({ top: 250, bottom: 290 }, 400, needed)).toBe(true)
    expect(opensUpward({ top: 100, bottom: 140 }, 400, needed)).toBe(false)
  })
})
