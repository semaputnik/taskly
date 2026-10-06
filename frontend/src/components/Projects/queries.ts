import type { QueryClient } from "@tanstack/react-query"

import { botsQuery, projectsQuery, warmQuery } from "@/lib/serverState"

/**
 * Every request the Projects page makes, and nothing that draws it. Kept
 * apart from the page so the route can start them as soon as it is matched,
 * while the page's own code is still on its way.
 */
export function prefetchProjects(queryClient: QueryClient) {
  void warmQuery(queryClient, projectsQuery())
  void warmQuery(queryClient, projectsQuery({ archived: true }))
  void warmQuery(queryClient, botsQuery())
}
