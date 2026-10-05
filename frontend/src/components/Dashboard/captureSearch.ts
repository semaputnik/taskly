/**
 * The capture line's search, apart from the line: what it looks for, which
 * matches are on show while an answer is awaited, how a title is marked, how
 * the arrow keys move, and which way the matches open (FR-06.14, FR-06.15).
 * Kept apart from the component so each rule can be tested without a renderer.
 */

/** The fewest characters the line searches on: one letter matches too much. */
export const MIN_TERM = 2

/** The most matches offered; the line is for finding a task, not for a list. */
export const MAX_MATCHES = 8

/**
 * What the line searches for, or null while there is nothing to search on.
 * The spaces around the text are not part of a title, so they are not
 * searched; the ones inside it are.
 */
export function searchTerm(typed: string): string | null {
  const term = typed.trim()
  return term.length >= MIN_TERM ? term : null
}

/** The tasks that answered a search, and the text it was for. */
export interface Answer<T> {
  text: string
  tasks: T[]
}

/**
 * The matches to show for what is typed now, given the latest answer, which
 * may be to older text (a newer one is on its way).
 *
 * An answer to the text typed is shown as it came. An answer to older text is
 * shown only as far as it still holds: the tasks whose title contains the
 * text typed since. Nothing the reader has moved past is ever shown, and the
 * list does not blank between keystrokes. `current` says which of the two it
 * is, so "no matches" is only ever said of a finished search.
 */
export function matchesFor<T extends { title: string }>(
  typed: string,
  answer: Answer<T> | undefined,
): { tasks: T[]; current: boolean } {
  const term = searchTerm(typed)
  if (term === null || !answer) return { tasks: [], current: false }
  if (answer.text === term) return { tasks: answer.tasks, current: true }
  const wanted = term.toLowerCase()
  return {
    tasks: answer.tasks.filter((task) =>
      task.title.toLowerCase().includes(wanted),
    ),
    current: false,
  }
}

/** A stretch of a title, and whether it is the text that was searched for. */
export interface TitlePart {
  text: string
  match: boolean
}

/**
 * A title cut around every place the text occurs, whatever its case, so the
 * matched stretches can be set in bold. The text is read as letters, never as
 * a pattern: "50% (" finds exactly that.
 */
export function titleParts(title: string, term: string): TitlePart[] {
  const parts: TitlePart[] = []
  const haystack = title.toLowerCase()
  const needle = term.toLowerCase()
  // Case-folding can change a string's length in a few scripts; the parts
  // would then be cut in the wrong place, so such a title is left unmarked.
  if (!needle || haystack.length !== title.length) {
    return [{ text: title, match: false }]
  }
  let from = 0
  for (;;) {
    const at = haystack.indexOf(needle, from)
    if (at < 0) break
    if (at > from) parts.push({ text: title.slice(from, at), match: false })
    parts.push({ text: title.slice(at, at + needle.length), match: true })
    from = at + needle.length
  }
  if (from < title.length) {
    parts.push({ text: title.slice(from), match: false })
  }
  return parts.length ? parts : [{ text: title, match: false }]
}

/**
 * Where the arrow keys put the highlight: -1 is the line itself (Enter
 * creates), 0 and up are the matches. Down walks the list in the order it is
 * drawn and Up walks it back; either passes through the line, so there is
 * always one key that returns to creating.
 */
export function stepActive(
  active: number,
  count: number,
  key: "ArrowDown" | "ArrowUp",
): number {
  if (count === 0) return -1
  const at = active >= count ? -1 : active
  if (key === "ArrowDown") return at + 1 >= count ? -1 : at + 1
  return at === -1 ? count - 1 : at - 1
}

/**
 * Whether the matches open above the line rather than below it: when the
 * line sits low, as it does pinned above a phone's browser bar, and there is
 * more room above it. Measured where the line is, so a line anywhere on the
 * screen opens toward the room it has.
 */
export function opensUpward(
  line: { top: number; bottom: number },
  viewportHeight: number,
  needed: number,
): boolean {
  const below = viewportHeight - line.bottom
  const above = line.top
  if (below >= needed) return false
  return above > below
}
