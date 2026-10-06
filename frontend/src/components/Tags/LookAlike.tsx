import { useMutation } from "@tanstack/react-query"
import { useState } from "react"

import { type TagPublic, TagsService } from "@/client"
import { ListHeading } from "@/components/Common/ListHeading"
import { textLink } from "@/components/Dashboard/shared"
import { useReportChange } from "@/lib/serverState"
import { toastError } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import { MergeTags } from "./MergeTags"
import { groupCounts, nameList, suggestedSurvivor } from "./words"

const act = cn(
  textLink,
  "text-[13.5px] font-medium disabled:opacity-50 pointer-coarse:-my-3 pointer-coarse:py-3",
)

/**
 * Tags whose names read as the same word, one line to a group, at the top of
 * the Tags page (FR-01.28).
 *
 * A group is only ever a suggestion: "Merge into" opens the same confirmation
 * as any merge, with the most used spelling suggested and the reader free to
 * pick another; "Keep apart" stops offering the group until one of its tags is
 * renamed or another spelling joins it.
 */
export function LookAlike({ groups }: { groups: TagPublic[][] }) {
  const reportChange = useReportChange()
  const [merging, setMerging] = useState<TagPublic[] | null>(null)

  const dismiss = useMutation({
    mutationFn: (tags: TagPublic[]) =>
      TagsService.dismissTagDuplicates({
        body: { tag_ids: tags.map((tag) => tag.id) },
      }),
    onError: (error) => toastError(error),
    onSettled: () => reportChange({ type: "tag duplicates dismissed" }),
  })

  if (groups.length === 0) return null

  return (
    <section aria-label="Look alike" className="mb-7">
      <ListHeading count={groups.length}>Look alike</ListHeading>
      <ul>
        {groups.map((tags) => {
          const names = tags.map((tag) => tag.name)
          const survivor = suggestedSurvivor(tags)
          return (
            <li
              key={tags.map((tag) => tag.id).join()}
              aria-label={`Look alike: ${names.join(", ")}`}
              className="border-rule flex flex-wrap items-baseline gap-x-3.5 gap-y-1 border-b py-2.5 text-sm last:border-b-0"
            >
              <span className="font-medium whitespace-pre-wrap">
                {nameList(names)}
              </span>
              <span className="text-ink-3 text-[13px]">
                {groupCounts(tags)}
              </span>
              <span className="ml-auto flex gap-3.5">
                <button
                  type="button"
                  onClick={() => setMerging(tags)}
                  className={cn(act, "text-ink")}
                >
                  Merge into {survivor.name}
                </button>
                <button
                  type="button"
                  disabled={dismiss.isPending}
                  onClick={() => dismiss.mutate(tags)}
                  className={cn(act, "text-ink-3 font-normal")}
                >
                  Keep apart
                </button>
              </span>
            </li>
          )
        })}
      </ul>

      {merging && (
        <MergeTags
          onClose={() => setMerging(null)}
          tags={merging}
          initialSurvivorId={suggestedSurvivor(merging).id}
        />
      )}
    </section>
  )
}
