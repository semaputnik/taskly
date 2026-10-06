import type { QueryClient } from "@tanstack/react-query"
import { z } from "zod"

import type { ActivityKind } from "@/client"
import {
  activityQuery,
  botsQuery,
  deletedBotsQuery,
  warmQuery,
} from "@/lib/serverState"
import { KINDS, ME, ORDERS, PAGE_SIZE } from "./words"

/**
 * Every request the Activity page makes, and nothing that draws it. Kept
 * apart from the page so the route can start them as soon as it is matched,
 * while the page's own code is still on its way: the route's loader stays in
 * the first bundle, and it only reaches for this module.
 */

/**
 * What the address can say about the log: the page, one kind of change, one
 * actor — the reader (`me`) or a bot user's id, which is what a bot user's
 * column hands off with — and the order. Each narrowing lives in the URL, so a
 * view can be linked to and survives a reload (FR-10.8, FR-10.10).
 */
export const activitySearchSchema = z.object({
  page: z.number().int().min(1).optional().catch(undefined),
  actor: z
    .union([z.literal(ME), z.string().uuid()])
    .optional()
    .catch(undefined),
  // Not a sort and not a page: which of its questions the log is answering.
  kind: z.enum(KINDS).optional().catch(undefined),
  order: z.enum(ORDERS).optional().catch(undefined),
})

export type ActivitySearch = z.infer<typeof activitySearchSchema>

/** What the address asks the API for. */
export function logRequest(search: ActivitySearch) {
  const { page = 1, actor, kind, order } = search
  return {
    skip: (page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    kind: kind as ActivityKind | undefined,
    actor_bot_user_id: actor && actor !== ME ? actor : undefined,
    by_user: actor === ME ? true : undefined,
    // Newest is the API's own order, so it is not asked for: one key for one
    // answer.
    order: order === "oldest" ? ("oldest" as const) : undefined,
  }
}

/** The sentence's two counts, of the whole log: asked for as counts alone. */
export const everythingQuery = () => activityQuery({ limit: 1 })
export const byBotsQuery = () => activityQuery({ by_bots: true, limit: 1 })

/**
 * Start every request the page will make without waiting on any of them:
 * what is already cached is left alone, so landing here again asks for
 * nothing. A request that fails is the page's to report.
 */
export function prefetchActivity(
  queryClient: QueryClient,
  search: ActivitySearch,
) {
  void warmQuery(queryClient, activityQuery(logRequest(search)))
  void warmQuery(queryClient, everythingQuery())
  void warmQuery(queryClient, byBotsQuery())
  void warmQuery(queryClient, botsQuery())
  void warmQuery(queryClient, deletedBotsQuery())
}
