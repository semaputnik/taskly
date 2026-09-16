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
  return new Date(year, month - 1, date).toLocaleDateString(undefined, DAY)
}

/** The local day a timestamp falls on. */
export function formatDate(timestamp: string): string {
  return new Date(timestamp).toLocaleDateString(undefined, DAY)
}

/** A timestamp to the minute. */
export function formatDateTime(timestamp: string): string {
  return new Date(timestamp).toLocaleString(undefined, MOMENT)
}
