import type { QueryClient } from "@tanstack/react-query"

import {
  activityQuery,
  botsQuery,
  deletedBotsQuery,
  scopeProjectsQuery,
  warmQuery,
} from "@/lib/serverState"

/**
 * Every request the Bots page makes, and nothing that draws it. Kept apart
 * from the page so the route can start them as soon as it is matched, while
 * the page's own code is still on its way: the route's loader stays in the
 * first bundle, and it only reaches for this module.
 */

/**
 * The start of the week the sentence counts changes over: today and the six
 * days before it, from midnight. A day's worth of the same answer, so the
 * request keeps one key all day instead of a new one every render.
 */
export function weekStart(now = new Date()): string {
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6)
  return start.toISOString()
}

/** How many changes the bot users made this week, as a count alone. */
export const weekChangesQuery = () =>
  activityQuery({ by_bots: true, since: weekStart(), limit: 1 })

/**
 * Start every request the page will make without waiting on any of them:
 * what is already cached is left alone, so landing here again asks for
 * nothing. A request that fails is the page's to report.
 */
export function prefetchBots(queryClient: QueryClient) {
  void warmQuery(queryClient, botsQuery())
  void warmQuery(queryClient, deletedBotsQuery())
  void warmQuery(queryClient, scopeProjectsQuery())
  void warmQuery(queryClient, weekChangesQuery())
}
