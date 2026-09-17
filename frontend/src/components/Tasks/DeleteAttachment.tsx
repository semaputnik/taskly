import { useMutation } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { type AttachmentPublic, AttachmentsService } from "@/client"
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
import { toastError } from "@/lib/toasts"
import { cn } from "@/lib/utils"

/**
 * Deleting an attachment, behind a confirmation that names the file.
 *
 * Unlike a task, an attachment has no way back: its bytes are gone the moment
 * the server acts, so an undo window would have nothing to restore. The
 * confirmation says so, and says what is not affected (FR-04.1).
 */
export function DeleteAttachment({
  attachment,
  className,
}: {
  attachment: AttachmentPublic
  className?: string
}) {
  const [isOpen, setIsOpen] = useState(false)
  const reportChange = useReportChange()

  const mutation = useMutation({
    mutationFn: () =>
      AttachmentsService.deleteAttachment({
        path: { attachment_id: attachment.id },
      }),
    // The list on screen is the receipt; only a failure is worth a toast, and
    // the file stays where it was.
    onSuccess: () => setIsOpen(false),
    onError: (error) => toastError(error),
    onSettled: () =>
      reportChange({
        type: "attachments changed",
        taskId: attachment.task_id,
      }),
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <Button
        variant="ghost"
        size="icon"
        aria-label={`Delete ${attachment.filename}`}
        className={cn(
          "text-muted-foreground hover:text-destructive",
          className,
        )}
        onClick={() => setIsOpen(true)}
      >
        <Trash2 />
      </Button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="break-all">
            Delete {attachment.filename}?
          </DialogTitle>
          <DialogDescription>
            The file is removed from this task and its contents are deleted, so
            it cannot be restored — the activity log only notes that it was
            removed. The task and its comments stay as they are.
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
            Delete file
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
