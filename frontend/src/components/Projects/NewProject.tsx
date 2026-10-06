import { useMutation } from "@tanstack/react-query"
import { useState } from "react"

import { ProjectsService } from "@/client"
import { useCaptureFocus, useRecordPanels } from "@/components/Records/panels"
import {
  DescriptionSection,
  ghost,
  gutter,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Textarea } from "@/components/ui/textarea"
import { useReportChange } from "@/lib/serverState"
import { toastError } from "@/lib/toasts"
import { cn } from "@/lib/utils"

/**
 * A project that does not exist yet, in the column it will be read in: its
 * name and its description, editable from the first frame, in the order of the
 * record's own sections.
 *
 * Nothing is written while the draft is filled in. There is one visible
 * commit — Create, or Enter in the name — and it makes the project and opens
 * it here, where its state and the tasks it holds are read.
 */
export function NewProject() {
  const panels = useRecordPanels()
  const reportChange = useReportChange()
  const nameRef = useCaptureFocus<HTMLInputElement>()

  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [announcement, setAnnouncement] = useState("")

  const mutation = useMutation({
    // What was typed rides with the call: text typed an instant before Enter
    // must be what is sent, not what an earlier render of this hook closed
    // over.
    mutationFn: (typed: { name: string; description: string | null }) =>
      ProjectsService.createProject({ body: typed }),
    onSuccess: ({ data }) => {
      setAnnouncement("Project created")
      panels.openProject(data.id)
    },
    onError: (error) => {
      setSending(false)
      toastError(error)
    },
    onSettled: () => reportChange({ type: "project created" }),
  })

  // The request is out from the moment it is made until it is answered. The
  // mutation's own pending state also covers the refresh that follows, which
  // would swallow a retry typed straight after a refusal.
  const [sending, setSending] = useState(false)
  const ready = name.trim() !== ""
  const create = () => {
    if (!ready || sending) return
    setSending(true)
    mutation.mutate({
      name: name.trim(),
      description: description.trim() || null,
    })
  }

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <div className={cn("pt-2 pb-[18px]", gutter)}>
        <Input
          ref={nameRef}
          aria-label="Project name"
          placeholder="Name the project"
          maxLength={255}
          value={name}
          onChange={(event) => setName(event.target.value)}
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
      </div>

      <DescriptionSection>
        <Textarea
          aria-label="Project description"
          placeholder="What is it for? (optional)"
          maxLength={255}
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className={cn(ghost, "-ml-2")}
        />
      </DescriptionSection>

      {/* The one commit, pinned where a thumb reaches it. */}
      <div
        className={cn(
          "bg-page border-rule-strong sticky bottom-0 mt-auto flex items-center justify-end gap-3 border-t py-3",
          gutter,
        )}
      >
        <span className="text-ink-3 text-xs">
          It opens here, ready for its first task.
        </span>
        <LoadingButton
          disabled={!ready}
          loading={sending}
          onClick={create}
          className="pointer-coarse:h-11"
        >
          Create project
        </LoadingButton>
      </div>

      <output aria-live="polite" className="sr-only">
        {announcement}
      </output>
    </div>
  )
}
