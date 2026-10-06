import type { ComponentType } from "react"

import type { RecordKind } from "./panels"

/**
 * Each record kind's panel body — which holds its capture form if it has
 * one — fetched the first time it is needed rather than with every page.
 *
 * The panels are mounted for the whole authenticated app, but a page is
 * read before any of them opens, and together they weigh about a sixth of
 * what the first screen downloads. They are fetched when the browser is idle
 * after the page, or at once when the address already has one open.
 */
const IMPORTS: Record<RecordKind, () => Promise<ComponentType>> = {
  task: () => import("@/components/Tasks/TaskDetail").then((m) => m.TaskDetail),
  project: () =>
    import("@/components/Projects/ProjectPanel").then((m) => m.ProjectPanel),
  tag: () => import("@/components/Tags/TagPanel").then((m) => m.TagPanel),
  bot: () => import("@/components/Bots/BotPanel").then((m) => m.BotPanel),
}

/**
 * A panel body on its way, marked as React reads a promise it is handed:
 * once it has arrived, `use` returns it in the same render instead of
 * suspending, so a panel whose code is already here opens at once.
 */
type Arriving = Promise<ComponentType> & {
  status?: "fulfilled"
  value?: ComponentType
}

const arriving: Partial<Record<RecordKind, Arriving>> = {}

/**
 * A kind's panel body, fetched once. A fetch that fails is forgotten, so the
 * next time the panel is needed it is asked for again.
 */
export function panelModule(kind: RecordKind): Promise<ComponentType> {
  const known = arriving[kind]
  if (known) return known
  const promise: Arriving = IMPORTS[kind]().then(
    (Panel) => {
      promise.status = "fulfilled"
      promise.value = Panel
      return Panel
    },
    (error: unknown) => {
      delete arriving[kind]
      throw error
    },
  )
  arriving[kind] = promise
  return promise
}

/** Start fetching a kind's panel body, with nothing waiting on it. */
export function preloadPanel(kind: RecordKind) {
  panelModule(kind).catch(() => {})
}
