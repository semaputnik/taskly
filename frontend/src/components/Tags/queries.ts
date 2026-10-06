import type { QueryClient } from "@tanstack/react-query"

import {
  tagDuplicatesQuery,
  tagVocabularyQuery,
  warmQuery,
} from "@/lib/serverState"

/**
 * Every request the Tags page makes, and nothing that draws it. Kept apart
 * from the page so the route can start them as soon as it is matched, while
 * the page's own code is still on its way.
 */
export function prefetchTags(queryClient: QueryClient) {
  void warmQuery(queryClient, tagVocabularyQuery())
  void warmQuery(queryClient, tagDuplicatesQuery())
}
