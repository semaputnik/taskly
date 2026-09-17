import { useQuery } from "@tanstack/react-query"
import { useBlocker } from "@tanstack/react-router"
import { useEffect, useRef, useState } from "react"

import { ProjectsService, type TaskPublic } from "@/client"
import {
  ghost,
  RecordHeader,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { type CaptureTarget, useTaskCapture } from "./capture"
import { carryOver, emptyDraft, isTouched, type TaskFields } from "./draft"
import { DescriptionSection, TaskPropertyRows } from "./TaskProperties"

// The commit chord, named the way the reader's keyboard names it.
const CHORD =
  typeof navigator !== "undefined" &&
  /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)
    ? "⌘ Enter"
    : "Ctrl Enter"

/**
 * The panel before the record exists: the task's own layout, as a draft.
 *
 * Every property a task has at creation is on screen and editable from the
 * first frame, in the rows and order of the task's panel, so what the reader
 * already knows — a day, a priority, a tag, another project — goes in at the
 * moment of capture, and nothing moves when the task is created. Only what a
 * record alone has (its status, when it was created, its comments, subtasks
 * and files) waits for the record.
 *
 * Nothing here is written as it changes. There is one explicit, visible
 * commit — Enter in the title, or Create task — and it sends the whole draft
 * as one request. ⌘/Ctrl+Enter from anywhere in the panel commits and keeps
 * capturing, carrying the properties over to the next draft. Because the
 * draft lives only here, closing one that holds something asks first, however
 * the panel is being closed.
 */
export function NewTask({
  target,
  onCreated,
}: {
  target: CaptureTarget
  onCreated: (task: TaskPublic, stay: boolean) => void
}) {
  const capture = useTaskCapture(target, onCreated)
  const [defaults, setDefaults] = useState(() => emptyDraft(target))
  const [draft, setDraft] = useState(defaults)
  const touched = isTouched(draft, defaults)
  const titleRef = useRef<HTMLInputElement>(null)
  // Set while a commit is taking the reader onto the new record, which is a
  // way of leaving the draft that loses nothing.
  const leaving = useRef(false)

  // The list's project filter can arrive after the panel does; until the
  // reader has chosen a project, the draft follows it.
  const [followedProject, setFollowedProject] = useState(target.projectId)
  if (followedProject !== target.projectId) {
    const previous = followedProject
    setFollowedProject(target.projectId)
    setDefaults((current) => ({ ...current, project_id: target.projectId }))
    setDraft((current) =>
      current.project_id === previous
        ? { ...current, project_id: target.projectId }
        : current,
    )
  }

  // Focused from here rather than through `autoFocus`, which a sheet's own
  // opening focus would win against. It is claimed twice: on a phone the
  // sidebar is a sheet of its own, and it hands focus back to the button that
  // opened capture as it finishes closing, a moment after this panel arrives.
  useEffect(() => {
    const frame = requestAnimationFrame(() => titleRef.current?.focus())
    const settled = setTimeout(() => {
      if (document.activeElement !== titleRef.current) {
        titleRef.current?.focus()
      }
    }, 350)
    return () => {
      cancelAnimationFrame(frame)
      clearTimeout(settled)
    }
  }, [])

  // Every way out goes through the address — Escape, the close button, a
  // click outside, Back, a link — so the question is asked there, and the
  // navigation waits for the answer.
  const guarded = useRef(false)
  guarded.current = touched
  const [asking, setAsking] = useState(false)
  const answer = useRef<((stay: boolean) => void) | null>(null)
  // The Escape that answers "Keep editing" can also reach the panel, in the
  // same key press. It is held without asking again until that press is over.
  const justKept = useRef(false)
  useBlocker({
    shouldBlockFn: ({ next }) => {
      if (!guarded.current || leaving.current) return false
      if ((next.search as { capture?: string }).capture === "task") {
        return false
      }
      // Asked to leave again while the question is up — the same Escape
      // reaching the panel before the question — is keeping the draft.
      if (answer.current) {
        answer.current(true)
        return true
      }
      if (justKept.current) return true
      setAsking(true)
      return new Promise<boolean>((resolve) => {
        answer.current = (stay) => {
          answer.current = null
          setAsking(false)
          resolve(stay)
        }
      })
    },
    enableBeforeUnload: () => guarded.current && !leaving.current,
  })

  // Unset already means the Inbox to the API, so choosing the Inbox is kept
  // as unset: picking what is already shown is not a change to the draft.
  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () =>
      (await ProjectsService.readProjects({ query: { skip: 0, limit: 100 } }))
        .data,
  })
  const inboxId = projects?.data.find((project) => project.is_inbox)?.id
  const change = (patch: Partial<TaskFields>) =>
    setDraft((previous) => ({
      ...previous,
      ...patch,
      ...("project_id" in patch && patch.project_id === inboxId
        ? { project_id: undefined }
        : {}),
    }))

  const commit = async (stay: boolean) => {
    const sent = draft
    if (!sent.title.trim()) return
    if (stay) {
      const next = carryOver(sent)
      setDefaults(next)
      setDraft(next)
      titleRef.current?.focus()
    } else {
      leaving.current = true
    }
    const accepted = await capture.create(sent, stay)
    if (accepted) return
    // A refusal keeps the whole draft. After a run's capture the title and
    // description come back, unless something new has been typed there.
    leaving.current = false
    if (stay) {
      setDraft((current) =>
        current.title === "" && current.description === ""
          ? { ...current, title: sent.title, description: sent.description }
          : current,
      )
    }
  }

  // The chord works from every field in the panel, the description
  // included, where plain Enter is a new line.
  const panel = useRef<HTMLDivElement>(null)
  const commitRef = useRef(commit)
  commitRef.current = commit
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Enter" || !(event.metaKey || event.ctrlKey)) return
      event.preventDefault()
      void commitRef.current(true)
    }
    const node = panel.current
    node?.addEventListener("keydown", onKeyDown)
    return () => node?.removeEventListener("keydown", onKeyDown)
  }, [])

  return (
    <div ref={panel} className="flex min-h-full flex-1 flex-col">
      <RecordHeader
        breadcrumb={
          <>
            <span className="shrink-0">New task</span>
            <span aria-hidden>·</span>
            <span className="truncate">Not saved yet</span>
          </>
        }
        title={
          <Input
            ref={titleRef}
            aria-label="Task title"
            placeholder="What needs doing?"
            value={draft.title}
            onChange={(event) =>
              setDraft((previous) => ({
                ...previous,
                title: event.target.value,
              }))
            }
            onKeyDown={(event) => {
              if (event.key !== "Enter" || event.metaKey || event.ctrlKey) {
                return
              }
              event.preventDefault()
              void commit(false)
            }}
            className={cn(
              "border-transparent bg-transparent shadow-none dark:bg-transparent",
              titleFieldClass,
            )}
          />
        }
      />

      <TaskPropertyRows
        fields={draft}
        onChange={change}
        isSubtask={Boolean(target.parentId)}
        defaultProjectName={target.projectName}
      />

      <DescriptionSection>
        <Textarea
          aria-label="Task description"
          placeholder="Add a description"
          rows={3}
          value={draft.description}
          onChange={(event) =>
            setDraft((previous) => ({
              ...previous,
              description: event.target.value,
            }))
          }
          className={ghost}
        />
      </DescriptionSection>

      {/* The one commit, pinned where a thumb reaches it. */}
      <div className="bg-card sticky bottom-0 mt-auto flex items-center justify-end gap-3 border-t px-6 py-3">
        <span className="text-muted-foreground text-xs">
          <kbd className="font-sans">{CHORD}</kbd> creates and starts another
        </span>
        <Button
          disabled={!draft.title.trim()}
          onClick={() => void commit(false)}
          className="pointer-coarse:h-11"
        >
          Create task
        </Button>
      </div>

      <output aria-live="polite" className="sr-only">
        {capture.announcement}
      </output>

      <DiscardDialog
        open={asking}
        onKeep={() => {
          justKept.current = true
          setTimeout(() => {
            justKept.current = false
          })
          answer.current?.(true)
        }}
        onDiscard={() => {
          // The draft is given up: whatever carries the reader away now goes
          // without asking again.
          leaving.current = true
          answer.current?.(false)
        }}
      />
    </div>
  )
}

function DiscardDialog({
  open,
  onKeep,
  onDiscard,
}: {
  open: boolean
  onKeep: () => void
  onDiscard: () => void
}) {
  const keep = useRef<HTMLButtonElement>(null)

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onKeep()}>
      <DialogContent
        className="sm:max-w-md"
        // The safe choice is the one in hand: Enter keeps the draft.
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          keep.current?.focus()
        }}
      >
        <DialogHeader>
          <DialogTitle>Discard this task?</DialogTitle>
          <DialogDescription>
            It has not been saved. Discarding it throws away what you have
            written and set here.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onDiscard}>
            Discard
          </Button>
          <Button ref={keep} onClick={onKeep}>
            Keep editing
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
