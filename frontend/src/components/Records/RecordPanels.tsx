import { Suspense, use, useEffect, useState } from "react"

import { IssuedTokenProvider } from "@/components/Bots/IssuedToken"
import { useCaptureShortcut } from "@/components/Tasks/capture"
import { panelModule, preloadPanel } from "./panelModules"
import { RECORD_KINDS, type RecordKind, useRecordPanels } from "./panels"

const KINDS = Object.keys(RECORD_KINDS) as RecordKind[]

/** A kind's panel body, which holds its capture form if it has one. */
function Panel({ kind }: { kind: RecordKind }) {
  const Body = use(panelModule(kind))
  return <Body />
}

/** Fetch every panel's code once the page has settled, so none waits to open. */
function usePanelsWhenIdle() {
  useEffect(() => {
    const preloadAll = () => {
      for (const kind of KINDS) preloadPanel(kind)
    }
    // Safari has no idle callback; a moment after the page is close enough.
    if (typeof window.requestIdleCallback === "function") {
      const handle = window.requestIdleCallback(preloadAll, { timeout: 3000 })
      return () => window.cancelIdleCallback(handle)
    }
    const timer = setTimeout(preloadAll, 1500)
    return () => clearTimeout(timer)
  }, [])
}

/**
 * Every record panel, mounted once for the whole authenticated app.
 *
 * They live here rather than on the screens that list their records so that
 * any route can open a record over itself — the Stay-Put Rule — and so that
 * capture works from wherever the reader had the thought, including screens
 * that list nothing of that kind at all.
 *
 * A panel is mounted from the first time it opens and stays mounted after,
 * as all of them used to be from the start; until then its code is not
 * needed on the page.
 */
export function RecordPanels() {
  const panels = useRecordPanels()
  useCaptureShortcut(() => panels.capture("task"))
  usePanelsWhenIdle()

  const open = panels.openKind
  const [opened, setOpened] = useState<readonly RecordKind[]>([])
  if (open && !opened.includes(open)) setOpened([...opened, open])

  return (
    // A token is shown once, and the control that issued it is replaced by
    // Revoke the moment it exists: the reveal is held above the panels so
    // that nothing it came from can take it down with it (FR-08.13).
    <IssuedTokenProvider>
      {KINDS.filter((kind) => kind === open || opened.includes(kind)).map(
        (kind) => (
          // Code that fails to arrive is said by the app's error screen, as
          // it is for a page's own code.
          <Suspense key={kind} fallback={null}>
            <Panel kind={kind} />
          </Suspense>
        ),
      )}
    </IssuedTokenProvider>
  )
}
