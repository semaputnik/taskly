import { useMutation, useSuspenseQuery } from "@tanstack/react-query"
import { Merge } from "lucide-react"
import { useState } from "react"

import { type TagPublic, TagsService } from "@/client"
import { Button } from "@/components/ui/button"
import { tagDuplicatesQuery, useReportChange } from "@/lib/serverState"
import { toastError } from "@/lib/toasts"
import { taskCountLabel, totalTasks } from "./counts"
import { MergeTags } from "./MergeTags"

/**
 * Tags whose names read as the same word, offered for merging
 * (FR-01.28).
 *
 * A group is only ever a suggestion: merging it goes through the same
 * confirmation as any merge, and "Keep apart" stops offering it until one of
 * its tags is renamed or another spelling joins. The most used spelling is
 * suggested as the one to keep, and the reader picks.
 */
export function DuplicateGroups({
  onOpenTag,
}: {
  onOpenTag: (tagId: string) => void
}) {
  const reportChange = useReportChange()
  const [merging, setMerging] = useState<TagPublic[] | null>(null)

  // Suspends with the tag table, so the two arrive together: suggestions
  // that landed on their own would push the table down after it was drawn.
  const { data } = useSuspenseQuery(tagDuplicatesQuery())

  const dismiss = useMutation({
    mutationFn: (tags: TagPublic[]) =>
      TagsService.dismissTagDuplicates({
        body: { tag_ids: tags.map((tag) => tag.id) },
      }),
    onError: (error) => toastError(error),
    onSettled: () => reportChange({ type: "tag duplicates dismissed" }),
  })

  const groups = data?.data ?? []
  if (groups.length === 0) return null

  return (
    <section
      aria-labelledby="tag-duplicates"
      className="bg-card rounded-[0.875rem] border"
    >
      <h2
        id="tag-duplicates"
        className="bg-muted/50 flex items-baseline gap-2 border-b px-4 py-2 text-xs font-semibold tracking-wide uppercase"
      >
        Likely duplicates
        <span className="text-muted-foreground tabular-nums">
          {groups.length}
        </span>
      </h2>
      <ul className="divide-y">
        {groups.map((group) => {
          const names = group.tags.map((tag) => tag.name).join(", ")
          return (
            <li
              key={group.tags.map((tag) => tag.id).join()}
              aria-label={`Likely duplicates: ${names}`}
              className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3"
            >
              <span className="flex min-w-0 basis-full flex-wrap gap-x-4 gap-y-1 text-sm sm:basis-0 sm:flex-1">
                {group.tags.map((tag) => (
                  <button
                    key={tag.id}
                    type="button"
                    onClick={() => onOpenTag(tag.id)}
                    className="max-w-full truncate text-left whitespace-pre underline-offset-4 hover:underline"
                  >
                    <span className="font-medium">{tag.name}</span>
                    <span className="text-muted-foreground">
                      {" · "}
                      {totalTasks(tag) === 0
                        ? "no tasks"
                        : taskCountLabel(totalTasks(tag))}
                      {tag.created_by_bot_user &&
                        ` · by ${tag.created_by_bot_user.name}`}
                    </span>
                  </button>
                ))}
              </span>
              <span className="flex shrink-0 gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={dismiss.isPending}
                  onClick={() => dismiss.mutate(group.tags)}
                >
                  Keep apart
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setMerging(group.tags)}
                >
                  <Merge />
                  Merge…
                </Button>
              </span>
            </li>
          )
        })}
      </ul>

      {merging && (
        <MergeTags
          onClose={() => setMerging(null)}
          tags={merging}
          initialSurvivorId={
            [...merging].sort((a, b) => totalTasks(b) - totalTasks(a))[0].id
          }
        />
      )}
    </section>
  )
}
