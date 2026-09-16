import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { type ProjectPublic, ProjectsService } from "@/client"
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
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

/**
 * Deleting a project, behind a confirmation that names the cascade.
 *
 * A project takes its tasks down with it, so the count is said before the act,
 * not discovered after it. Both are restorable from the activity log, which
 * the confirmation says too: a deletion that can be undone should not be
 * dressed as one that cannot (FR-05.8, FR-05.9).
 */
export default function DeleteProject({
  project,
  onSuccess,
}: {
  project: ProjectPublic
  onSuccess: () => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () =>
      ProjectsService.deleteProject({ path: { project_id: project.id } }),
    onSuccess: () => {
      showSuccessToast(`“${project.name}” was deleted`)
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  const tasks =
    project.task_count === 0
      ? "It holds no tasks."
      : `Its ${project.task_count === 1 ? "task" : `${project.task_count} tasks`} go with it.`

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DeleteTrigger label="Delete project" onClick={() => setIsOpen(true)} />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete {project.name}?</DialogTitle>
          <DialogDescription>
            {tasks} The deletion is recorded in your activity log, so the
            project and its tasks can be restored from there.
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
            onClick={() => mutation.mutate()}
          >
            Delete
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
