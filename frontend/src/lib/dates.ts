/**
 * The product's one way of writing a date, so the same fact reads the same
 * wherever it appears.
 *
 * A day is said in words: "Today", "Tomorrow" and "Yesterday" while those are
 * what the reader would say, then the day and a short month, "24 Sept", with
 * the year only when it is not this one, "24 Sept 2025". The reader's locale
 * orders the parts ("Sep 24" for en-US), so nobody has to decide whether
 * 03/02 is March or February. A moment adds the time to the minute; seconds
 * are noise on a record's history.
 */

const DAY_MS = 86_400_000

/** Whole calendar days from `from` to `to`, whatever the hour or a clock change. */
function daysBetween(from: Date, to: Date): number {
  const start = Date.UTC(from.getFullYear(), from.getMonth(), from.getDate())
  const end = Date.UTC(to.getFullYear(), to.getMonth(), to.getDate())
  return Math.round((end - start) / DAY_MS)
}

/**
 * A date written out plainly: "24 Sept", or "24 Sept 2025" when its year is
 * not `now`'s. No "Today" here, for a line that must say the date itself.
 */
export function dateInWords(
  date: Date,
  now: Date = new Date(),
  locale?: string,
): string {
  // `format` throws on an invalid date, where the old text said so.
  if (Number.isNaN(date.getTime())) return ""
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    ...(date.getFullYear() !== now.getFullYear() && { year: "numeric" }),
  }).format(date)
}

/** A date as a reader says it: "Today", "Tomorrow", "Yesterday", else the date. */
function inWords(date: Date, now: Date, locale?: string): string {
  const days = daysBetween(now, date)
  if (days === 0) return "Today"
  if (days === 1) return "Tomorrow"
  if (days === -1) return "Yesterday"
  return dateInWords(date, now, locale)
}

/**
 * A calendar day as the API sends it (`YYYY-MM-DD`). Read as a local date:
 * parsed as UTC it would show the day before for anyone west of Greenwich.
 */
export function formatDay(
  day: string,
  now: Date = new Date(),
  locale?: string,
): string {
  const [year, month, date] = day.split("-").map(Number)
  const local = new Date(year, month - 1, date)
  // Something that is not a day is shown as it came rather than as
  // "Invalid Date".
  return Number.isNaN(local.getTime()) ? day : inWords(local, now, locale)
}

/** A stored day as the date alone, for a range's ends, where "Today" would not read. */
export function formatDayPlain(
  day: string,
  now: Date = new Date(),
  locale?: string,
): string {
  const [year, month, date] = day.split("-").map(Number)
  const local = new Date(year, month - 1, date)
  return Number.isNaN(local.getTime()) ? day : dateInWords(local, now, locale)
}

/**
 * A day or moment that sits in the middle of a sentence ("created today",
 * "expires tomorrow, 10:00"): its leading "Today", "Tomorrow" or "Yesterday"
 * in lower case, as a sentence has it. A date is left as it is.
 */
export function inSentence(text: string): string {
  return text.replace(/^(Today|Tomorrow|Yesterday)\b/, (word) =>
    word.toLowerCase(),
  )
}

/** The local day a timestamp falls on. */
export function formatDayOf(
  timestamp: string,
  now: Date = new Date(),
  locale?: string,
): string {
  const at = new Date(timestamp)
  // Not a moment: shown as it came, as `formatDay` does.
  return Number.isNaN(at.getTime()) ? timestamp : inWords(at, now, locale)
}

/** A timestamp to the minute: its day in words, then the time. */
export function formatDateTime(
  timestamp: string,
  now: Date = new Date(),
  locale?: string,
): string {
  if (Number.isNaN(new Date(timestamp).getTime())) return timestamp
  const time = new Date(timestamp).toLocaleTimeString(locale, {
    hour: "2-digit",
    minute: "2-digit",
  })
  return `${formatDayOf(timestamp, now, locale)}, ${time}`
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

/** The time of day of a timestamp, to the minute, as a history column shows it. */
export function formatTimeOf(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  })
}

/**
 * A day as a history separator names it: "Today" and "Yesterday" while those
 * are what the reader would say, the date in words after that.
 */
export function dayHeading(timestamp: string, now: Date = new Date()): string {
  return formatDayOf(timestamp, now)
}
