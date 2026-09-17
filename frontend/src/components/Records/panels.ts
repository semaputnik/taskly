import { type UseQueryOptions, useQuery } from "@tanstack/react-query"
import { useNavigate, useSearch } from "@tanstack/react-router"
import { useCallback, useEffect, useRef } from "react"
import { z } from "zod"

import type {
  BotUserPublic,
  ProjectPublic,
  TagPublic,
  TaskPublic,
} from "@/client"
import { isRefusal } from "@/lib/apiErrors"
import { botQuery, projectQuery, tagQuery, taskQuery } from "@/lib/serverState"

/**
 * Record panels: every kind of record that opens in a panel, declared once.
 *
 * A panel is addressed by the URL (The Real Address Rule) and only one is
 * open at a time, over whatever screen the reader is on (The Stay-Put Rule).
 * From the one list below come the URL keys and their validation, closing
 * every panel, opening one, what a panel is called while it loads or fails,
 * and every link to a record. A record kind supplies only its own panel body,
 * which renders its capture form if it has one.
 */

/** Records by the kind of panel they open in. */
interface Records {
  task: TaskPublic
  project: ProjectPublic
  tag: TagPublic
  bot: BotUserPublic
}

/** The record types that have a panel of their own. */
export type RecordKind = keyof Records

interface Declared<K extends RecordKind> {
  /** What it is called in a sentence: "This bot user could not be opened". */
  noun: string
  /** How the record is read by id. */
  query: (
    id: string | null,
  ) => UseQueryOptions<
    Records[K],
    Error,
    Records[K],
    (string | null | undefined)[]
  >
  /** The record's own name, which the panel is announced by. */
  nameOf: (record: Records[K]) => string
}

// The URL key each panel is open under. `tag_id` rather than `tag`: the task
// list already narrows by tag *name* under `tag`, and a filter and a panel
// must not share a key.
const KEYS = {
  task: "task",
  project: "project",
  tag: "tag_id",
  bot: "bot",
} as const satisfies Record<RecordKind, string>

type PanelKey = (typeof KEYS)[RecordKind]

export const RECORD_KINDS: { [K in RecordKind]: Declared<K> } = {
  task: { noun: "task", query: taskQuery, nameOf: (task) => task.title },
  project: {
    noun: "project",
    query: projectQuery,
    nameOf: (project) => project.name,
  },
  tag: { noun: "tag", query: tagQuery, nameOf: (tag) => tag.name },
  bot: { noun: "bot user", query: botQuery, nameOf: (bot) => bot.name },
}

/** The record types that are created by naming them in their own panel. */
export const CAPTURE_KINDS = [
  "task",
  "project",
  "tag",
] as const satisfies readonly RecordKind[]
export type CaptureKind = (typeof CAPTURE_KINDS)[number]

const kinds = Object.keys(KEYS) as RecordKind[]
const recordId = z.string().uuid().optional().catch(undefined)

/**
 * Which record has its panel open, and whether one is being created.
 *
 * They live in the URL so a panel can be linked to and so Back closes it, and
 * they are validated by the layout rather than by each screen: the panels are
 * mounted once for the whole app, so every route carries them and a reader
 * who opens a record from the dashboard or the activity log stays where they
 * were. Capture is view state like the open record, so it travels the same
 * way and Back cancels it.
 */
export const panelSearchSchema = z.object({
  ...(Object.fromEntries(kinds.map((kind) => [KEYS[kind], recordId])) as {
    [K in PanelKey]: typeof recordId
  }),
  capture: z.enum(CAPTURE_KINDS).optional().catch(undefined),
})

export type PanelSearch = z.infer<typeof panelSearchSchema>

/** Every panel closed, as search params. */
const NONE = Object.fromEntries(
  Object.keys(panelSearchSchema.shape).map((key) => [key, undefined]),
) as { [K in keyof PanelSearch]: undefined }

/** A link's search, with at most one panel open and the others closed. */
export function panelLink(
  previous: Record<string, unknown>,
  next: PanelSearch,
): Record<string, unknown> {
  return { ...previous, ...NONE, ...next }
}

const opening = (kind: RecordKind, id: string): PanelSearch => ({
  [KEYS[kind]]: id,
})

/**
 * Every link to a record: its panel, over the screen the reader is on, with
 * any other panel closed.
 */
export function recordLink(kind: RecordKind, id: string) {
  return {
    to: "." as const,
    search: (previous: Record<string, unknown>) =>
      panelLink(previous, opening(kind, id)),
  }
}

/**
 * The view state to leave behind when a screen's search becomes an API query.
 *
 * Which panel is open is not a filter. Left in, it lands in the query key, and
 * opening a record silently refetches the list behind the panel and flashes
 * the whole page back to its skeleton.
 */
export function withoutPanelState<T extends Record<string, unknown>>(
  search: T,
): Omit<T, keyof PanelSearch> {
  const rest: Record<string, unknown> = { ...search }
  for (const key of Object.keys(NONE)) delete rest[key]
  return rest as Omit<T, keyof PanelSearch>
}

/**
 * Which record is open, and how to open another. One record is open at a
 * time, so opening any of them clears the rest rather than stacking sheets.
 */
export function useRecordPanels() {
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as PanelSearch & {
    project_id?: string
  }

  const go = useCallback(
    (next: PanelSearch) =>
      navigate({
        to: ".",
        search: (previous: Record<string, unknown>) =>
          panelLink(previous, next),
      }),
    [navigate],
  )
  const open = useCallback(
    (kind: RecordKind, id: string) => go(opening(kind, id)),
    [go],
  )

  return {
    idOf: (kind: RecordKind): string | null => search[KEYS[kind]] ?? null,
    capturing: search.capture,
    /** The project the current list is narrowed to, if it is narrowed at all. */
    filteredProjectId: search.project_id,
    open,
    close: useCallback(() => go({}), [go]),
    openTask: useCallback((id: string) => open("task", id), [open]),
    openProject: useCallback((id: string) => open("project", id), [open]),
    openTag: useCallback((id: string) => open("tag", id), [open]),
    openBot: useCallback((id: string) => open("bot", id), [open]),
    /** Open a panel on a record that does not exist yet. */
    capture: useCallback((kind: CaptureKind) => go({ capture: kind }), [go]),
  }
}

/** How far a panel has got with reading its record. */
export interface RecordLoad {
  /** A request for the record is in flight and nothing is known yet. */
  pending?: boolean
  /**
   * The record cannot be shown. `missing`: the API refused it — deleted, not
   * the reader's, or not an id at all, which it answers alike so that nothing
   * is revealed. `unavailable`: the API did not answer, and it may yet.
   */
  failure?: "missing" | "unavailable"
  /** Ask again now, cutting short any retry already waiting. */
  onRetry?: () => void
}

/**
 * A panel's load state from its record query, for a panel that is `reading`
 * a record rather than capturing one.
 *
 * A failed read has to say so: a skeleton is shown only while a request is
 * really on its way, never for a request that has already failed. A record
 * already on screen stays there through a background refetch that fails.
 */
export function recordLoad(
  query: {
    data: unknown
    isLoading: boolean
    failureCount: number
    failureReason: Error | null
    refetch: () => unknown
  },
  reading: boolean,
): RecordLoad {
  if (!reading) return {}
  // A failure is said as soon as the first attempt fails, even while a
  // failure that may pass is still being retried behind it: the skeleton is
  // only for the first request, genuinely on its way.
  const failed = query.failureCount > 0 && query.data === undefined
  return {
    pending: query.isLoading && !failed,
    failure: !failed
      ? undefined
      : isRefusal(query.failureReason)
        ? "missing"
        : "unavailable",
    onRetry: () => void query.refetch(),
  }
}

const capitalised = (noun: string) => noun[0].toUpperCase() + noun.slice(1)

/**
 * One kind's panel: whether it is open, on which record or on a capture, the
 * record itself, and the props for its `RecordPanel` shell.
 */
export function useRecordPanel<K extends RecordKind>(kind: K) {
  const panels = useRecordPanels()
  const declared = RECORD_KINDS[kind]
  const id = panels.idOf(kind)
  // Capture is the panel one step earlier, so it opens the same surface. The
  // record itself is only read once there is one.
  const capturing = panels.capturing === kind && !id
  const query = useQuery(declared.query(id))
  const record = query.data
  const noun = capitalised(declared.noun)

  return {
    id,
    capturing,
    record,
    panels,
    shell: {
      open: Boolean(id) || capturing,
      onClose: panels.close,
      name: capturing
        ? `New ${declared.noun}`
        : record
          ? declared.nameOf(record)
          : noun,
      kind: declared.noun,
      ...recordLoad(query, !capturing && Boolean(id)),
    },
  }
}

/**
 * Put focus on a capture field as its panel opens.
 *
 * Done here rather than through `autoFocus`, which a sheet's own opening focus
 * would win against. It is claimed twice: on a phone the sidebar is a sheet of
 * its own, and it hands focus back to the button that opened capture as it
 * finishes closing, a moment after this panel arrives.
 */
export function useCaptureFocus<T extends HTMLElement>(enabled = true) {
  const ref = useRef<T>(null)
  useEffect(() => {
    if (!enabled) return
    const frame = requestAnimationFrame(() => ref.current?.focus())
    const settled = setTimeout(() => {
      if (document.activeElement !== ref.current) ref.current?.focus()
    }, 350)
    return () => {
      cancelAnimationFrame(frame)
      clearTimeout(settled)
    }
  }, [enabled])
  return ref
}
