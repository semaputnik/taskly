import { activityQuery } from "@/lib/serverState"

/**
 * What the day page's sections share: their preview lengths, the text link
 * they end with, and the Changes log's request, which the sentence under the
 * date reads its total from. Kept apart from the sections so none of them
 * imports another.
 */

/** How many rows a band shows before it hands off to the task list. */
export const PREVIEW_ROWS = 5

/** How many lines the day page's Changes log shows before the full log. */
export const LOG_LINES = 8

/** The account's changes in the window the page counts from, newest first. */
export const changesQuery = (since: string | null) =>
  activityQuery({ since: since ?? undefined, limit: LOG_LINES })

/** A text action: underlined on hover, ringed on keyboard focus. */
export const textLink =
  "focus-visible:ring-ring/50 rounded-sm underline-offset-[3px] outline-none hover:underline focus-visible:ring-[3px]"

/** A line's count as a link: quiet at rest, tinted under the pointer. */
export const countLink =
  "focus-visible:ring-ring/50 hover:bg-rule -my-1 -mr-2 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[13.5px] font-medium whitespace-nowrap outline-none focus-visible:ring-[3px] pointer-coarse:-my-3 pointer-coarse:py-3"
