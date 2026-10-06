import { describe, expect, test } from "bun:test"

import type { BotPermissions, BotUserPublic } from "@/client"
import {
  counts,
  lastUseInWords,
  monogram,
  permissionsInWords,
  projectsInWords,
  reachInWords,
  stillNamedInWords,
} from "./words"

const NONE: BotPermissions = {
  read_tasks: false,
  create_tasks: false,
  update_tasks: false,
  delete_tasks: false,
  add_comments: false,
  create_tags: false,
}

const bot = (patch: Partial<BotUserPublic> = {}): BotUserPublic => ({
  id: "b",
  name: "inbox-triage",
  scope: { project_ids: [], permissions: NONE },
  has_token: true,
  webhooks: { task: {}, comment: {}, has_secret: false },
  ...patch,
})

describe("the plate", () => {
  test.each([
    ["inbox-triage", "IT"],
    ["research agent", "RA"],
    ["Nightly", "NI"],
    ["x", "X"],
    ["  --  ", "?"],
    ["calendar_sync_2", "CS"],
  ])("%s is %s", (name, plate) => {
    expect(monogram(name)).toBe(plate)
  })
})

describe("permissions in words", () => {
  test("in the order a reader thinks of them", () => {
    expect(
      permissionsInWords({
        ...NONE,
        add_comments: true,
        read_tasks: true,
        create_tags: true,
        update_tasks: true,
      }),
    ).toBe("reads, updates, comments, tags")
  })

  test("the reach sentence says what tags are for", () => {
    expect(
      permissionsInWords(
        { ...NONE, read_tasks: true, create_tags: true },
        { forReach: true },
      ),
    ).toBe("reads, creates tags")
  })

  test("none at all is said", () => {
    expect(permissionsInWords(NONE)).toBe("no permissions")
  })
})

describe("projects in words", () => {
  const projects = {
    a: { name: "Inbox", archived: false },
    b: { name: "Old site", archived: true },
  }

  test("names each, and says which are archived or gone", () => {
    expect(projectsInWords(["a", "b", "zzz"], projects)).toBe(
      "Inbox, Old site (archived), an unavailable project",
    )
    expect(projectsInWords([], projects)).toBe("no projects")
  })

  test("reach joins where and what in one sentence", () => {
    expect(
      reachInWords(
        bot({
          scope: {
            project_ids: ["a"],
            permissions: { ...NONE, read_tasks: true },
          },
        }),
        projects,
      ),
    ).toBe("Inbox · reads")
  })
})

describe("last use", () => {
  const now = new Date("2026-10-06T12:00:00Z").getTime()
  const at = (hoursAgo: number) =>
    new Date(now - hoursAgo * 3_600_000).toISOString()

  test("says never, just now, hours, yesterday and days", () => {
    expect(lastUseInWords({}, now)).toBe("never used")
    expect(lastUseInWords({ token_last_used_at: at(0.001) }, now)).toBe(
      "used just now",
    )
    expect(lastUseInWords({ token_last_used_at: at(2) }, now)).toBe(
      "used 2 hours ago",
    )
    expect(lastUseInWords({ token_last_used_at: at(30) }, now)).toBe(
      "used yesterday",
    )
    expect(lastUseInWords({ token_last_used_at: at(240) }, now)).toBe(
      "used 10 days ago",
    )
  })
})

describe("what a deleted bot user is still named on", () => {
  test("counts tasks, and always the log", () => {
    expect(stillNamedInWords(0)).toBe("still named in the log")
    expect(stillNamedInWords(1)).toBe("still named on 1 task and in the log")
    expect(stillNamedInWords(3)).toBe("still named on 3 tasks and in the log")
  })
})

describe("the sentence under the heading", () => {
  const now = new Date("2026-10-06T12:00:00Z")
  const working = bot({ has_token: true })
  const without = bot({ has_token: false })
  const revoked = bot({ has_token: false, token_revoked_at: "2026-10-01" })
  const expired = bot({ token_expires_at: "2026-10-01T00:00:00Z" })

  test("counts the bot users, how many work, and the week's changes", () => {
    expect(counts([working, working, working, without], 20, now)).toEqual({
      lead: "4 bot users.",
      rest: "3 working, 1 without a token. They made 20 changes this week.",
    })
  })

  test("a revoked token is without one, an expired one is its own count", () => {
    expect(counts([revoked, expired, working], 1, now).rest).toBe(
      "1 working, 1 without a token, 1 with an expired token. They made 1 change this week.",
    )
  })

  test("one bot user, no changes, and changes not yet known", () => {
    expect(counts([working], 0, now)).toEqual({
      lead: "1 bot user.",
      rest: "1 working. It made no changes this week.",
    })
    expect(counts([working], null, now).rest).toBe("1 working.")
  })
})
