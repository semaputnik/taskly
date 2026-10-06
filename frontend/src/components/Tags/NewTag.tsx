import { useMutation } from "@tanstack/react-query"
import { useState } from "react"

import { TagsService } from "@/client"
import { useCaptureFocus, useRecordPanels } from "@/components/Records/panels"
import {
  ghost,
  gutter,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { refusalMessage } from "@/lib/apiErrors"
import { useReportChange } from "@/lib/serverState"
import { cn } from "@/lib/utils"

/**
 * A tag that does not exist yet, in the column it will be read in: its name,
 * editable from the first frame.
 *
 * Nothing is written while the draft is filled in. There is one visible
 * commit — Create, or Enter in the name — and it makes the tag and opens it
 * here, where what carries it and how to fold another into it are read. A
 * refused name stays in the field with the reason beneath it.
 */
export function NewTag() {
  const panels = useRecordPanels()
  const reportChange = useReportChange()
  const nameRef = useCaptureFocus<HTMLInputElement>()

  const [name, setName] = useState("")
  const [refusal, setRefusal] = useState<string | null>(null)
  const [announcement, setAnnouncement] = useState("")

  const mutation = useMutation({
    // The name rides with the call: a name typed an instant before Enter must
    // be the one sent, not the one an earlier render of this hook closed over.
    mutationFn: (typed: string) =>
      TagsService.createTag({ body: { name: typed } }),
    onSuccess: ({ data }) => {
      setAnnouncement("Tag created")
      panels.openTag(data.id)
    },
    // Said under the name, where the reader's words stay.
    onError: (error) => {
      setSending(false)
      setRefusal(refusalMessage(error))
    },
    onSettled: () => reportChange({ type: "tag created" }),
  })

  // The request is out from the moment it is made until it is answered. The
  // mutation's own pending state also covers the refresh that follows, which
  // would swallow a retry typed straight after a refusal.
  const [sending, setSending] = useState(false)
  const ready = name.trim() !== ""
  const create = () => {
    if (!ready || sending) return
    setSending(true)
    mutation.mutate(name.trim())
  }

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <div className={cn("pt-2 pb-[18px]", gutter)}>
        <Input
          ref={nameRef}
          aria-label="Tag name"
          aria-invalid={refusal ? true : undefined}
          placeholder="What does it gather?"
          maxLength={50}
          value={name}
          onChange={(event) => {
            setName(event.target.value)
            setRefusal(null)
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.nativeEvent.isComposing) {
              event.preventDefault()
              create()
            }
          }}
          className={cn(
            ghost,
            titleFieldClass,
            "-ml-2 border-transparent bg-transparent shadow-none dark:bg-transparent",
          )}
        />
        {refusal && (
          <p role="alert" className="text-late mt-1 text-[13px] text-pretty">
            {refusal}
          </p>
        )}
      </div>

      <p className={cn("text-ink-3 text-sm text-pretty", gutter)}>
        A tag means the same thing across every project, and stays until you
        delete it.
      </p>

      {/* The one commit, pinned where a thumb reaches it. */}
      <div
        className={cn(
          "bg-page border-rule-strong sticky bottom-0 mt-auto flex items-center justify-end gap-3 border-t py-3",
          gutter,
        )}
      >
        <span className="text-ink-3 text-xs">
          It opens here once it exists.
        </span>
        <LoadingButton
          disabled={!ready}
          loading={sending}
          onClick={create}
          className="pointer-coarse:h-11"
        >
          Create tag
        </LoadingButton>
      </div>

      <output aria-live="polite" className="sr-only">
        {announcement}
      </output>
    </div>
  )
}
