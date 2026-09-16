/**
 * The product's one way of writing a date, so the same fact reads the same
 * wherever it appears.
 *
 * A day is written the way the browser's own date field writes it — numeric,
 * in the reader's locale — because the panel edits due dates in that field and
 * the table beside it has to agree with it. A moment adds the time to the
 * minute; seconds are noise on a record's history.
 */

const DAY: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}

const MOMENT: Intl.DateTimeFormatOptions = {
  ...DAY,
  hour: "2-digit",
  minute: "2-digit",
}

/**
 * A calendar day as the API sends it (`YYYY-MM-DD`). Read as a local date:
 * parsed as UTC it would show the day before for anyone west of Greenwich.
 */
export function formatDay(day: string): string {
  const [year, month, date] = day.split("-").map(Number)
  const local = new Date(year, month - 1, date)
  // Something that is not a day is shown as it came rather than as
  // "Invalid Date".
  return Number.isNaN(local.getTime())
    ? day
    : local.toLocaleDateString(undefined, DAY)
}

/** The local day a timestamp falls on. */
export function formatDayOf(timestamp: string): string {
  return new Date(timestamp).toLocaleDateString(undefined, DAY)
}

/** A timestamp to the minute. */
export function formatDateTime(timestamp: string): string {
  return new Date(timestamp).toLocaleString(undefined, MOMENT)
}

/**
 * A local date as the API and date fields write a day (`YYYY-MM-DD`). Built
 * from local parts: `toISOString()` would shift the day for anyone west of
 * UTC after their afternoon.
 */
export function isoDay(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}
