import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { type TaskPublic, TasksService } from "@/client"
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
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError, isSubtaskCascadeError } from "@/utils"

interface DeleteTaskProps {
  task: TaskPublic
  onSuccess: () => void
}

/**
 * Deleting a task, behind a confirmation.
 *
 * A task with subtasks takes its whole subtree down with it, so the API
 * refuses the first request and the dialog turns that refusal into the warning
 * the user needs before confirming the cascade (FR-01.11, FR-01.12).
 */
const DeleteTask = ({ task, onSuccess }: DeleteTaskProps) => {
  const [isOpen, setIsOpen] = useState(false)
  // Set once the API has refused because of subtasks: the dialog then both
  // warns and, on the next attempt, confirms the cascade.
  const [cascadeWarned, setCascadeWarned] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (confirmCascade: boolean) =>
      TasksService.deleteTask({
        path: { task_id: task.id },
        query: { delete_subtasks: confirmCascade },
      }),
    onSuccess: () => {
      showSuccessToast("Task deleted successfully")
      setIsOpen(false)
      onSuccess()
    },
    onError: (error: Error) => {
      if (isSubtaskCascadeError(error)) {
        setCascadeWarned(true)
        return
      }
      handleError.call(showErrorToast, error)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  const openDialog = (nextOpen: boolean) => {
    setIsOpen(nextOpen)
    if (nextOpen) {
      setCascadeWarned(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={openDialog}>
      <DropdownMenuItem
        variant="destructive"
        onSelect={(e) => e.preventDefault()}
        onClick={() => openDialog(true)}
      >
        <Trash2 />
        Delete Task
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {cascadeWarned ? "This task has subtasks" : "Delete task"}
          </DialogTitle>
          <DialogDescription>
            {cascadeWarned
              ? `Deleting “${task.title}” deletes its subtasks too, however deep they go. Nothing was deleted yet.`
              : `“${task.title}” will be deleted.`}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            loading={mutation.isPending}
            onClick={() => mutation.mutate(cascadeWarned)}
          >
            {cascadeWarned ? "Delete task and subtasks" : "Delete"}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default DeleteTask
