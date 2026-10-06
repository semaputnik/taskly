import { useMutation } from "@tanstack/react-query"
import { useState } from "react"

import { PaperlessService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { DialogTrigger } from "@/components/ui/dialog"
import { useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import { pdfs } from "./paperlessTest"

/**
 * Ending the connection. Nothing in Paperless is deleted, and a PDF kept there
 * stays there, but Taskly cannot reach it until the connection is set again
 * (FR-04.8), so the question says how many before the button that does it.
 */
export function DisconnectPaperless({
  kept,
  triggerClassName,
  onDone,
}: {
  /** How many PDFs are kept in Paperless now. */
  kept: number
  triggerClassName?: string
  onDone: () => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const reportChange = useReportChange()

  const mutation = useMutation({
    mutationFn: () => PaperlessService.disconnect(),
    onSuccess: ({ data }) => {
      setIsOpen(false)
      onDone()
      toastSuccess(
        data.unreachable_documents > 0
          ? `Paperless disconnected. ${pdfs(data.unreachable_documents)} out of reach until you connect it again.`
          : "Paperless disconnected",
      )
    },
    onError: (error) => toastError(error),
    onSettled: () => reportChange({ type: "paperless changed" }),
  })

  return (
    <ConfirmDialog
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      trigger={
        <DialogTrigger asChild>
          <button type="button" className={triggerClassName}>
            Disconnect
            <span className="sr-only"> Paperless</span>
          </button>
        </DialogTrigger>
      }
      title="Disconnect Paperless?"
      confirm="Disconnect"
      destructive
      pending={mutation.isPending}
      onConfirm={() => mutation.mutate()}
    >
      {kept > 0
        ? `${pdfs(kept)} kept in Paperless stay there, and nothing is deleted from it, but Taskly cannot open ${kept === 1 ? "it" : "them"} until you connect Paperless again.`
        : "No PDF is kept in Paperless yet."}{" "}
      PDFs attached from now on stay in Taskly, and so does any still on its way
      to Paperless.
    </ConfirmDialog>
  )
}
