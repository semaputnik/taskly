/**
 * The words at the top of the day page: the date, and the one sentence of
 * what needs the reader and what their bot users did since they last looked.
 *
 * Plain functions, so the wording for zero, one and many, and the rule for
 * when a visit starts, can be read and tested apart from the page.
 */

/** The day of the month large, and the weekday, month and year beside it. */
export function dayHeading(
  date: Date,
  locale?: string,
): { day: string; rest: string } {
  const weekday = date.toLocaleDateString(locale, { weekday: "long" })
  const month = date.toLocaleDateString(locale, {
    month: "long",
    year: "numeric",
  })
  return {
    day: String(date.getDate()).padStart(2, "0"),
    rest: `${weekday}, ${month}`,
  }
}

/**
 * What the bot users' changes are counted from: the reader's last visit, or,
 * on a first visit, everything they have done.
 */
export type ChangesWindow = "visit" | "ever"

const changesNoun = (count: number) => (count === 1 ? "change" : "changes")

/**
 * The sentence, in its two halves: what needs the reader today — what is
 * overdue or due today — set in ink, then the bot users' changes, muted.
 *
 * `changes` is the bot users' count alone: the reader's own changes are not
 * in it. With none, the sentence says so rather than count a zero.
 */
export function lede({
  needYou,
  changes,
  window,
}: {
  needYou: number
  changes: number
  window: ChangesWindow
}): { needs: string; changes: string } {
  const needs =
    needYou === 0
      ? "Nothing needs you today."
      : `${needYou} ${needYou === 1 ? "needs" : "need"} you.`

  if (changes === 0) {
    return { needs, changes: "No bot user has changed anything yet." }
  }
  const counted = `${changes} ${changesNoun(changes)}`
  return {
    needs,
    changes:
      window === "ever"
        ? `Your bot users have made ${counted} so far.`
        : `Your bot users made ${counted} since your last visit.`,
  }
}

/** The two storages a visit is kept in, as the browser offers them. */
export interface VisitStore {
  local: Pick<Storage, "getItem" | "setItem">
  session: Pick<Storage, "getItem" | "setItem">
}

// When the reader last looked at the day page, across sessions.
const LAST_SEEN = "taskly.day.lastSeen"
// What this session counts from, fixed at its first look. Empty for a first
// visit, which has nothing to count from.
const SINCE = "taskly.day.since"

/**
 * When the reader's last visit was, as an ISO timestamp, or null on a first
 * visit.
 *
 * A visit is one browser tab's session: its first look at the day page fixes
 * what it counts from, so reading the page again, or reloading it, does not
 * reset the count to nothing. Every look is remembered, and the next session counts
 * from the latest of them. Kept in the browser, so it is per device; storage
 * that refuses makes every visit a first one rather than breaking the page.
 */
export function visitSince(store: VisitStore, now: Date): string | null {
  try {
    let since = store.session.getItem(SINCE)
    if (since === null) {
      since = store.local.getItem(LAST_SEEN) ?? ""
      store.session.setItem(SINCE, since)
    }
    store.local.setItem(LAST_SEEN, now.toISOString())
    return since || null
  } catch {
    return null
  }
}

/**
 * What `visitSince` will answer, read without writing anything: the page's
 * requests can be started before the page itself fixes the visit, under the
 * same key it will ask with.
 */
export function peekVisitSince(
  store: { [K in keyof VisitStore]: Pick<Storage, "getItem"> },
): string | null {
  try {
    const since =
      store.session.getItem(SINCE) ?? store.local.getItem(LAST_SEEN) ?? ""
    return since || null
  } catch {
    return null
  }
}

/**
 * Remember that the reader is looking at the day page now, without moving
 * what this session counts from. Called as the reader leaves the page, so a
 * tab left open all day still counts the next session from its last look.
 */
export function markSeen(store: VisitStore, now: Date): void {
  try {
    store.local.setItem(LAST_SEEN, now.toISOString())
  } catch {
    // Storage that refuses only costs the next visit its count.
  }
}
