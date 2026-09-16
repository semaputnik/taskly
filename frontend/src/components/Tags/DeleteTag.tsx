import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { type TagPublic, TagsService } from "@/client"
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

interface DeleteTagProps {
  tag: TagPublic
  onSuccess: () => void
}

function tasksLosingIt(count: number): string {
  if (count === 0) {
    return "No task carries it."
  }
  return `It will be taken off ${count} ${count === 1 ? "task" : "tasks"}.`
}

/**
 * Deletes a tag, behind a confirmation that says how many tasks lose it. There
 * is no restoring it afterwards (FR-01.25, FR-01.26).
 */
const DeleteTag = ({ tag, onSuccess }: DeleteTagProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => TagsService.deleteTag({ path: { tag_id: tag.id } }),
    onSuccess: () => {
      showSuccessToast(`“${tag.name}” was deleted`)
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tags"] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      {/* The one act with no undo gets the one control in the panel's
          corner: no menu to open first, and no neighbours to catch a stray
          click. */}
      <Button
        variant="ghost"
        size="icon"
        aria-label="Delete tag"
        className="text-muted-foreground hover:text-destructive"
        onClick={() => setIsOpen(true)}
      >
        <Trash2 />
      </Button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete the tag {tag.name}?</DialogTitle>
          <DialogDescription>
            {tasksLosingIt(tag.task_count ?? 0)} This can't be undone.
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
