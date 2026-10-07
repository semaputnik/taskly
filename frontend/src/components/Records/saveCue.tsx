import {
  createContext,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
} from "react"

import { cn } from "@/lib/utils"

/**
 * The column's word about its last save.
 *
 * A field in a record saves where it is edited, with nothing to press, so
 * without a word from the column a good save and a lost one look the same.
 * Success is a quiet "Saved" in the bar that fades on its own; a refusal is
 * "Couldn't save: <reason>", which stays until the next edit, so it cannot be
 * missed by looking away. Both are said through one polite live region.
 */

/** How long "Saved" holds before it starts to fade, and how long the fade is. */
const HOLD_MS = 1_800
const FADE_MS = 300

interface CueState {
  text: string
  tone: "saved" | "failed" | null
  fading: boolean
}

const IDLE: CueState = { text: "", tone: null, fading: false }

export interface SaveCueStore {
  subscribe: (listener: () => void) => () => void
  getSnapshot: () => CueState
  /** A field was saved. */
  saved: () => void
  /** A field was refused, and why, in the API's words. */
  failed: (reason: string) => void
  dispose: () => void
}

export function createSaveCue(): SaveCueStore {
  let state = IDLE
  const listeners = new Set<() => void>()
  let hold: ReturnType<typeof setTimeout> | undefined
  let fade: ReturnType<typeof setTimeout> | undefined

  const set = (next: CueState) => {
    state = next
    for (const listener of listeners) listener()
  }
  const stop = () => {
    clearTimeout(hold)
    clearTimeout(fade)
  }

  return {
    subscribe: (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    getSnapshot: () => state,
    saved: () => {
      stop()
      set({ text: "Saved", tone: "saved", fading: false })
      hold = setTimeout(() => {
        set({ ...state, fading: true })
        fade = setTimeout(() => set(IDLE), FADE_MS)
      }, HOLD_MS)
    },
    failed: (reason) => {
      stop()
      set({ text: `Couldn't save: ${reason}`, tone: "failed", fading: false })
    },
    dispose: stop,
  }
}

const SaveCueContext = createContext<SaveCueStore | null>(null)

/** Gives a record's column one cue, which its fields report to and its bar shows. */
export function SaveCueProvider({ children }: { children: React.ReactNode }) {
  const [store] = useState(createSaveCue)
  useEffect(() => store.dispose, [store])
  return <SaveCueContext value={store}>{children}</SaveCueContext>
}

/** The column's cue, or nothing where there is no column, as in a list row. */
export function useSaveCue(): SaveCueStore | null {
  return useContext(SaveCueContext)
}

/**
 * The cue as the bar shows it, at the right of the context. The region is
 * always there (never hidden, or a screen reader would miss the first thing
 * put in it), so changes to it are said, and it takes no room while empty.
 * On a phone the context has none to spare, so the cue stands in its place for
 * as long as it is up.
 */
export function SaveCue() {
  const store = useSaveCue()
  const state = useSyncExternalStore(
    store?.subscribe ?? (() => () => {}),
    store?.getSnapshot ?? (() => IDLE),
    () => IDLE,
  )
  return (
    <output
      data-save-cue
      aria-live="polite"
      className={cn(
        "bg-page ml-auto min-w-0 text-[13px] leading-tight transition-opacity duration-300 motion-reduce:transition-none max-sm:not-empty:absolute max-sm:not-empty:inset-0 max-sm:not-empty:ml-0 max-sm:not-empty:flex max-sm:not-empty:items-center",
        state.tone === "failed" ? "text-late sm:line-clamp-2" : "shrink-0",
        state.tone === "saved" && "text-ink-3",
        state.fading && "opacity-0",
      )}
    >
      {state.text}
    </output>
  )
}
