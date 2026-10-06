import { describe, expect, test } from "bun:test"

import {
  openPanelKind,
  panelSearchSchema,
  RECORD_KINDS,
  recordLink,
  withoutPanelState,
} from "./panels"

const ID = "7f1c2e44-3a4b-4c1d-9e2f-0a1b2c3d4e5f"
const OTHER = "0d9e8f7a-6b5c-4d3e-8f1a-2b3c4d5e6f70"

describe("the panel search schema", () => {
  test("has a key for every declared kind, and capture", () => {
    expect(Object.keys(panelSearchSchema.shape).sort()).toEqual(
      ["bot", "capture", "project", "tag_id", "task"].sort(),
    )
    expect(Object.keys(RECORD_KINDS).sort()).toEqual(
      ["bot", "project", "tag", "task"].sort(),
    )
  })

  test("accepts exactly the declared keys, and drops what is unusable", () => {
    expect(
      panelSearchSchema.parse({
        task: ID,
        project: "not-an-id",
        tag_id: ID,
        bot: ID,
        capture: "bot",
        tag: "errands",
        page: 2,
      }),
    ).toEqual({
      task: ID,
      project: undefined,
      tag_id: ID,
      bot: ID,
      capture: undefined,
    })
    expect(panelSearchSchema.parse({ capture: "tag" }).capture).toBe("tag")
  })
})

describe("a link to a record", () => {
  const previous = {
    task: OTHER,
    project: OTHER,
    tag_id: OTHER,
    bot: OTHER,
    capture: "task",
    // Not panels: the list's own view stays as it is.
    project_id: OTHER,
    tag: "errands",
    page: 3,
  }

  test.each([
    ["task", { task: ID }],
    ["project", { project: ID }],
    ["tag", { tag_id: ID }],
    ["bot", { bot: ID }],
  ] as const)("opens only the %s panel", (kind, open) => {
    const link = recordLink(kind, ID)
    expect(link.to).toBe(".")
    expect(link.search(previous)).toEqual({
      task: undefined,
      project: undefined,
      tag_id: undefined,
      bot: undefined,
      capture: undefined,
      ...open,
      project_id: OTHER,
      tag: "errands",
      page: 3,
    })
  })
})

test("a query leaves every panel key behind", () => {
  expect(
    withoutPanelState({
      task: ID,
      project: ID,
      tag_id: ID,
      bot: ID,
      capture: "task",
      tag: "errands",
      page: 2,
    }),
  ).toEqual({ tag: "errands", page: 2 })
})

describe("which panel is open", () => {
  test("is the kind whose record the search names", () => {
    expect(openPanelKind({ task: ID })).toBe("task")
    expect(openPanelKind({ tag_id: ID })).toBe("tag")
    expect(openPanelKind({ bot: ID })).toBe("bot")
    expect(openPanelKind({ project: ID })).toBe("project")
  })

  test("is the kind being captured when no record is named", () => {
    expect(openPanelKind({ capture: "project" })).toBe("project")
  })

  test("is none when the search names nothing", () => {
    expect(openPanelKind({})).toBeUndefined()
  })
})
