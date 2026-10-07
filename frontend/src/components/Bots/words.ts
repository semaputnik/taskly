import type { BotPermissions, BotUserPublic } from "@/client"
import { formatDayOf, inSentence } from "@/lib/dates"
import { since } from "./health"
import { tokenStatus } from "./tokens"

/**
 * What a bot user is, said the way a person would say it: the words on its
 * line in the list, the sentence under the page's heading, and the one
 * sentence of reach in its column.
 *
 * Plain functions, so the wording can be read and tested apart from the page.
 */

/** A bot user's two letters on its plate: "inbox-triage" is "IT". */
export function monogram(name: string): string {
  const words = name.match(/[\p{L}\p{N}]+/gu) ?? []
  const [first, second] = words
  if (!first) return "?"
  const letters = second
    ? `${Array.from(first)[0]}${Array.from(second)[0]}`
    : Array.from(first).slice(0, 2).join("")
  return letters.toUpperCase()
}

// Each grant as the verb it is, in the order a reader thinks of them.
const GRANTS: { key: keyof BotPermissions; words: string; reach: string }[] = [
  { key: "read_tasks", words: "reads", reach: "reads" },
  { key: "create_tasks", words: "creates", reach: "creates" },
  { key: "update_tasks", words: "updates", reach: "updates" },
  { key: "delete_tasks", words: "deletes", reach: "deletes" },
  { key: "add_comments", words: "comments", reach: "comments" },
  { key: "create_tags", words: "tags", reach: "creates tags" },
]

/** What it may do: "reads, updates, comments", or that it may do nothing. */
export function permissionsInWords(
  permissions: BotPermissions,
  { forReach = false } = {},
): string {
  const granted = GRANTS.filter(({ key }) => permissions[key]).map(
    ({ words, reach }) => (forReach ? reach : words),
  )
  return granted.length > 0 ? granted.join(", ") : "no permissions"
}

/** The projects it reaches, by name: archived ones say so, unknown ones too. */
export function projectsInWords(
  projectIds: string[],
  projects: Record<string, { name: string; archived: boolean }>,
): string {
  if (projectIds.length === 0) return "no projects"
  return projectIds
    .map((id) => {
      const project = projects[id]
      if (!project) return "an unavailable project"
      return project.archived ? `${project.name} (archived)` : project.name
    })
    .join(", ")
}

/** Everything a bot user reaches and does, as one sentence. */
export function reachInWords(
  bot: BotUserPublic,
  projects: Record<string, { name: string; archived: boolean }>,
): string {
  const where = projectsInWords(bot.scope.project_ids, projects)
  const what = permissionsInWords(bot.scope.permissions, { forReach: true })
  return `${where} · ${what}`
}

/** The state of the token as the line says it. */
export const TOKEN_WORDS = {
  active: "Working",
  none: "No token",
  revoked: "Revoked",
  expired: "Expired",
} as const

/** When it was last heard from, in the line's right-hand column. */
export function lastUseInWords(
  bot: Pick<BotUserPublic, "token_last_used_at">,
  now = Date.now(),
): string {
  const at = bot.token_last_used_at
  if (!at) return "never used"
  const span = since(at, now)
  if (span === "less than a minute") return "used just now"
  if (span === "1 day") return "used yesterday"
  return `used ${span} ago`
}

/** What a deleted bot user is still on the record for. */
export function stillNamedInWords(taskCount: number): string {
  return taskCount === 0
    ? "still named in the log"
    : `still named on ${taskCount} ${taskCount === 1 ? "task" : "tasks"} and in the log`
}

/** "deleted 12 Sept", or just "deleted" for a record that does not say when. */
export function deletedInWords(at: string | null | undefined): string {
  return at ? `deleted ${inSentence(formatDayOf(at))}` : "deleted"
}

const count = (n: number, one: string, many: string) =>
  `${n} ${n === 1 ? one : many}`

/**
 * The sentence under the heading: how many bot users, how many of them work,
 * and how much they changed this week. `lead` is the part in full ink.
 */
export function counts(
  bots: BotUserPublic[],
  changesThisWeek: number | null,
  now = new Date(),
): { lead: string; rest: string } {
  const states = bots.map((bot) => tokenStatus(bot, now))
  const working = states.filter((state) => state === "active").length
  const without = states.filter(
    (state) => state === "none" || state === "revoked",
  ).length
  const expired = states.filter((state) => state === "expired").length

  const parts = [
    working > 0 && `${working} working`,
    without > 0 && `${without} without a token`,
    expired > 0 && `${expired} with an expired token`,
  ].filter(Boolean)
  const status = parts.length > 0 ? `${parts.join(", ")}.` : ""

  const they = bots.length === 1 ? "It" : "They"
  const changes =
    changesThisWeek === null
      ? ""
      : changesThisWeek === 0
        ? `${they} made no changes this week.`
        : `${they} made ${count(changesThisWeek, "change", "changes")} this week.`

  return {
    lead: `${count(bots.length, "bot user", "bot users")}.`,
    rest: [status, changes].filter(Boolean).join(" "),
  }
}
