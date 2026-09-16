import type { BotUserPublic } from "@/client"
import { tokenStatus } from "./tokens"

/**
 * A bot user's health in an operator's words.
 *
 * The table used to hand over timestamps and leave the reading to whoever was
 * looking: "last used 2026-09-14, 04:11" answers a question nobody asked. What
 * an operator wants to know is whether the integration works, and whether it
 * has gone quiet — so that is what these say.
 */

const MINUTE = 60 * 1000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/** How long has passed, as a span: "9 days", "2 hours". */
export function since(
  value: string | null | undefined,
  now = Date.now(),
): string {
  if (!value) return ""
  const elapsed = now - new Date(value).getTime()
  if (elapsed < MINUTE) return "less than a minute"
  if (elapsed < HOUR) {
    const minutes = Math.floor(elapsed / MINUTE)
    return `${minutes} ${minutes === 1 ? "minute" : "minutes"}`
  }
  if (elapsed < DAY) {
    const hours = Math.floor(elapsed / HOUR)
    return `${hours} ${hours === 1 ? "hour" : "hours"}`
  }
  const days = Math.floor(elapsed / DAY)
  if (days < 30) return `${days} ${days === 1 ? "day" : "days"}`
  const months = Math.floor(days / 30)
  return `${months} ${months === 1 ? "month" : "months"}`
}

/** How long ago, in the words a person would use. */
export function ago(
  value: string | null | undefined,
  now = Date.now(),
): string {
  if (!value) return ""
  if (now - new Date(value).getTime() < MINUTE) return "just now"
  return `${since(value, now)} ago`
}

/** In how long, for a moment that has not arrived yet. */
export function until(
  value: string | null | undefined,
  now = Date.now(),
): string {
  if (!value) return ""
  const remaining = new Date(value).getTime() - now
  if (remaining <= 0) return "already"
  const days = Math.floor(remaining / DAY)
  if (days >= 1) return `in ${days} ${days === 1 ? "day" : "days"}`
  const hours = Math.max(1, Math.floor(remaining / HOUR))
  return `in ${hours} ${hours === 1 ? "hour" : "hours"}`
}

/**
 * A bot user that has not been heard from in a week. Not an error and not a
 * colour: a fact worth seeing in a list of agents, said in words.
 */
export const DORMANT_AFTER = 7 * DAY

export type Liveness = "never" | "working" | "dormant" | "stopped"

export function liveness(bot: BotUserPublic, now = Date.now()): Liveness {
  if (tokenStatus(bot, new Date(now)) !== "active") return "stopped"
  if (!bot.token_last_used_at) return "never"
  return now - new Date(bot.token_last_used_at).getTime() > DORMANT_AFTER
    ? "dormant"
    : "working"
}

const STOPPED_BECAUSE = {
  none: "no token",
  revoked: "token revoked",
  expired: "token expired",
  active: "",
} as const

/**
 * The one line a list can afford about how a bot user is getting on.
 *
 * It always answers the column it sits under — when the integration was last
 * heard from — and only then says why it is not being heard from now. A
 * credential that stopped working does not erase the fact that it worked
 * yesterday (FR-08.17).
 */
export function livenessText(bot: BotUserPublic, now = Date.now()): string {
  const state = liveness(bot, now)
  if (state === "working") return `Used ${ago(bot.token_last_used_at, now)}`
  if (state === "dormant") {
    return `Silent for ${since(bot.token_last_used_at, now)}`
  }
  if (state === "never") return "Never used"

  const why = STOPPED_BECAUSE[tokenStatus(bot, new Date(now))]
  return bot.token_last_used_at
    ? `Used ${ago(bot.token_last_used_at, now)} · ${why}`
    : `Never used · ${why}`
}
