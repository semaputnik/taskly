import { FolderKanban } from "lucide-react"

import type { TaskPublic } from "@/client"
import {
  PropertyList,
  PropertyRow,
  ReadOnlyValue,
  RecordHeader,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { CaptureField, type CaptureTarget, useTaskCapture } from "./capture"

/**
 * The panel before the record exists.
 *
 * It is the same surface the task is read and edited in, opened one step
 * earlier: one field, already focused, and the project the task will land in
 * so that a default is visible rather than assumed. Everything else waits for
 * the record, because a task cannot exist without a title and a panel full of
 * controls that quietly buffer their values would be a form with the Save
 * button hidden.
 */
export function NewTask({
  target,
  onCreated,
}: {
  target: CaptureTarget
  onCreated: (task: TaskPublic, stay: boolean) => void
}) {
  const capture = useTaskCapture(target, onCreated)

  return (
    <>
      <RecordHeader
        breadcrumb="New task"
        title={
          <CaptureField
            autoFocus
            label="Task title"
            placeholder="What needs doing?"
            onCommit={capture.create}
            className={`border-transparent bg-transparent shadow-none dark:bg-transparent ${titleFieldClass}`}
          />
        }
      />

      <PropertyList>
        <PropertyRow icon={FolderKanban} label="Project">
          <ReadOnlyValue>{target.projectName}</ReadOnlyValue>
        </PropertyRow>
      </PropertyList>

      <p className="text-muted-foreground px-6 py-4 text-sm text-pretty">
        Enter records it and opens it here, where the rest is set. Hold ⌘ or
        Ctrl with Enter to keep capturing.
      </p>

      <output aria-live="polite" className="sr-only">
        {capture.announcement}
      </output>
    </>
  )
}
