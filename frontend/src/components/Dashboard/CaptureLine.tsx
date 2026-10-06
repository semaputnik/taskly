import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { ArrowUp, Plus } from "lucide-react"
import { type ReactNode, useId, useLayoutEffect, useRef, useState } from "react"

import type { TaskPublic } from "@/client"
import { useRecordPanels } from "@/components/Records/panels"
import { useCaptureTarget } from "@/components/Tasks/capture"
import { StatusMark } from "@/components/Tasks/status"
import { OPEN_STATUSES } from "@/components/Tasks/statuses"
import {
  useTaskCapture,
  useUndoCapture,
} from "@/components/Tasks/useTaskWrites"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { useIsPhone } from "@/hooks/useIsPhone"
import { projectsQuery, taskTitleSearchQuery } from "@/lib/serverState"
import { toastCreated } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import {
  MAX_MATCHES,
  matchesFor,
  opensUpward,
  searchTerm,
  stepActive,
  titleParts,
} from "./captureSearch"

/** How long typing has to pause before the open tasks are asked for. */
const SEARCH_DELAY_MS = 200

/** About what eight matches, their heading and their hints take up. */
const MATCHES_HEIGHT = 360

/**
 * What the capture sheet hands the line it carries: the words it keeps while
 * it is closed, what to do once the line has made or opened a task, and what
 * its "More options…" line does.
 */
export interface SheetBinding {
  title: string
  setTitle: (title: string) => void
  /** The line made a task, or opened one it found: the sheet is done. */
  onDone: () => void
  /** "More options…": on to the full draft. */
  onMore: () => void
}

/**
 * The frameless line at the top of a page that a task is written into: a
 * plus, the field, and the key cap that does the same from anywhere.
 *
 * It writes into the project the page is narrowed to, and says so — "Add a
 * task to Website relaunch…" — and into the Inbox otherwise (FR-05.4,
 * FR-06.15). The day page is narrowed to no project, so there it is always
 * the Inbox.
 *
 * Enter makes the task at once. A title alone is a complete task — Backlog,
 * in the project it is written into, nothing else set — and it is one create
 * request, so nothing is held back for a second step (ADR-0005, amended). The
 * line empties for the next thought and a notice names what was made, with
 * Open (its panel) and Undo (which deletes it; the deletion is restorable
 * from the activity log). A task that needs a day, a priority or another
 * project before it exists is written in the full draft, which the `c` key
 * opens.
 *
 * It also searches. Once two characters are typed, the open tasks whose title
 * contains them are offered under the line, each as a task line in miniature
 * (FR-06.14). Typing on is not interrupted: Enter still creates, and only the
 * arrow keys, which move through the matches, make Enter open one instead.
 * The field is a combobox over a listbox, so a screen reader hears the count
 * of matches and which one is chosen.
 *
 * A phone has no line on its pages: the add control in the bottom bar raises
 * a capture sheet carrying this same line (FR-06.15, `CaptureSheet`). Given
 * a `sheet`, the line sits at the foot of it, its matches are part of the
 * sheet and stand above the line rather than floating, and a "More options…"
 * line leads on to the full draft.
 *
 * `opens` fixes the side the matches open on. Left alone, they open toward
 * whichever side of the line has the room.
 */
export function CaptureLine({
  opens,
  sheet,
}: {
  opens?: "down" | "up"
  sheet?: SheetBinding
}) {
  const panels = useRecordPanels()
  const undo = useUndoCapture()
  // In the sheet the words belong to the sheet, which outlives the line: one
  // closed with Escape keeps them for the next time it is raised.
  const [own, setOwn] = useState("")
  const title = sheet ? sheet.title : own
  const setTitle = (next: string | ((now: string) => string)) => {
    const value = typeof next === "function" ? next(title) : next
    if (sheet) sheet.setTitle(value)
    else setOwn(value)
  }
  const target = useCaptureTarget()
  // A page narrowed to a project knows the project's name only once the
  // projects have come: words committed before then would go to the Inbox
  // under a line that already says the project's name. The line holds them
  // until it knows where they go.
  const { data: projects, isPending: projectsPending } = useQuery(
    projectsQuery(),
  )
  const settling = Boolean(panels.filteredProjectId) && projectsPending
  const capture = useTaskCapture(target, (task) =>
    toastCreated(`“${task.title}” created in ${target.projectName}`, {
      open: () => panels.openTask(task.id),
      undo: () => void undo(task),
    }),
  )
  const where = target.projectId ? ` to ${target.projectName}` : ""

  // The search. Typing is debounced so a fast typist does not make a request
  // per key; the answer carries the text it is for, and what is shown is
  // worked out from that against the text now (see `matchesFor`), so an
  // answer that arrives late never displaces a newer one.
  const listId = useId()
  const wrapper = useRef<HTMLDivElement>(null)
  const term = searchTerm(title)
  const settled = useDebouncedValue(term, SEARCH_DELAY_MS)
  const { data: answer } = useQuery({
    ...taskTitleSearchQuery(settled ?? "", {
      status: OPEN_STATUSES,
      limit: MAX_MATCHES,
    }),
    enabled: settled !== null && term !== null,
    placeholderData: keepPreviousData,
  })
  const { tasks: matches, current } = matchesFor(title, answer)
  const [focused, setFocused] = useState(false)
  // Escape closes the matches and keeps the text; they stay closed until the
  // text changes, whatever it changes to.
  const [dismissed, setDismissed] = useState(false)
  // The highlighted match is held by its task, not its place: an answer that
  // reorders the list never moves the highlight on to another task.
  const [activeId, setActiveId] = useState<string | null>(null)
  const open =
    focused && term !== null && !dismissed && (matches.length > 0 || current)

  // Which side the matches open on is decided as they appear, not while they
  // are typed into: a list that flipped between keystrokes would be a jump.
  const [upward, setUpward] = useState(false)
  useLayoutEffect(() => {
    if (!open || sheet) return
    if (opens) return setUpward(opens === "up")
    const line = wrapper.current?.getBoundingClientRect()
    if (!line) return
    setUpward(
      opensUpward(
        line,
        window.visualViewport?.height ?? window.innerHeight,
        MATCHES_HEIGHT,
      ),
    )
  }, [open, opens, sheet])

  const projectNames = Object.fromEntries(
    (projects?.data ?? []).map((project) => [project.id, project.name]),
  )

  const commit = async () => {
    const typed = title.trim()
    if (!typed || settling) return
    // The line is free for the next thought while this one is on its way.
    setTitle("")
    // The same title again while it is still being written is the one refusal
    // that says nothing: the task is already on its way, so the words do not
    // come back.
    if (capture.isSending(typed)) return
    const created = await capture.create(typed, false)
    // A refusal says why in its own notice; the words come back unless the
    // reader has already started the next ones.
    if (!created) setTitle((now) => now || typed)
    // The sheet has done its work, and would hold the notice's Open and Undo
    // out of reach beneath its own scrim.
    else sheet?.onDone()
  }

  const openMatch = (task: Pick<TaskPublic, "id">) => {
    // The task was found: the search is over, and the line is free again.
    setTitle("")
    setActiveId(null)
    sheet?.onDone()
    panels.openTask(task.id)
  }

  // A newer answer that no longer holds the highlighted task ends the
  // highlight. It is not only hidden: left set, it would come back on the
  // task if a later answer listed it again, and Enter would open a task the
  // reader had not chosen.
  if (activeId !== null && !matches.some((task) => task.id === activeId)) {
    setActiveId(null)
  }
  const active = open ? matches.findIndex((task) => task.id === activeId) : -1
  const chosen = active >= 0 ? matches[active] : undefined
  const optionId = (index: number) => `${listId}-${index}`
  const heading = term ? `Open tasks matching “${term}”` : ""

  const results = open && term && (
    <div
      className={cn(
        sheet
          ? "max-h-[calc(var(--vv-height,100svh)-9.5rem)] overflow-y-auto overscroll-contain"
          : "bg-popover border-rule-strong absolute inset-x-0 z-20 rounded-lg border py-1.5 shadow-md",
        !sheet && (upward ? "bottom-full mb-2" : "top-full mt-1.5"),
      )}
    >
      <div
        className={cn(
          "text-ink-3 truncate pt-1.5 pb-1 text-[12.5px]",
          !sheet && "px-3.5",
        )}
      >
        {matches.length === 0
          ? `No open task has “${term}” in its title`
          : heading}
      </div>
      {matches.length > 0 && (
        <div id={listId} role="listbox" aria-label={heading}>
          {matches.map((task, index) => (
            <Match
              key={task.id}
              id={optionId(index)}
              task={task}
              term={term}
              projectName={projectNames[task.project_id]}
              selected={index === active}
              inSheet={Boolean(sheet)}
              onChoose={() => openMatch(task)}
            />
          ))}
        </div>
      )}
      {!sheet && (
        <div className="text-ink-3 border-rule mt-1 flex flex-wrap justify-between gap-x-3 gap-y-1 border-t px-3.5 pt-2 pb-1 text-xs">
          <span className="min-w-0">
            <KeyCap className="pointer-coarse:hidden">↵</KeyCap>
            <span className="hidden pointer-coarse:inline">Return</span> creates
            “
            <span className="inline-block max-w-40 truncate align-bottom">
              {title.trim()}
            </span>
            ” in {target.projectName}
          </span>
          <span className="shrink-0 pointer-coarse:hidden">
            <KeyCap>↑</KeyCap>
            <KeyCap>↓</KeyCap> then <KeyCap>↵</KeyCap> opens a match
          </span>
          <span className="hidden shrink-0 pointer-coarse:inline">
            Tap a match to open it
          </span>
        </div>
      )}
    </div>
  )

  return (
    <div>
      {/* In the sheet the matches are in the flow, above the line. */}
      {sheet && results}
      <div ref={wrapper} className="relative">
        <label
          className={cn(
            "text-ink-3 flex items-center gap-2.5 transition-colors",
            sheet
              ? "h-[52px]"
              : "border-rule-strong focus-within:border-ink h-10 border-b",
          )}
        >
          <Plus aria-hidden className="size-4 shrink-0" strokeWidth={1.5} />
          <input
            type="text"
            role="combobox"
            aria-expanded={open}
            aria-controls={open && matches.length > 0 ? listId : undefined}
            aria-activedescendant={chosen ? optionId(active) : undefined}
            aria-autocomplete="list"
            autoComplete="off"
            aria-label={`Add a task${where}`}
            placeholder={`Add a task${where}…`}
            value={title}
            onChange={(event) => {
              setTitle(event.target.value)
              setDismissed(false)
              setActiveId(null)
            }}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(event) => {
              if (event.nativeEvent.isComposing) return
              if (event.key === "Escape" && open) {
                // Closes the matches and nothing else: the text stays, and the
                // column behind the page does not hear this Escape.
                event.preventDefault()
                setDismissed(true)
                setActiveId(null)
                return
              }
              if (
                (event.key === "ArrowDown" || event.key === "ArrowUp") &&
                open &&
                matches.length > 0
              ) {
                // The record column walks its list with these keys when focus
                // is not in a field; here they walk the matches instead.
                event.preventDefault()
                const key = event.key
                setActiveId(
                  matches[stepActive(active, matches.length, key)]?.id ?? null,
                )
                return
              }
              if (event.key !== "Enter") return
              event.preventDefault()
              if (chosen) openMatch(chosen)
              else void commit()
            }}
            // 16px in the sheet: iOS zooms the page in to any field set smaller.
            className={cn(
              "text-ink placeholder:text-ink-3 h-full min-w-0 flex-1 bg-transparent text-[15px] outline-none",
              sheet && "text-base",
            )}
          />
          {/* The key works from every screen; the cap is for a keyboard, so a
            touch screen, which has none, goes without it. */}
          {!sheet && (
            <kbd
              aria-hidden
              className="border-rule-strong rounded border px-[5px] font-mono text-[11px] leading-4 pointer-coarse:hidden"
            >
              C
            </kbd>
          )}
          {/* A phone's keyboard has a Return key, but a thumb is surer of a
            button. It keeps focus where it is, so the keyboard stays up. */}
          {sheet && title.trim() && (
            <button
              type="button"
              aria-label="Create task"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => void commit()}
              className="-mr-1.5 grid size-11 shrink-0 place-items-center"
            >
              <span className="bg-ink text-page grid size-8 place-items-center rounded-full">
                <ArrowUp aria-hidden className="size-4" strokeWidth={1.8} />
              </span>
            </button>
          )}
        </label>

        {/* Said whenever the matches change, whether or not they can be seen. */}
        <div role="status" className="sr-only">
          {open &&
            current &&
            (matches.length === 0
              ? "No open task matches"
              : `${matches.length} open ${matches.length === 1 ? "task matches" : "tasks match"}`)}
        </div>

        {!sheet && results}
      </div>
      {sheet && (
        <SheetFoot
          typed={title.trim()}
          project={target.projectName}
          onMore={sheet.onMore}
        />
      )}
    </div>
  )
}

/**
 * The foot of the capture sheet: what Return will do, and the way into the
 * full draft for a task that needs more than a title.
 */
function SheetFoot({
  typed,
  project,
  onMore,
}: {
  typed: string
  project: string
  onMore: () => void
}): ReactNode {
  return (
    <div className="text-ink-3 flex min-h-11 items-center justify-between gap-3 text-xs">
      <span className="min-w-0 truncate">
        {typed
          ? `Return creates “${typed}” in ${project}`
          : `Goes to ${project}`}
      </span>
      <button
        type="button"
        onMouseDown={(event) => event.preventDefault()}
        onClick={onMore}
        className="text-ink focus-visible:outline-ink -mr-2 inline-flex h-11 shrink-0 items-center rounded-md px-2 text-[13.5px] font-medium underline-offset-4 hover:underline focus-visible:outline-2"
      >
        More options…
      </button>
    </div>
  )
}

/** A key named in a hint: the outlined cap of the design system. */
function KeyCap({
  className,
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <kbd
      className={cn(
        "border-rule-strong mx-px rounded border px-[5px] font-mono text-[11px] leading-4",
        className,
      )}
    >
      {children}
    </kbd>
  )
}

/**
 * A match: the task line in miniature — its status mark, its title with the
 * searched text in bold, and its project. A pointer press is kept from taking
 * focus off the field, so choosing a match never closes the list before the
 * click lands.
 */
function Match({
  id,
  task,
  term,
  projectName,
  selected,
  inSheet,
  onChoose,
}: {
  id: string
  task: TaskPublic
  term: string
  projectName?: string
  selected: boolean
  inSheet: boolean
  onChoose: () => void
}) {
  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: the keys belong to the field, which owns focus
    <div
      id={id}
      role="option"
      // Not in the tab order: the field keeps focus and names the chosen
      // match with aria-activedescendant.
      tabIndex={-1}
      aria-selected={selected}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onChoose}
      className={cn(
        "hover:bg-hover flex cursor-pointer items-center gap-3 py-2.5 text-[15px]",
        inSheet ? "border-rule min-h-11 border-b" : "px-3.5 md:py-2 md:text-sm",
        selected && "bg-hover",
      )}
    >
      <StatusMark status={task.status} priority={task.priority} />
      {/* The project follows the title in the sheet, where the line is
          narrow, and sits at the right edge beside a desktop's wider one. */}
      <span
        className={cn("min-w-0 truncate font-medium", !inSheet && "md:flex-1")}
      >
        {titleParts(task.title, term).map((part, index) =>
          part.match ? (
            <b key={index} className="font-bold">
              {part.text}
            </b>
          ) : (
            <span key={index}>{part.text}</span>
          ),
        )}
      </span>
      {projectName && (
        <span className="text-ink-3 max-w-[45%] shrink-[100] truncate text-[12.5px] md:max-w-56">
          <span className="sr-only">Project: </span>
          {projectName}
        </span>
      )}
    </div>
  )
}

/**
 * The capture line a page carries at its top. A phone has none: its add
 * control raises the capture sheet instead (FR-06.15).
 */
export function PageCaptureLine({ className }: { className?: string }) {
  const phone = useIsPhone()
  if (phone) return null
  return (
    <div className={className}>
      <CaptureLine />
    </div>
  )
}
