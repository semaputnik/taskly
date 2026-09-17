import type { ComponentType } from "react"

import { BotPanel } from "@/components/Bots/BotPanel"
import { IssuedTokenProvider } from "@/components/Bots/IssuedToken"
import { ProjectPanel } from "@/components/Projects/ProjectPanel"
import { TagPanel } from "@/components/Tags/TagPanel"
import { useCaptureShortcut } from "@/components/Tasks/capture"
import { TaskDetail } from "@/components/Tasks/TaskDetail"
import { RECORD_KINDS, type RecordKind, useRecordPanels } from "./panels"

/** Each record kind's panel: its body, and its capture form if it has one. */
const PANELS: Record<RecordKind, ComponentType> = {
  task: TaskDetail,
  project: ProjectPanel,
  tag: TagPanel,
  bot: BotPanel,
}

/**
 * Every record panel, mounted once for the whole authenticated app.
 *
 * They live here rather than on the screens that list their records so that
 * any route can open a record over itself — the Stay-Put Rule — and so that
 * capture works from wherever the reader had the thought, including screens
 * that list nothing of that kind at all.
 */
export function RecordPanels() {
  const panels = useRecordPanels()
  useCaptureShortcut(() => panels.capture("task"))

  return (
    // A token is shown once, and the control that issued it is replaced by
    // Revoke the moment it exists: the reveal is held above the panels so
    // that nothing it came from can take it down with it (FR-08.13).
    <IssuedTokenProvider>
      {(Object.keys(RECORD_KINDS) as RecordKind[]).map((kind) => {
        const Panel = PANELS[kind]
        return <Panel key={kind} />
      })}
    </IssuedTokenProvider>
  )
}
