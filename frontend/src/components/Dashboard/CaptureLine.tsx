import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { ArrowUp, Plus } from "lucide-react"
import { useId, useLayoutEffect, useRef, useState } from "react"

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
import { useVisualViewport } from "@/hooks/useVisualViewport"
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
 * On a phone the line leaves the top of the page and is pinned to the bottom
 * of the screen, where a thumb rests (FR-06.15). It follows the visual
 * viewport, so it rides above Safari's own bar and above the keyboard while
 * one is up (`useVisualViewport`); the list scrolls under it with a short
 * fade; its matches open upward; and while a record's column covers the
 * screen it is not there at all.
 *
 * `opens` fixes the side the matches open on. Left alone, a phone's open
 * upward and a wider screen's toward whichever side of the line has the room.
 */
export function CaptureLine({ opens }: { opens?: "down" | "up" }) {
  const panels = useRecordPanels()
  const phone = useIsPhone()
  const bar = useRef<HTMLDivElement>(null)
  useVisualViewport(bar, phone)
  const side = opens ?? (phone ? "up" : undefined)
  const undo = useUndoCapture()
  const [title, setTitle] = useState("")
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
    if (!open) return
    if (side) return setUpward(side === "up")
    const line = wrapper.current?.getBoundingClientRect()
    if (!line) return
    setUpward(
      opensUpward(
        line,
        window.visualViewport?.height ?? window.innerHeight,
        MATCHES_HEIGHT,
      ),
    )
  }, [open, side])

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
  }

  const openMatch = (task: Pick<TaskPublic, "id">) => {
    // The task was found: the search is over, and the line is free again.
    setTitle("")
    setActiveId(null)
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

  return (
    <div
      ref={bar}
      className={cn(
        // Pinned on a phone: the ground and a hairline over the list, the
        // keyboard's height as its offset, the home indicator's as its foot
        // (which a keyboard covers, so it counts for nothing then).
        "max-md:bg-page max-md:border-rule-strong max-md:focus-within:border-ink max-md:fixed max-md:inset-x-0 max-md:bottom-[var(--kb-inset,0px)] max-md:z-30 max-md:border-t max-md:px-4 max-md:pb-[max(0px,calc(env(safe-area-inset-bottom)-var(--kb-inset,0px)))]",
        "max-md:group-has-[[data-record-column]]/shell:hidden",
      )}
    >
      {/* The list's last lines fade out under the pinned line. */}
      <div
        aria-hidden
        className="to-page pointer-events-none absolute inset-x-0 bottom-full h-7 bg-linear-to-b from-transparent md:hidden"
      />
      <div ref={wrapper} className="relative">
        <label className="text-ink-3 border-rule-strong focus-within:border-ink flex h-10 items-center gap-2.5 border-b transition-colors max-md:h-[52px] max-md:border-b-0">
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
            // 16px on a phone: iOS zooms the page in to any field set smaller.
            className="text-ink placeholder:text-ink-3 h-full min-w-0 flex-1 bg-transparent text-[15px] outline-none max-md:text-base"
          />
          {/* The key works from every screen; the cap is for a keyboard, so a
            touch screen, which has none, goes without it. */}
          <kbd
            aria-hidden
            className="border-rule-strong rounded border px-[5px] font-mono text-[11px] leading-4 pointer-coarse:hidden"
          >
            C
          </kbd>
          {/* A phone's keyboard has a Return key, but a thumb is surer of a
            button. It keeps focus where it is, so the keyboard stays up. */}
          {title.trim() && (
            <button
              type="button"
              aria-label="Create task"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => void commit()}
              className="-mr-1.5 grid size-11 shrink-0 place-items-center md:hidden"
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

        {open && term && (
          <div
            className={cn(
              "bg-popover border-rule-strong absolute inset-x-0 z-20 rounded-lg border py-1.5 shadow-md max-md:max-h-[calc(var(--vv-height,100svh)-8rem)] max-md:overflow-y-auto",
              upward ? "bottom-full mb-2" : "top-full mt-1.5",
            )}
          >
            <div className="text-ink-3 truncate px-3.5 pt-1.5 pb-1 text-[12.5px]">
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
                    onChoose={() => openMatch(task)}
                  />
                ))}
              </div>
            )}
            <div className="text-ink-3 border-rule mt-1 flex flex-wrap justify-between gap-x-3 gap-y-1 border-t px-3.5 pt-2 pb-1 text-xs">
              <span className="min-w-0">
                <KeyCap className="pointer-coarse:hidden">↵</KeyCap>
                <span className="hidden pointer-coarse:inline">Return</span>{" "}
                creates “
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
          </div>
        )}
      </div>
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
  onChoose,
}: {
  id: string
  task: TaskPublic
  term: string
  projectName?: string
  selected: boolean
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
        "hover:bg-hover flex cursor-pointer items-center gap-3 px-3.5 py-2.5 text-[15px] md:py-2 md:text-sm",
        selected && "bg-hover",
      )}
    >
      <StatusMark status={task.status} priority={task.priority} />
      {/* The project follows the title on a phone, where the line is narrow,
          and sits at the right edge beside a desktop's wider one. */}
      <span className="min-w-0 truncate font-medium md:flex-1">
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
