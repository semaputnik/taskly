import type { BotUserPublic } from "@/client"
import { isoDay } from "@/lib/dates"

export type TokenStatus = "none" | "revoked" | "expired" | "active"

/** Where a bot user's token stands, as the Bots page tells it. */
export function tokenStatus(bot: BotUserPublic, now = new Date()): TokenStatus {
  if (!bot.has_token) {
    return bot.token_revoked_at ? "revoked" : "none"
  }
  if (bot.token_expires_at && new Date(bot.token_expires_at) <= now) {
    return "expired"
  }
  return "active"
}

/**
 * The moment a token picked to expire on `date` (a `yyyy-mm-dd` from a date
 * input) stops working: the end of that day where the user is, so the day
 * they chose is still a working one.
 */
export function expiryFromDate(date: string | undefined): string | undefined {
  if (!date) return undefined
  return new Date(`${date}T23:59:59.999`).toISOString()
}

/** Today as a date input's `min`: a token cannot be issued already expired. */
export function today(): string {
  return isoDay(new Date())
}
