import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, Trash2, Upload } from "lucide-react"
import { useRef } from "react"

import {
  type AttachmentPublic,
  AttachmentsService,
  type TaskPublic,
} from "@/client"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface TaskAttachmentsProps {
  task: TaskPublic
  /** Hold the request back until the panel is the one on screen. */
  enabled?: boolean
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * A task's file attachments: upload, download, and delete. Byte storage sits
 * behind a swappable backend on the server (ADR-0002); this dialog only ever
 * sees the metadata and the raw bytes it downloads (FR-04.1).
 */
export const TaskAttachments = ({
  task,
  enabled = true,
}: TaskAttachmentsProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const queryKey = ["attachments", task.id]

  const { data: attachments, isLoading } = useQuery({
    queryKey,
    queryFn: async () =>
      (await AttachmentsService.readAttachments({ path: { task_id: task.id } }))
        .data,
    enabled,
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey })

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      AttachmentsService.uploadAttachment({
        path: { task_id: task.id },
        body: { file },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const deleteMutation = useMutation({
    mutationFn: (attachmentId: string) =>
      AttachmentsService.deleteAttachment({
        path: { attachment_id: attachmentId },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: invalidate,
  })

  const download = async (attachment: AttachmentPublic) => {
    try {
      const response = await AttachmentsService.downloadAttachment({
        path: { attachment_id: attachment.id },
        responseType: "blob",
      })
      const blob = response.data as unknown as Blob
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = attachment.filename
      // Safari only treats a click as a download trigger when the anchor is
      // actually in the document, and revoking the URL has to wait for the
      // download to have started rather than happen on the very next line.
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 0)
    } catch (error) {
      handleError.call(showErrorToast, error as Error)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        {isLoading ? (
          <p className="text-muted-foreground text-sm italic">Loading…</p>
        ) : attachments?.data.length ? (
          attachments.data.map((attachment) => (
            <div
              key={attachment.id}
              className="flex items-center justify-between gap-2 rounded-md border p-2 text-sm"
            >
              <div className="flex min-w-0 flex-col">
                <span className="truncate font-medium">
                  {attachment.filename}
                </span>
                <span className="text-muted-foreground text-xs">
                  {formatSize(attachment.size)}
                </span>
              </div>
              <div className="flex shrink-0 gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Download ${attachment.filename}`}
                  onClick={() => download(attachment)}
                >
                  <Download className="size-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Delete ${attachment.filename}`}
                  onClick={() => deleteMutation.mutate(attachment.id)}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            </div>
          ))
        ) : (
          <p className="text-muted-foreground text-sm italic">
            No attachments yet.
          </p>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          e.target.value = ""
          if (file) uploadMutation.mutate(file)
        }}
      />
      <LoadingButton
        variant="outline"
        loading={uploadMutation.isPending}
        onClick={() => fileInputRef.current?.click()}
      >
        <Upload />
        Upload a file
      </LoadingButton>
    </div>
  )
}

export default TaskAttachments
