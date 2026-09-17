import { useMutation } from "@tanstack/react-query"
import { useState } from "react"

import { type TagPublic, TagsService } from "@/client"
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
import { useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import { allTasks, totalTasks } from "./counts"

interface DeleteTagProps {
  tag: TagPublic
  onSuccess: () => void
}

function tasksLosingIt(tag: TagPublic): string {
  const total = totalTasks(tag)
  if (total === 0) {
    return "No task carries it."
  }
  // Archived work is reached too: the tag goes from every task it is on.
  return `It will be taken off ${allTasks(tag)}; ${total === 1 ? "the task stays as it is" : "the tasks stay as they are"}.`
}

/**
 * Deletes a tag, behind a confirmation that says how many tasks lose it. There
 * is no restoring it afterwards (FR-01.25, FR-01.26).
 */
const DeleteTag = ({ tag, onSuccess }: DeleteTagProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const reportChange = useReportChange()

  const mutation = useMutation({
    mutationFn: () => TagsService.deleteTag({ path: { tag_id: tag.id } }),
    onSuccess: () => {
      toastSuccess(`“${tag.name}” was deleted`)
      setIsOpen(false)
      onSuccess()
    },
    onError: (error) => toastError(error),
    onSettled: () => reportChange({ type: "tag changed" }),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DeleteTrigger label="Delete tag" onClick={() => setIsOpen(true)} />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete the tag {tag.name}?</DialogTitle>
          <DialogDescription>
            {tasksLosingIt(tag)} This can't be undone.
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

export default DeleteTag
