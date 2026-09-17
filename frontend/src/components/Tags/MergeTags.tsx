import { useMutation, useQuery } from "@tanstack/react-query"
import { X } from "lucide-react"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { tagMergePreviewQuery, useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import {
  archivedNote,
  type TaskCounts,
  taskCountLabel,
  taskReach,
  totalTasks,
} from "./counts"

const quoted = (names: string[]) =>
  names.length === 1
    ? `“${names[0]}”`
    : `${names
        .slice(0, -1)
        .map((name) => `“${name}”`)
        .join(", ")} and “${names[names.length - 1]}”`

/** What a merge does to tasks, archived ones included, in one sentence. */
function moves(preview: TaskCounts, survivor: string): string {
  const total = totalTasks(preview)
  if (total === 0) return "No task carries them, so no task changes."
  const [count, where] = taskReach(preview)
  const change = `${count} ${total === 1 ? "changes" : "change"} to carry “${survivor}” instead`
  return where ? `${change}, ${where}.` : `${change}.`
}

/**
 * Merging tags: the reader gathers the tags to put together, picks which name
 * survives, reads exactly what moves and what goes, and confirms (FR-01.27).
 *
 * A merge is the one way to put two spellings of an idea together — renaming
 * into a name in use stays refused — and, like deleting a tag, it cannot be
 * undone. So the confirmation names the surviving tag, every tag that ceases
 * to exist, and how many tasks change, archived ones included, before its
 * button; and it never runs on its own.
 *
 * Mounted for one merge at a time, so it always opens on that merge's own
 * tags and suggestion.
 */
export function MergeTags({
  tags,
  candidates = [],
  initialSurvivorId,
  onClose,
  onMerged,
}: {
  /** The tags it opens with; at least two are needed to merge. */
  tags: TagPublic[]
  /** Other tags the reader may add to the merge. */
  candidates?: TagPublic[]
  initialSurvivorId?: string
  onClose: () => void
  onMerged?: (survivor: TagPublic) => void
}) {
  const [members, setMembers] = useState(tags)
  const [survivorId, setSurvivorId] = useState(initialSurvivorId ?? tags[0]?.id)
  const reportChange = useReportChange()
  const groupName = useId()

  const survivor = members.find((tag) => tag.id === survivorId) ?? members[0]
  const sources = members.filter((tag) => tag.id !== survivor?.id)
  const sourceIds = sources.map((tag) => tag.id)
  const addable = candidates.filter(
    (candidate) => !members.some((member) => member.id === candidate.id),
  )

  const preview = useQuery(tagMergePreviewQuery(survivor?.id, sourceIds))

  const merge = useMutation({
    mutationFn: () =>
      TagsService.mergeTags({
        path: { tag_id: survivor.id },
        body: { source_ids: sourceIds },
      }),
    onSuccess: ({ data }) => {
      toastSuccess(
        `${quoted(sources.map((tag) => tag.name))} merged into “${data.name}”`,
      )
      onClose()
      onMerged?.(data)
    },
    onError: (error) => toastError(error),
    onSettled: () => reportChange({ type: "tag changed" }),
  })

  if (!survivor) return null
  const ready = sources.length > 0 && Boolean(preview.data)

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="break-words">
            {sources.length > 0
              ? `Merge into ${survivor.name}?`
              : `Merge with ${survivor.name}`}
          </DialogTitle>
          <DialogDescription>
            {sources.length === 0
              ? "Add the tags to fold into this one."
              : `${sources.length === 1 ? "The tag" : "The tags"} ${quoted(
                  sources.map((tag) => tag.name),
                )} ${sources.length === 1 ? "is" : "are"} removed. ${
                  preview.data ? `${moves(preview.data, survivor.name)} ` : ""
                }This can't be undone: the activity log records the merge but cannot bring the removed tags back.`}
          </DialogDescription>
        </DialogHeader>

        <fieldset className="flex flex-col gap-1">
          <legend className="mb-2 text-sm font-medium">Keep the name</legend>
          {members.map((tag, index) => (
            <div key={tag.id} className="flex items-center gap-1">
              <label className="hover:bg-accent flex min-h-9 min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-md px-2 text-sm pointer-coarse:min-h-11">
                <input
                  type="radio"
                  name={groupName}
                  value={tag.id}
                  checked={tag.id === survivor.id}
                  onChange={() => setSurvivorId(tag.id)}
                  className="accent-primary size-4"
                />
                <span className="min-w-0 flex-1 truncate font-medium whitespace-pre">
                  {tag.name}
                </span>
                <span className="text-muted-foreground shrink-0 tabular-nums">
                  {taskCountLabel(tag.task_count ?? 0)}
                  {archivedNote(tag) && ` ${archivedNote(tag)}`}
                </span>
              </label>
              {/* The tags it opened with are the point of the merge; only
                  those the reader added can be taken out again. */}
              {index >= tags.length && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Leave ${tag.name} out`}
                  className="pointer-coarse:size-11"
                  onClick={() =>
                    setMembers(members.filter((member) => member.id !== tag.id))
                  }
                >
                  <X />
                </Button>
              )}
            </div>
          ))}
        </fieldset>

        {addable.length > 0 && (
          <Select
            value=""
            onValueChange={(id) => {
              const added = addable.find((candidate) => candidate.id === id)
              if (added) setMembers([...members, added])
            }}
          >
            <SelectTrigger aria-label="Add a tag to merge" className="w-full">
              <SelectValue placeholder="Add a tag to merge…" />
            </SelectTrigger>
            <SelectContent>
              {addable.map((candidate) => (
                <SelectItem key={candidate.id} value={candidate.id}>
                  <span className="whitespace-pre">{candidate.name}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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
            disabled={!ready}
            onClick={() => merge.mutate()}
          >
            Merge into {survivor.name}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
