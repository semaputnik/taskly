import { useNavigate, useSearch } from "@tanstack/react-router"
import { useCallback } from "react"

/** The record types that have a panel of their own. */
export type RecordKind = "task" | "project" | "tag" | "bot"

/** The record types that are created by naming them in their own panel. */
export type CaptureKind = "task" | "project" | "tag"

type PanelSearch = {
  task?: string
  project?: string
  /** The tag panel's record: `tag` is the task list's filter by name. */
  tag_id?: string
  bot?: string
  capture?: CaptureKind
  /** Not a panel: the list's project filter, which capture reads. */
  project_id?: string
}

const NONE: PanelSearch = {
  task: undefined,
  project: undefined,
  tag_id: undefined,
  bot: undefined,
  capture: undefined,
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
): Omit<T, keyof typeof NONE> {
  const { task, project, tag_id, bot, capture, ...rest } = search
  return rest as Omit<T, keyof typeof NONE>
}

/**
 * Which record is open, and how to open another.
 *
 * Every panel is addressed by its record's id in the URL, on whatever route
 * the reader is already on: a record can be linked to, Back closes it, and
 * opening one never moves anybody to another screen (The Real Address Rule,
 * The Stay-Put Rule). One record is open at a time, so opening any of them
 * clears the rest rather than stacking sheets.
 */
export function useRecordPanels() {
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as PanelSearch

  const go = useCallback(
    (next: PanelSearch) =>
      navigate({
        to: ".",
        search: (previous: Record<string, unknown>) => ({
          ...previous,
          ...NONE,
          ...next,
        }),
      }),
    [navigate],
  )

  return {
    taskId: search.task ?? null,
    projectId: search.project ?? null,
    tagId: search.tag_id ?? null,
    botId: search.bot ?? null,
    capturing: search.capture,
    /** The project the current list is narrowed to, if it is narrowed at all. */
    filteredProjectId: search.project_id,
    close: useCallback(() => go({}), [go]),
    openTask: useCallback((task: string) => go({ task }), [go]),
    openProject: useCallback((project: string) => go({ project }), [go]),
    openTag: useCallback((tag: string) => go({ tag_id: tag }), [go]),
    openBot: useCallback((bot: string) => go({ bot }), [go]),
    /** Open a panel on a record that does not exist yet. */
    capture: useCallback((kind: CaptureKind) => go({ capture: kind }), [go]),
  }
}
