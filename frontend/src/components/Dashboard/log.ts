/**
 * The words on the day page's Changes log: what window the heading says it
 * covers, the time in each line's narrow column, and the days the lines fall
 * into once the log reaches back past today.
 *
 * Plain functions, so the wording can be read and tested apart from the page.
 * Everything is in the reader's local calendar.
 */

const DAY_MS = 86_400_000

/** How many calendar days before `now` the date falls: 0 today, 1 yesterday. */
function daysBefore(date: Date, now: Date): number {
  const start = (d: Date) =>
    new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  // Rounded: a day across a clock change is an hour short or long.
  return Math.round((start(now) - start(date)) / DAY_MS)
}

/** The time to the minute, as the reader's locale writes it. */
export function clock(date: Date, locale?: string): string {
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" })
}

/**
 * A past day as a reader says it: yesterday, a weekday within the week, a
 * date beyond — with the year only when it is not this one. Null for today,
 * which needs no name.
 */
function dayName(date: Date, now: Date, locale?: string): string | null {
  const days = daysBefore(date, now)
  if (days <= 0) return null
  if (days === 1) return "yesterday"
  if (days < 7) return date.toLocaleDateString(locale, { weekday: "long" })
  return date.toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
    ...(date.getFullYear() !== now.getFullYear() && { year: "numeric" }),
  })
}

/**
 * What the heading says the log covers: since the reader's last visit, by
 * the time it was and the day if not today ("since yesterday 17:00"), or,
 * on a first visit, everything so far. A visit before this week is named by
 * its day alone; its time no longer helps.
 */
export function windowLabel(
  since: Date | null,
  now: Date,
  locale?: string,
): string {
  if (since === null) return "so far"
  const day = dayName(since, now, locale)
  if (day === null) return `since ${clock(since, locale)}`
  if (daysBefore(since, now) >= 7) return `since ${day}`
  return `since ${day} ${clock(since, locale)}`
}

/** The lines written on one day, with the day's name, or null for today. */
export interface Day<T> {
  label: string | null
  entries: T[]
}

/**
 * The lines split by the day they were written, in the order given (newest
 * first). Today's lines carry no label: the page is today. Every earlier day
 * is named, so a time in the narrow column is never read as today's.
 */
export function byDay<T extends { created_at?: string | null }>(
  entries: T[],
  now: Date,
  locale?: string,
): Day<T>[] {
  const days: (Day<T> & { key: number })[] = []
  for (const entry of entries) {
    const date = entry.created_at ? new Date(entry.created_at) : now
    const key = daysBefore(date, now)
    const last = days[days.length - 1]
    if (last?.key === key) {
      last.entries.push(entry)
      continue
    }
    const name = dayName(date, now, locale)
    days.push({
      key,
      label: name && name.charAt(0).toUpperCase() + name.slice(1),
      entries: [entry],
    })
  }
  return days.map(({ label, entries }) => ({ label, entries }))
}
