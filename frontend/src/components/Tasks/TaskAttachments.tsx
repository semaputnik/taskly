import { useMutation, useQuery } from "@tanstack/react-query"
import { useRef } from "react"

import {
  type AttachmentPublic,
  AttachmentsService,
  type TaskPublic,
} from "@/client"
import { RecordSection } from "@/components/Records/RecordPanel"
import { attachmentsQuery, useReportChange } from "@/lib/serverState"
import { toastError } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import { DeleteAttachment } from "./DeleteAttachment"

interface TaskAttachmentsProps {
  task: TaskPublic
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * A task's files, as a section of the task: attach, download, and remove. Byte storage sits
 * behind a swappable backend on the server (ADR-0002); this section only ever
 * sees the metadata and the raw bytes it downloads (FR-04.1).
 */
export const TaskAttachments = ({ task }: TaskAttachmentsProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const reportChange = useReportChange()

  const { data: attachments } = useQuery(attachmentsQuery(task.id))

  const invalidate = () =>
    reportChange({ type: "attachments changed", taskId: task.id })

  const uploadMutation = useMutation({
    mutationFn: (file: File) =>
      AttachmentsService.uploadAttachment({
        path: { task_id: task.id },
        body: { file },
      }),
    onError: (error) => toastError(error),
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
      toastError(error)
    }
  }

  const files = attachments?.data ?? []
  // Touch is no place for a small text target: both actions grow to a
  // thumb and keep clear of one another.
  const action =
    "text-ink-3 hover:text-ink focus-visible:ring-ring/50 rounded-sm underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] pointer-coarse:min-h-11 pointer-coarse:min-w-11"

  return (
    <RecordSection
      title="Files"
      count={files.length > 0 ? files.length : undefined}
      action={
        <button
          type="button"
          disabled={uploadMutation.isPending}
          onClick={() => fileInputRef.current?.click()}
          className={cn(action, "text-[13px] disabled:opacity-50")}
        >
          {uploadMutation.isPending ? "Attaching…" : "Attach a file"}
        </button>
      }
    >
      <ul>
        {files.map((attachment) => (
          <li
            key={attachment.id}
            className="border-rule grid min-h-9 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b py-1.5"
          >
            <div className="flex min-w-0 flex-col sm:flex-row sm:items-baseline sm:gap-2">
              <span className="truncate text-sm font-medium">
                {attachment.filename}
              </span>
              {/* Where the bytes are kept is part of what the file is
                  (FR-04.11). Every file is kept in Taskly until another
                  store is connected (FR-04.3). */}
              <span className="text-ink-3 shrink-0 text-[12.5px]">
                {formatSize(attachment.size)} · kept in Taskly
              </span>
            </div>
            {/* Remove is a word, not a bin, and asks first: the bytes are
                gone the moment the server acts. On touch the two sit a thumb
                apart. */}
            <div className="flex shrink-0 items-center gap-3 text-[13px] pointer-coarse:gap-6">
              <button
                type="button"
                aria-label={`Download ${attachment.filename}`}
                className={action}
                onClick={() => download(attachment)}
              >
                Download
              </button>
              <DeleteAttachment
                attachment={attachment}
                className="pointer-coarse:min-h-11 pointer-coarse:min-w-11"
              />
            </div>
          </li>
        ))}
      </ul>
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
    </RecordSection>
  )
}

export default TaskAttachments
