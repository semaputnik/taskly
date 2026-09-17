import { useState } from "react"

import type { TaskPublic } from "@/client"
import { DeleteTrigger } from "@/components/Records/RecordPanel"
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
import { useTaskDelete } from "./useTaskWrites"

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
  const deletion = useTaskDelete(task)

  const confirm = async () => {
    const outcome = await deletion.remove(cascadeWarned)
    if (outcome.saved) {
      setIsOpen(false)
      onSuccess()
    } else if (outcome.reason === "has subtasks") {
      setCascadeWarned(true)
    }
  }

  const openDialog = (nextOpen: boolean) => {
    setIsOpen(nextOpen)
    if (nextOpen) {
      setCascadeWarned(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={openDialog}>
      <DeleteTrigger label="Delete task" onClick={() => openDialog(true)} />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {cascadeWarned ? "This task has subtasks" : "Delete task"}
          </DialogTitle>
          {/* The way back is said at the moment the hand hesitates: a
              deletion is recorded in the activity log, and restoring it there
              brings back everything it took, as it was (FR-10.4). */}
          <DialogDescription>
            {cascadeWarned
              ? `Deleting “${task.title}” deletes its subtasks too, however deep they go. Nothing was deleted yet.`
              : `“${task.title}” will be deleted.`}{" "}
            {cascadeWarned
              ? "The task and its subtasks are recorded in your activity log as one deletion, and can be restored from there together."
              : "The deletion is recorded in your activity log, and the task can be restored from there."}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={deletion.isPending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            loading={deletion.isPending}
            onClick={confirm}
          >
            {cascadeWarned ? "Delete task and subtasks" : "Delete"}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default DeleteTask
