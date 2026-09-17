import { useMutation } from "@tanstack/react-query"
import { useState } from "react"

import {
  type DueDateScope,
  type TaskPublic,
  TasksService,
  type TaskUpdate,
} from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { useReportChange } from "@/lib/serverState"
import { handleError } from "@/utils"
import { sameRecurrence } from "./recurrence"

/**
 * Saving a field of a task, from wherever it is being edited.
 *
 * Editing happens field by field in the task's panel, so this is called often
 * and says nothing when it succeeds — the value on screen is the receipt. Only
 * a failure is worth interrupting for.
 *
 * Two rules travel with it. Moving an open occurrence of a recurring task has
 * to say whether the routine moves too, so the update is held until the reader
 * chooses (`scopeNeeded`). And an omitted key means "leave unchanged" to the
 * API, so a cleared field must be sent as `null` rather than dropped.
 */
export function useTaskUpdate(task: TaskPublic) {
  // An update held back until the user says how far a new due date reaches.
  const [awaitingScope, setAwaitingScope] = useState<TaskUpdate | null>(null)
  const reportChange = useReportChange()
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (body: TaskUpdate) =>
      TasksService.updateTask({ path: { task_id: task.id }, body }),
    onSuccess: () => setAwaitingScope(null),
    onError: (error: Error) => {
      setAwaitingScope(null)
      handleError.call(showErrorToast, error)
    },
    onSettled: () => reportChange({ type: "task changed", taskId: task.id }),
  })

  const save = (body: TaskUpdate) => {
    // A changed rule restarts the schedule anyway; only a moved date on an
    // unchanged rule is ambiguous.
    const reschedules =
      task.recurrence &&
      task.status !== "done" &&
      body.due_date !== undefined &&
      body.due_date !== (task.due_date ?? null) &&
      sameRecurrence(body.recurrence ?? task.recurrence, task.recurrence)

    if (reschedules) {
      setAwaitingScope(body)
      return
    }
    mutation.mutate(body)
  }

  return {
    save,
    isPending: mutation.isPending,
    scopeNeeded: awaitingScope !== null,
    cancelScope: () => setAwaitingScope(null),
    chooseScope: (scope: DueDateScope) => {
      if (awaitingScope) {
        mutation.mutate({ ...awaitingScope, due_date_scope: scope })
      }
    },
  }
}
