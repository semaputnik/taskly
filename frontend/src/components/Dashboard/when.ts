import { formatDate } from "@/lib/dates"

/**
 * Dates the dashboard asks the API about, and the words it puts on them.
 *
 * Due dates are plain calendar days (`YYYY-MM-DD`) with no timezone of their
 * own, so every comparison here is done in the reader's local calendar. Using
 * `toISOString()` would shift the day for anyone west of UTC after their
 * afternoon, quietly filing today's work under tomorrow.
 */

function isoDay(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function shiftDays(days: number): Date {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return date
}

export const today = () => isoDay(new Date())
export const tomorrow = () => isoDay(shiftDays(1))
export const inAWeek = () => isoDay(shiftDays(7))

/** "3 days ago" for an overdue date, in whole days. */
export function daysLate(dueDate: string): string {
  const due = new Date(`${dueDate}T00:00:00`)
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  const days = Math.round((start.getTime() - due.getTime()) / 86_400_000)
  if (days <= 0) return "due today"
  if (days === 1) return "1 day late"
  return `${days} days late`
}

/** "4h ago" for an activity timestamp, shrinking to a date after a week. */
export function timeAgo(timestamp: string): string {
  const then = new Date(timestamp)
  const minutes = Math.round((Date.now() - then.getTime()) / 60_000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return formatDate(timestamp)
}

/** The half of the day the reader is in, for the greeting. */
export function partOfDay(): "morning" | "afternoon" | "evening" {
  const hour = new Date().getHours()
  if (hour < 12) return "morning"
  if (hour < 18) return "afternoon"
  return "evening"
}
