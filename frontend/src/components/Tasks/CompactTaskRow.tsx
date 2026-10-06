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
import { recordLink, useIsOpen } from "@/components/Records/panels"
import { Skeleton } from "@/components/ui/skeleton"
import { isoDay } from "@/lib/dates"
import { cn } from "@/lib/utils"
import { CompleteTask } from "./CompleteTask"
import { type DueTone, type MetaFact, metaLine } from "./compact"
import { StatusMark } from "./status"

/**
 * Only a missed day is coloured; today is ink. Both are set a weight up, as
 * the two days that ask for action; the rest stay quiet.
 */
const DUE_TONE: Record<DueTone, string> = {
  late: "text-late font-medium",
  today: "text-ink font-medium",
  soon: "",
  later: "",
}

/** Each fact's glyph, and the label a screen reader hears before it. */
const FACT: Record<
  Exclude<MetaFact["kind"], "assignee">,
  { glyph: LucideIcon; spokenLabel: string }
> = {
  subtasks: { glyph: ListTree, spokenLabel: "Subtasks done:" },
  due: { glyph: CalendarDays, spokenLabel: "Due:" },
  recurrence: { glyph: Repeat, spokenLabel: "Repeats:" },
  tag: { glyph: Tag, spokenLabel: "Tag:" },
}

/**
 * The task line: its status mark, which is also the control that closes it
 * and carries the priority as its colour; the title in medium weight; and
 * beneath it a quiet meta line — subtask progress, due day, recurrence and
 * tags, each a small glyph and its value, then who the task is with, in
 * words, with the project at the far right
 * as a neutral square and its name. The project is always there, so a line
 * is two lines tall even when it has nothing else to say.
 *
 * It is the dashboard's line and the task list's compact view. It opens the
 * task from its title, never the whole line: the line also holds the mark,
 * and a checkbox inside a link is a trap.
 */
export function CompactTaskRow({
  task,
  projectName,
  receipt = false,
  flush = false,
  depth = 0,
  asItem = false,
  readOnly = false,
  children,
}: {
  task: TaskPublic
  /** Set at the far right of the meta line. */
  projectName?: string
  /**
   * Completing the task takes this line off the list it is in, so the
   * mark confirms the move and offers the way back (ADR-0006).
   */
  receipt?: boolean
  /**
   * Set on a page that is its own column, with no frame around the list:
   * the line runs to the column's edges, as the rules between lines do.
   */
  flush?: boolean
  /**
   * How far down its root task's tree the line is drawn, where it is drawn
   * under that root: indented, with a branch mark in place of the subtask
   * glyph, which only says a line is a subtask when nothing beside it does.
   * Root tasks, and lines in a list that is not a tree, are 0.
   */
  depth?: number
  /** Set where the line sits in a list: it is the list's item itself. */
  asItem?: boolean
  /**
   * Set for a task nothing can change, one of an archived project's (FR-05.12):
   * the status is shown, not a control, and the title is text, not a way into
   * a panel whose every field would refuse an edit.
   */
  readOnly?: boolean
  /** Set under the meta line, in the title's column: a line about the task. */
  children?: React.ReactNode
}) {
  const done = task.status === "done"
  // The line whose task is open in the column is tinted, as one under the
  // pointer is. A reader who cannot see the tint has the link's own
  // aria-current, which the router sets on the link to where they are.
  const open = useIsOpen("task", task.id)
  const { facts, project } = metaLine(task, {
    today: isoDay(new Date()),
    projectName,
  })

  const Line = asItem ? "li" : "div"
  const branch = depth > 0

  return (
    <Line
      className={cn(
        "border-rule hover:row-tint flex gap-3 border-b py-2.5 transition-colors last:border-b-0",
        open && "row-tint",
        flush ? "px-0" : "px-4",
      )}
      // 30px under the root, and a little more for each level below that.
      style={branch ? { paddingLeft: 30 + (depth - 1) * 20 } : undefined}
    >
      {branch && (
        <span
          role="img"
          aria-label="Subtask"
          className="border-rule-strong -mr-1 mt-0.5 size-2.5 shrink-0 self-start rounded-bl-[3px] border-b-[1.5px] border-l-[1.5px]"
        />
      )}
      {/* Held to the title's line, not centred on the whole task line, and
          nudged so the two share a centre: the mark itself sits a pixel
          down, inside its larger target. */}
      {readOnly ? (
        <span className="mt-px flex self-start">
          <StatusMark status={task.status} priority={task.priority} labelled />
        </span>
      ) : (
        <CompleteTask
          task={task}
          asMark
          receipt={receipt}
          className="-mt-[3px] self-start"
        />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {task.parent_id && !branch && (
            <CornerDownRight
              className="text-ink-3 size-3.5 shrink-0"
              aria-label="Subtask"
            />
          )}
          {readOnly ? (
            <span
              className={cn(
                "min-w-0 truncate leading-snug font-medium",
                done && "text-ink-3 line-through",
              )}
            >
              {task.title}
            </span>
          ) : (
            <RouterLink
              {...recordLink("task", task.id)}
              className={cn(
                "focus-visible:ring-ring/50 min-w-0 truncate rounded-sm leading-snug font-medium underline-offset-4 outline-none hover:underline focus-visible:ring-[3px]",
                done && "text-ink-3 line-through",
              )}
            >
              {task.title}
            </RouterLink>
          )}
        </div>

        {(facts.length > 0 || project) && (
          <div className="text-ink-3 mt-1 flex items-start gap-3 text-[0.8125rem] leading-tight tabular-nums">
            {facts.length > 0 && (
              <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
                {facts.map((fact, index) => (
                  <Fact key={`${fact.kind}-${index}`} fact={fact} />
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
                <span className="truncate">{project}</span>
              </span>
            )}
          </div>
        )}
        {children}
      </div>
    </Line>
  )
}

function Fact({ fact }: { fact: MetaFact }) {
  if (fact.kind === "assignee") return <Assignee fact={fact} />
  const { glyph: Glyph, spokenLabel } = FACT[fact.kind]
  return (
    <span
      className={cn(
        "flex min-w-0 items-center gap-1",
        fact.kind === "due" && DUE_TONE[fact.tone],
      )}
    >
      <Glyph className="size-[0.8125rem] shrink-0" aria-hidden />
      <span className="sr-only">{spokenLabel}</span>
      <span className="truncate">{fact.text}</span>
    </span>
  )
}

/**
 * Whose task it is, in words alone: a name needs no glyph beside it. Quiet
 * like the rest of the line, except the hand-over, which is set in Ink 2 as
 * the one fact that asks something of the reader (FR-06.13). On a phone its
 * name is capped, so a long one gives way before the project does.
 */
export function Assignee({
  fact,
}: {
  fact: Extract<MetaFact, { kind: "assignee" }>
}) {
  return (
    <span
      className={cn(
        "flex max-w-32 min-w-0 sm:max-w-64",
        fact.handover && "text-ink-2",
      )}
    >
      <span className="sr-only">
        {fact.handover ? "Handed over by:" : "Assigned to:"}
      </span>
      {/* The arrow is the hand-over; a long name gives way before it does. */}
      <span className="min-w-0 truncate">{fact.name ?? fact.text}</span>
      {fact.name && <span className="shrink-0 whitespace-pre"> → you</span>}
    </span>
  )
}

/** The line while its task is on its way: the same two lines, in outline. */
export function CompactTaskRowPending({ flush = false }: { flush?: boolean }) {
  return (
    <div
      className={cn(
        "border-rule flex gap-3 border-b py-2.5 last:border-b-0",
        flush ? "px-0" : "px-4",
      )}
    >
      <Skeleton className="mt-px size-[1.125rem] shrink-0 rounded-full" />
      <div className="flex flex-1 flex-col gap-1.5">
        <Skeleton className="h-4 w-48 max-w-full" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
  )
}
