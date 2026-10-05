import { describe, expect, test } from "bun:test"

import { navCount } from "./counts"

describe("navCount", () => {
  test("says nothing while the count is unknown", () => {
    expect(navCount(undefined, "task")).toBeNull()
  })

  test("says nothing for an empty screen", () => {
    expect(navCount(0, "task")).toBeNull()
  })

  test("shows the figure and names what it counts", () => {
    expect(navCount(1, "open task")).toEqual({
      figure: "1",
      description: "1 open task",
    })
    expect(navCount(8, "open task")).toEqual({
      figure: "8",
      description: "8 open tasks",
    })
  })

  test("caps the figure but keeps the full count for a screen reader", () => {
    expect(navCount(1234, "project")).toEqual({
      figure: "999+",
      description: "1234 projects",
    })
  })
})
