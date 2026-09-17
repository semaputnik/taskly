import { useMutation } from "@tanstack/react-query"
import { ArchiveRestore } from "lucide-react"
import { useState } from "react"

import { type ActivityEntryPublic, ActivityService } from "@/client"
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
import { useReportChange } from "@/lib/serverState"
import { handleError } from "@/utils"

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
 * project with its tasks — behind a confirmation that says what else comes
 * back (FR-10.4).
 *
 * When a restore has nowhere to come back to, the API says why, and that
 * message is what the user sees.
 */
export function RestoreDeletion({ entry }: RestoreDeletionProps) {
  const [isOpen, setIsOpen] = useState(false)
  const reportChange = useReportChange()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { heading, name, comesBack } = describe(entry)

  const mutation = useMutation({
    mutationFn: () =>
      ActivityService.restoreFromActivityEntry({
        path: { entry_id: entry.id },
      }),
    onSuccess: () => {
      showSuccessToast(`“${name}” restored`)
      setIsOpen(false)
    },
    onError: (error: Error) => {
      setIsOpen(false)
      handleError.call(showErrorToast, error)
    },
    onSettled: () => reportChange({ type: "deletion restored" }),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <Button variant="outline" size="sm" onClick={() => setIsOpen(true)}>
        <ArchiveRestore />
        Restore
      </Button>
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
            onClick={() => mutation.mutate()}
          >
            Restore
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
