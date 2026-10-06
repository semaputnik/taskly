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

/** What the confirmation says comes back, for a task or a project. */
function describe(entry: ActivityEntryPublic) {
  if (entry.entity_type === "project") {
    const name = (entry.details.name as string | undefined) ?? "this project"
    const tasks = (entry.details.task_count as number | undefined) ?? 0
    return {
      heading: "Restore project",
      name,
      comesBack:
        tasks > 0
          ? `, with ${plural(tasks, "the task", "tasks")} deleted along with it`
          : "",
    }
  }
  const title = entry.details.title as string | undefined
  if (title === undefined) {
    // A batch deletion names no single task; what comes back is the selection
    // it took down, and it comes back as the one act it was.
    const tasks = (entry.details.task_count as number | undefined) ?? 0
    return {
      heading: "Restore tasks",
      name: plural(tasks, "1 task", "tasks"),
      comesBack: ", together, as they went",
    }
  }
  const name = title
  const subtasks = (entry.details.subtask_count as number | undefined) ?? 0
  return {
    heading: "Restore task",
    name,
    comesBack:
      subtasks > 0
        ? `, with ${plural(subtasks, "the subtask", "subtasks")} deleted along with it`
        : "",
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
