import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { CaptureField } from "@/components/Tasks/capture"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { RecordHeader, titleFieldClass } from "./RecordPanel"

/**
 * A record that does not exist yet, in the panel it will be read in.
 *
 * Creating and editing are one act: the panel opens with the record's name as
 * its only field, and everything else about the record is set afterwards in
 * the same place. It is the task capture pattern, which projects and tags
 * follow because a record type should not have two ways to come into being.
 */
export function NewRecord<T extends { id: string }>({
  kind,
  label,
  placeholder,
  hint,
  create,
  invalidate,
  onCreated,
}: {
  /** What is being made, said in the panel's breadcrumb. */
  kind: string
  label: string
  placeholder: string
  hint: React.ReactNode
  create: (name: string) => Promise<{ data: T }>
  /** The query keys the new record belongs to. */
  invalidate: string[]
  onCreated: (record: T) => void
}) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const [announcement, setAnnouncement] = useState("")

  const mutation = useMutation({
    mutationFn: (name: string) => create(name),
    onSuccess: ({ data }) => {
      setAnnouncement(`${kind} created`)
      onCreated(data)
    },
    onError: (error: Error) => handleError.call(showErrorToast, error),
    onSettled: () => {
      for (const key of invalidate) {
        queryClient.invalidateQueries({ queryKey: [key] })
      }
    },
  })

  return (
    <>
      <RecordHeader
        breadcrumb={`New ${kind.toLowerCase()}`}
        title={
          <CaptureField
            autoFocus
            label={label}
            placeholder={placeholder}
            onCommit={async (name) => {
              const trimmed = name.trim()
              if (!trimmed) return false
              try {
                await mutation.mutateAsync(trimmed)
              } catch {
                // The name stays on screen: a refusal is the API's, and
                // retyping it would be the reader's cost.
              }
              return false
            }}
            className={`border-transparent bg-transparent shadow-none dark:bg-transparent ${titleFieldClass}`}
          />
        }
      />

      <p className="text-muted-foreground px-6 py-4 text-sm text-pretty">
        {hint}
      </p>

      <output aria-live="polite" className="sr-only">
        {announcement}
      </output>
    </>
  )
}
