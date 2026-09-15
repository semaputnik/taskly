import { useMutation, useQueryClient } from "@tanstack/react-query"
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
import { handleError } from "@/utils"

interface RestoreTaskProps {
  entry: ActivityEntryPublic
}

/**
 * Restoring a deleted task from its deletion entry, behind a confirmation
 * that says what else comes back with it (FR-10.4).
 *
 * When the task has nowhere to come back to — its parent or project is gone,
 * its project is archived — the API says so, and that message is what the
 * user sees.
 */
export function RestoreTask({ entry }: RestoreTaskProps) {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const title = (entry.details.title as string | undefined) ?? "this task"
  const subtasks = (entry.details.subtask_count as number | undefined) ?? 0

  const mutation = useMutation({
    mutationFn: () =>
      ActivityService.restoreFromActivityEntry({
        path: { entry_id: entry.id },
      }),
    onSuccess: () => {
      showSuccessToast(`“${title}” restored`)
      setIsOpen(false)
    },
    onError: (error: Error) => {
      setIsOpen(false)
      handleError.call(showErrorToast, error)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["activity"] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <Button variant="outline" size="sm" onClick={() => setIsOpen(true)}>
        <ArchiveRestore />
        Restore
      </Button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Restore task</DialogTitle>
          <DialogDescription>
            “{title}” comes back where it was
            {subtasks === 1 && ", with the subtask deleted along with it"}
            {subtasks > 1 &&
              `, with the ${subtasks} subtasks deleted along with it`}
            . Comments and attachments come back too.
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
