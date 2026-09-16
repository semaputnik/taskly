import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useId, useState } from "react"

import { type TagPublic, TagsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { tasks } from "./counts"

const quoted = (names: string[]) =>
  names.length === 1
    ? `“${names[0]}”`
    : `${names
        .slice(0, -1)
        .map((name) => `“${name}”`)
        .join(", ")} and “${names[names.length - 1]}”`

/** What a merge does to tasks, archived ones included, in one sentence. */
function moves(
  preview: { task_count: number; archived_task_count: number },
  survivor: string,
): string {
  const total = preview.task_count + preview.archived_task_count
  if (total === 0) return "No task carries them, so no task changes."
  const change = `${tasks(total)} ${total === 1 ? "changes" : "change"} to carry “${survivor}” instead`
  const archived = preview.archived_task_count
  if (archived === 0) return `${change}.`
  if (total === 1) return `${change}; it is in an archived project.`
  return `${change}, ${archived} of them in ${archived === 1 ? "an archived project" : "archived projects"}.`
}

/**
 * Merging tags: the reader picks which name survives, reads exactly what moves
 * and what goes, and confirms (semaputnik/taskly#69).
 *
 * A merge is the one way to put two spellings of an idea together — renaming
 * into a name in use stays refused — and, like deleting a tag, it cannot be
 * undone. So the confirmation names the surviving tag, every tag that ceases
 * to exist, and how many tasks change, archived ones included, before its
 * button; and it never runs on its own.
 */
export function MergeTags({
  open,
  onOpenChange,
  tags,
  initialSurvivorId,
  onMerged,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** The tags being put together, at least two. */
  tags: TagPublic[]
  initialSurvivorId?: string
  onMerged?: (survivor: TagPublic) => void
}) {
  // Mounted afresh for each merge, so the suggestion it opens with is
  // always that merge's own.
  const [survivorId, setSurvivorId] = useState(initialSurvivorId ?? tags[0]?.id)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const groupName = useId()

  const survivor = tags.find((tag) => tag.id === survivorId) ?? tags[0]
  const sources = tags.filter((tag) => tag.id !== survivor?.id)
  const sourceIds = sources.map((tag) => tag.id)

  const preview = useQuery({
    queryKey: ["tag-merge-preview", survivor?.id, sourceIds],
    queryFn: async () =>
      (
        await TagsService.previewTagMerge({
          path: { tag_id: survivor.id },
          query: { source_ids: sourceIds },
        })
      ).data,
    enabled: open && Boolean(survivor) && sourceIds.length > 0,
  })

  const merge = useMutation({
    mutationFn: () =>
      TagsService.mergeTags({
        path: { tag_id: survivor.id },
        body: { source_ids: sourceIds },
      }),
    onSuccess: ({ data }) => {
      showSuccessToast(
        `${quoted(sources.map((tag) => tag.name))} merged into “${data.name}”`,
      )
      onOpenChange(false)
      onMerged?.(data)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] })
      queryClient.invalidateQueries({ queryKey: ["tag"] })
      queryClient.invalidateQueries({ queryKey: ["tag-duplicates"] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      queryClient.invalidateQueries({ queryKey: ["task"] })
    },
  })

  if (!survivor) return null

  const names = quoted(sources.map((tag) => tag.name))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="break-words">
            Merge into {survivor.name}?
          </DialogTitle>
          <DialogDescription>
            {sources.length === 1 ? "The tag " : "The tags "}
            {names} {sources.length === 1 ? "is" : "are"} removed.{" "}
            {preview.data && moves(preview.data, survivor.name)} This can't be
            undone: the activity log records the merge but cannot bring the
            removed tags back.
          </DialogDescription>
        </DialogHeader>

        {tags.length > 1 && (
          <fieldset className="flex flex-col gap-1">
            <legend className="mb-2 text-sm font-medium">Keep the name</legend>
            {tags.map((tag) => (
              <label
                key={tag.id}
                className="hover:bg-accent flex min-h-9 cursor-pointer items-center gap-3 rounded-md px-2 text-sm pointer-coarse:min-h-11"
              >
                <input
                  type="radio"
                  name={groupName}
                  value={tag.id}
                  checked={tag.id === survivor.id}
                  onChange={() => setSurvivorId(tag.id)}
                  className="accent-primary size-4"
                />
                <span className="min-w-0 flex-1 truncate font-medium">
                  {tag.name}
                </span>
                <span className="text-muted-foreground shrink-0 tabular-nums">
                  {tasks(tag.task_count ?? 0)}
                  {(tag.archived_task_count ?? 0) > 0 &&
                    ` + ${tag.archived_task_count} archived`}
                </span>
              </label>
            ))}
          </fieldset>
        )}

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={merge.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            loading={merge.isPending}
            disabled={!preview.data}
            onClick={() => merge.mutate()}
          >
            Merge into {survivor.name}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
