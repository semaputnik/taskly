import { isoDay } from "@/lib/dates"

/**
 * Dates the dashboard asks the API about, and the words it puts on them.
 *
 * Due dates are plain calendar days (`YYYY-MM-DD`) with no timezone of their
 * own, so every comparison here is done in the reader's local calendar
 * (`isoDay`), never in UTC.
 */

function shiftDays(days: number): Date {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return date
}

export const today = () => isoDay(new Date())
export const tomorrow = () => isoDay(shiftDays(1))
export const inAWeek = () => isoDay(shiftDays(7))
