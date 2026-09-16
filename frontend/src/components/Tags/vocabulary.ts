import { useQuery } from "@tanstack/react-query"

import { type TagPublic, TagsService } from "@/client"

const PAGE = 500

/**
 * Every tag the user has, however many: what picking a tag to merge with
 * offers, so no spelling is out of reach for sitting past the first page.
 */
export function useVocabulary() {
  return useQuery({
    queryKey: ["tags", "vocabulary"],
    queryFn: async () => {
      const tags: TagPublic[] = []
      for (let skip = 0; ; skip += PAGE) {
        const page = (
          await TagsService.readTags({ query: { skip, limit: PAGE } })
        ).data
        tags.push(...page.data)
        if (page.data.length < PAGE || tags.length >= page.count) return tags
      }
    },
  })
}
