import { useMutation, useQuery } from "@tanstack/react-query"
import { AxiosError } from "axios"
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

/** How often a task's files are read again while one is on its way to Paperless. */
const HANDOVER_REFRESH_MS = 5_000

const isSending = (attachment: AttachmentPublic) =>
  attachment.paperless_handover?.state === "pending"

/**
 * A download that failed has its answer in a Blob, because the request asked
 * for the file. Read it back so the notice says what the API said (a Paperless
 * that cannot be reached, a document it no longer has).
 */
async function readableFailure(error: unknown): Promise<unknown> {
  if (error instanceof AxiosError && error.response?.data instanceof Blob) {
    try {
      const data = JSON.parse(await error.response.data.text())
      return new AxiosError(
        error.message,
        error.code,
        error.config,
        error.request,
        { ...error.response, data },
      )
    } catch {
      return error
    }
  }
  return error
}

/**
 * A task's files, as a section of the task: attach, download, and remove. Byte storage sits
 * behind a swappable backend on the server (ADR-0002); this section only ever
 * sees the metadata and the raw bytes it downloads (FR-04.1). Each file says
 * where it is kept (FR-04.11): in Paperless, with the way to the document,
 * here, on its way to Paperless, or, when that failed, why and how to try again.
 */
export const TaskAttachments = ({ task }: TaskAttachmentsProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const reportChange = useReportChange()

  const { data: attachments } = useQuery({
    ...attachmentsQuery(task.id),
    // A PDF is handed over in the background, so the answer changes without
    // the reader doing anything: keep reading until none is on its way.
    refetchInterval: (query) =>
      query.state.data?.data.some(isSending) ? HANDOVER_REFRESH_MS : false,
  })

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

  const resendMutation = useMutation({
    mutationFn: (attachment: AttachmentPublic) =>
      AttachmentsService.resendAttachment({
        path: { attachment_id: attachment.id },
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
      toastError(await readableFailure(error))
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
        {files.map((attachment) => {
          const handover = attachment.paperless_handover
          return (
            <li
              key={attachment.id}
              className="border-rule grid min-h-9 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 border-b py-1.5"
            >
              <div className="flex min-w-0 flex-col sm:flex-row sm:items-baseline sm:gap-2">
                <span className="truncate text-sm font-medium">
                  {attachment.filename}
                </span>
                {/* Where the bytes are kept is part of what the file is
                    (FR-04.11). */}
                <span className="text-ink-3 shrink-0 text-[12.5px]">
                  {formatSize(attachment.size)} · <KeptIn file={attachment} />
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
              {handover?.state === "failed" && (
                // Still here and still downloadable; this says why Paperless
                // does not have it and offers the one thing to do about it.
                <p className="text-late col-span-2 flex flex-wrap items-baseline gap-x-3 pt-0.5 text-[12.5px] leading-snug">
                  <span className="min-w-0 text-pretty break-words">
                    Paperless would not take it:{" "}
                    {handover.error ?? "no reason was given"}
                  </span>
                  <button
                    type="button"
                    aria-label={`Send ${attachment.filename} again`}
                    disabled={resendMutation.isPending}
                    className={cn(action, "text-ink-2 font-medium")}
                    onClick={() => resendMutation.mutate(attachment)}
                  >
                    Send again
                  </button>
                </p>
              )}
            </li>
          )
        })}
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

/** Where a file is kept, in words: in Paperless (with the way to it), on its way there, or here. */
function KeptIn({ file }: { file: AttachmentPublic }) {
  if (file.kept_in === "paperless") {
    return file.paperless_url ? (
      <a
        href={file.paperless_url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-ink-2 hover:text-ink focus-visible:ring-ring/50 rounded-sm underline underline-offset-4 outline-none focus-visible:ring-[3px]"
      >
        kept in Paperless
        <span className="sr-only"> (opens the document)</span>
      </a>
    ) : (
      // Disconnected: the document is still there, out of Taskly's reach.
      <>kept in Paperless, not connected</>
    )
  }
  if (isSending(file)) return <>sending to Paperless…</>
  return <>kept here</>
}

export default TaskAttachments
