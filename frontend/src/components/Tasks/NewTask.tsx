import { FolderKanban } from "lucide-react"

import type { TaskPublic } from "@/client"
import {
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { CaptureField, type CaptureTarget, useTaskCapture } from "./capture"
import { Row } from "./TaskProperties"

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
      <SheetHeader className="gap-3 border-b p-6">
        <SheetDescription className="pr-20 text-sm">New task</SheetDescription>
        <SheetTitle className="sr-only">New task</SheetTitle>
        <CaptureField
          autoFocus
          label="Task title"
          placeholder="What needs doing?"
          onCommit={capture.create}
          className="h-auto border-transparent bg-transparent px-2 py-1.5 text-xl leading-snug font-semibold shadow-none md:text-xl dark:bg-transparent"
        />
      </SheetHeader>

      <div className="divide-y px-6 py-2">
        <Row icon={FolderKanban} label="Project">
          <span className="text-muted-foreground px-2">
            {target.projectName}
          </span>
        </Row>
      </div>

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
