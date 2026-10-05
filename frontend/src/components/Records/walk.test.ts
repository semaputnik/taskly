import { describe, expect, test } from "bun:test"

import { joinLists, neighbours } from "./walk"

describe("joining the lists on a page", () => {
  test("runs them in rank order, whatever order they arrived in", () => {
    expect(
      joinLists([
        { rank: 1, ids: ["c", "d"] },
        { rank: 0, ids: ["a", "b"] },
      ]),
    ).toEqual(["a", "b", "c", "d"])
  })

  test("keeps a record that is in two groups at its first place only", () => {
    expect(
      joinLists([
        { rank: 0, ids: ["a", "b"] },
        { rank: 1, ids: ["b", "c"] },
      ]),
    ).toEqual(["a", "b", "c"])
  })
})

describe("the neighbours of the open record", () => {
  const list = ["a", "b", "c"]

  test("say where it is and what comes before and after", () => {
    expect(neighbours(list, "b")).toEqual({
      position: 2,
      count: 3,
      previous: "a",
      next: "c",
    })
  })

  test("have no previous at the start and no next at the end", () => {
    expect(neighbours(list, "a")?.previous).toBeUndefined()
    expect(neighbours(list, "c")?.next).toBeUndefined()
  })

  test("are nothing when the record was not opened from the list", () => {
    expect(neighbours(list, "z")).toBeNull()
    expect(neighbours([], "a")).toBeNull()
    expect(neighbours(list, null)).toBeNull()
  })

  test("are nothing for a list of one: there is nowhere to walk", () => {
    expect(neighbours(["a"], "a")).toBeNull()
  })
})
