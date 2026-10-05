import { Link as RouterLink } from "@tanstack/react-router"
import {
  CalendarDays,
  CornerDownRight,
  ListTree,
  type LucideIcon,
  Repeat,
  Tag,
} from "lucide-react"

import type { TaskPublic } from "@/client"
import { recordLink } from "@/components/Records/panels"
import { Skeleton } from "@/components/ui/skeleton"
import { isoDay } from "@/lib/dates"
import { cn } from "@/lib/utils"
import { CompleteTask } from "./CompleteTask"
import { type DueTone, type MetaItem, metaLine } from "./compact"

/** Only a missed day is coloured; today is ink, and the rest stay quiet. */
const DUE_TONE: Record<DueTone, string> = {
  late: "text-late font-medium",
  today: "text-ink font-medium",
  soon: "",
  later: "",
}

/** Each meta item's glyph, and what it is said as to a screen reader. */
const META: Record<
  Exclude<MetaItem["kind"], "project">,
  { glyph: LucideIcon; said: string }
> = {
  subtasks: { glyph: ListTree, said: "Subtasks done:" },
  due: { glyph: CalendarDays, said: "Due:" },
  recurrence: { glyph: Repeat, said: "Repeats:" },
  tag: { glyph: Tag, said: "Tag:" },
}

/**
 * The task line: its status mark, which is also the control that closes it
 * and carries the priority as its colour; the title in medium weight; and
 * beneath it a quiet meta line — subtask progress, due day, recurrence and
 * tags, each a small glyph and its value, with the project at the far right
 * as a neutral square and its name. A line with nothing to say in its meta
 * is one line tall.
 *
 * It is the dashboard's line and the task list's compact view. It opens the
 * task from its title, never the whole line: the line also holds the mark,
 * and a checkbox inside a link is a trap.
 */
export function CompactTaskRow({
  task,
  projectName,
  receipt = false,
}: {
  task: TaskPublic
  /** Set at the far right of the meta line. */
  projectName?: string
  /**
   * Completing the task takes this line off the list it is in, so the
   * mark confirms the move and offers the way back (ADR-0006).
   */
  receipt?: boolean
}) {
  const done = task.status === "done"
  const items = metaLine(task, { today: isoDay(new Date()), projectName })
  const project = items.find((item) => item.kind === "project")
  const facts = items.filter((item) => item.kind !== "project")

  return (
    <div className="hover:from-hover flex gap-3 border-b border-rule px-4 py-2.5 transition-colors last:border-b-0 hover:bg-linear-to-r hover:to-transparent hover:to-85%">
      {/* Held to the title's line, not centred on the whole task line, and
          nudged so the two share a centre: the mark itself sits a pixel
          down, inside its larger target. */}
      <CompleteTask
        task={task}
        asMark
        receipt={receipt}
        className="-mt-[3px] self-start"
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {task.parent_id && (
            <CornerDownRight
              className="text-ink-3 size-3.5 shrink-0"
              aria-label="Subtask"
            />
          )}
          <RouterLink
            {...recordLink("task", task.id)}
            className={cn(
              "focus-visible:ring-ring/50 min-w-0 truncate rounded-sm leading-snug font-medium underline-offset-4 outline-none hover:underline focus-visible:ring-[3px]",
              done && "text-ink-3 line-through",
            )}
          >
            {task.title}
          </RouterLink>
        </div>

        {items.length > 0 && (
          <div className="text-ink-3 mt-1 flex items-start gap-3 text-[0.8125rem] leading-tight tabular-nums">
            {facts.length > 0 && (
              <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
                {facts.map((item, index) => (
                  <MetaFact key={`${item.kind}-${index}`} item={item} />
                ))}
              </div>
            )}
            {project && (
              // Last and at the far right, and the first thing to give way:
              // it shrinks a hundred times faster than the facts beside it,
              // so a long project name truncates before the line has to wrap
              // what it says about the task itself.
              <span className="ml-auto flex max-w-[50%] min-w-16 shrink-[100] items-center justify-end gap-1.5">
                <span
                  className="size-2 shrink-0 rounded-[2px] bg-current opacity-55"
                  aria-hidden
                />
                <span className="sr-only">Project:</span>
                <span className="truncate">{project.text}</span>
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function MetaFact({ item }: { item: Exclude<MetaItem, { kind: "project" }> }) {
  const { glyph: Glyph, said } = META[item.kind]
  return (
    <span
      className={cn(
        "flex min-w-0 items-center gap-1",
        item.kind === "due" && DUE_TONE[item.tone],
      )}
    >
      <Glyph className="size-[13px] shrink-0" aria-hidden />
      <span className="sr-only">{said}</span>
      <span className="truncate">{item.text}</span>
    </span>
  )
}

/** The line while its task is on its way: the same two lines, in outline. */
export function CompactTaskRowPending() {
  return (
    <div className="flex gap-3 border-b border-rule px-4 py-2.5 last:border-b-0">
      <Skeleton className="mt-px size-[1.125rem] shrink-0 rounded-full" />
      <div className="flex flex-1 flex-col gap-1.5">
        <Skeleton className="h-4 w-48 max-w-full" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
  )
}
