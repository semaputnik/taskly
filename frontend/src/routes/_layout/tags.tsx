import { useSuspenseQueries } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { ListHeading } from "@/components/Common/ListHeading"
import { textLink } from "@/components/Dashboard/shared"
import { useRecordPanels } from "@/components/Records/panels"
import { useRecordList } from "@/components/Records/walk"
import { LookAlike } from "@/components/Tags/LookAlike"
import { prefetchTags } from "@/components/Tags/queries"
import { TagLine, TagLinePending } from "@/components/Tags/TagLine"
import { counts } from "@/components/Tags/words"
import { Skeleton } from "@/components/ui/skeleton"
import { tagDuplicatesQuery, tagVocabularyQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout/tags")({
  component: Tags,
  // The requests start as soon as the route is matched, beside the download
  // of the page's own code rather than after it.
  loader: ({ context }) => {
    prefetchTags(context.queryClient)
  },
  head: () => ({
    meta: [
      {
        title: "Tags - Taskly",
      },
    ],
  }),
})

/**
 * The sentence of counts, the groups that look alike and every tag as a line.
 * Both requests are read together, so the page is drawn once they have come:
 * suggestions that landed on their own would push the lines down after they
 * were drawn.
 */
function TagLines() {
  const [{ data: tags }, { data: duplicates }] = useSuspenseQueries({
    queries: [tagVocabularyQuery(), tagDuplicatesQuery()],
  })
  // The column walks the lines in the order they are drawn in.
  useRecordList(
    0,
    tags.map((tag) => tag.id),
  )

  const groups = duplicates.data.map((group) => group.tags)
  const alike = groups.reduce((sum, group) => sum + group.length, 0)
  const { lead, rest } = counts(tags.length, alike)

  return (
    <>
      <p className="text-ink-3 mb-6">
        <span className="text-ink font-medium">{lead}</span> {rest}
      </p>

      <LookAlike groups={groups} />

      {tags.length > 0 && (
        <section aria-label="Tags">
          <ListHeading count={tags.length}>Tags</ListHeading>
          <ul aria-label="All tags">
            {tags.map((tag) => (
              <TagLine key={tag.id} tag={tag} />
            ))}
          </ul>
        </section>
      )}
    </>
  )
}

/** The sentence and the lines while they are on their way. */
function TagLinesPending() {
  return (
    <div aria-hidden>
      <div className="mb-6 flex h-[1.45em] items-center">
        <Skeleton className="h-4 w-72 max-w-full" />
      </div>
      {Array.from({ length: 5 }).map((_, index) => (
        <TagLinePending key={index} />
      ))}
    </div>
  )
}

/**
 * The user's tags, and the only place they are renamed, merged or deleted
 * (FR-01.26). Creating one also happens by typing it onto a task.
 */
function Tags() {
  const { capture } = useRecordPanels()

  return (
    <div className="page-column">
      <div className="mb-1 flex items-baseline gap-4">
        <h1 className="text-[22px] leading-[1.2] font-semibold tracking-[-0.015em]">
          Tags
        </h1>
        <button
          type="button"
          onClick={() => capture("tag")}
          className={cn(
            textLink,
            "text-ink-2 hover:text-ink ml-auto text-[13.5px] font-medium pointer-coarse:-my-3 pointer-coarse:py-3",
          )}
        >
          <span aria-hidden>+ </span>New tag
        </button>
      </div>
      <Suspense fallback={<TagLinesPending />}>
        <TagLines />
      </Suspense>
    </div>
  )
}
