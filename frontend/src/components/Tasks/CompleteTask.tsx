import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { type SubtaskCompletion, type TaskPublic, TasksService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError, isUncompletedSubtasksError } from "@/utils"

interface CompleteTaskProps {
  task: TaskPublic
}

/**
 * The completion checkbox for a task.
 *
 * Completing a task that still has open subtasks is refused by the API until
 * the request says what happens to them, so the refusal turns into a prompt
 * offering both outcomes (FR-02.5).
 */
export function CompleteTask({ task }: CompleteTaskProps) {
  const [isPrompting, setIsPrompting] = useState(false)
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (body: { completed: boolean; subtasks?: SubtaskCompletion }) =>
      TasksService.updateTask({ path: { task_id: task.id }, body }),
    onSuccess: () => {
      setIsPrompting(false)
    },
    onError: (error: Error) => {
      if (isUncompletedSubtasksError(error)) {
        setIsPrompting(true)
        return
      }
      handleError.call(showErrorToast, error)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return (
    <>
      <Checkbox
        // Round: a square check in this table selects a row, and completion
        // is neither a selection nor a value — it is the state of the task.
        className="rounded-full"
        checked={task.completed}
        disabled={mutation.isPending}
        onCheckedChange={(checked) =>
          mutation.mutate({ completed: checked === true })
        }
        aria-label={
          task.completed ? "Mark as not completed" : "Mark as completed"
        }
      />

      <Dialog open={isPrompting} onOpenChange={setIsPrompting}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>This task has subtasks</DialogTitle>
            <DialogDescription>
              “{task.title}” still has subtasks that are not completed. Choose
              what happens to them.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="sm:flex-col sm:gap-2">
            <Button
              variant="outline"
              disabled={mutation.isPending}
              onClick={() =>
                mutation.mutate({
                  completed: true,
                  subtasks: "complete",
                })
              }
            >
              Complete the subtasks too
            </Button>
            <Button
              variant="outline"
              disabled={mutation.isPending}
              onClick={() =>
                mutation.mutate({
                  completed: true,
                  subtasks: "leave_uncompleted",
                })
              }
            >
              Leave the subtasks uncompleted
            </Button>
            <DialogClose asChild>
              <Button variant="ghost" disabled={mutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
