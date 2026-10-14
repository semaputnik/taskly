import { useMutation } from "@tanstack/react-query"
import { useState } from "react"

import { type ActivityEntryPublic, ActivityService } from "@/client"
import { textLink } from "@/components/Dashboard/shared"
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
import { useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import { cn } from "@/lib/utils"

interface RestoreDeletionProps {
  entry: ActivityEntryPublic
}

function plural(count: number, one: string, many: string): string {
  return count === 1 ? one : `${count} ${many}`
}

/**
 * What the confirmation says comes back, for a task or a project.
 *
 * `RestoreDeletion` only ever renders over a deletion entry (`task_deleted`
 * or `project_deleted`), so this switches on `details.kind` rather than
 * `entry.entity_type`: the discriminated union itself (#299's spike) is what
 * tells a single task's own deletion from a batch's apart, by which of the
 * two shapes `task_deleted` carries — never by reading for a `title` that
 * may or may not be there.
 */
function describe(entry: ActivityEntryPublic) {
  const { details } = entry
  switch (details.kind) {
    case "project_deleted": {
      const tasks = details.task_count
      return {
        heading: "Restore project",
        name: details.name ?? "this project",
        comesBack:
          tasks > 0
            ? `, with ${plural(tasks, "the task", "tasks")} deleted along with it`
            : "",
      }
    }
    case "task_deleted_batch": {
      // A batch deletion names no single task; what comes back is the
      // selection it took down, and it comes back as the one act it was.
      const tasks = details.task_count
      return {
        heading: "Restore tasks",
        name: plural(tasks, "1 task", "tasks"),
        comesBack: ", together, as they went",
      }
    }
    case "task_deleted": {
      const subtasks = details.subtask_count ?? 0
      return {
        heading: "Restore task",
        name: details.title,
        comesBack:
          subtasks > 0
            ? `, with ${plural(subtasks, "the subtask", "subtasks")} deleted along with it`
            : "",
      }
    }
    default:
      // Every other `kind` is unreachable here in practice — the log only
      // ever offers a restore on a deletion entry — but this stays safe
      // rather than assuming a caller never passes anything else.
      return { heading: "Restore", name: "this", comesBack: "" }
  }
}

/**
 * Restoring what a deletion entry took down — a task with its subtasks, or a
 * project with its tasks (FR-10.4). The toast says what came back; when a
 * restore has nowhere to come back to, the API says why, and that message is
 * what the user sees.
 */
export function useRestoreDeletion(entry: ActivityEntryPublic) {
  const reportChange = useReportChange()
  const described = describe(entry)
  const mutation = useMutation({
    mutationFn: () =>
      ActivityService.restoreFromActivityEntry({
        path: { entry_id: entry.id },
      }),
    onSuccess: () => toastSuccess(`“${described.name}” restored`),
    onError: (error: Error) => toastError(error),
    onSettled: () => reportChange({ type: "deletion restored" }),
  })
  return { ...described, mutation }
}

/**
 * The full log's Restore, behind a confirmation that says what else comes
 * back.
 */
export function RestoreDeletion({ entry }: RestoreDeletionProps) {
  const [isOpen, setIsOpen] = useState(false)
  const { heading, name, comesBack, mutation } = useRestoreDeletion(entry)

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-label={`Restore ${name}`}
        className={cn(
          textLink,
          "text-ink underline pointer-coarse:-my-3 pointer-coarse:py-3",
        )}
      >
        Restore
      </button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{heading}</DialogTitle>
          <DialogDescription>
            “{name}” comes back where it was{comesBack}. Comments and
            attachments come back too.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            loading={mutation.isPending}
            onClick={() =>
              mutation.mutate(undefined, { onSettled: () => setIsOpen(false) })
            }
          >
            Restore
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
