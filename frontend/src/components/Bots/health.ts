/**
 * How long ago, and how long until, in a person's words.
 *
 * A bot user's page used to hand over timestamps and leave the reading to
 * whoever was looking: "last used 2026-09-14, 04:11" answers a question
 * nobody asked. What an operator wants to know is whether the integration
 * works and when it was last heard from, so that is what these say.
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
