import { useQuery } from "@tanstack/react-query"

import { BotPanel } from "@/components/Bots/BotPanel"
import { IssuedTokenProvider } from "@/components/Bots/IssuedToken"
import { ProjectPanel } from "@/components/Projects/ProjectPanel"
import { TagPanel } from "@/components/Tags/TagPanel"
import {
  type CaptureTarget,
  useCaptureShortcut,
} from "@/components/Tasks/capture"
import { TaskDetail } from "@/components/Tasks/TaskDetail"
import { projectsQuery } from "@/lib/serverState"
import { useRecordPanels } from "./panels"

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
  const { capturing, filteredProjectId } = panels

  useCaptureShortcut(() => panels.capture("task"))

  // Asked for to name a captured task's destination, and asked for as soon as
  // the screen is narrowed to a project rather than when capture opens: a
  // capture that beats the answer would file the task in the Inbox while the
  // panel was still saying which project it was going to. Archived projects
  // are not among them, which is why a list filtered to one falls back to the
  // Inbox rather than capturing into a project the API would refuse
  // (FR-05.12).
  const { data: projects } = useQuery({
    ...projectsQuery(),
    enabled: capturing === "task" || Boolean(filteredProjectId),
  })

  const filtered = projects?.data.find(
    (project) => project.id === filteredProjectId,
  )
  const captureTarget: CaptureTarget = {
    projectId: filtered?.id,
    // The default is stated rather than assumed, from the moment the panel
    // opens (FR-05.4).
    projectName: filtered?.name ?? "Inbox",
  }

  return (
    // A token is shown once, and the control that issued it is replaced by
    // Revoke the moment it exists: the reveal is held above the panels so
    // that nothing it came from can take it down with it (FR-08.13).
    <IssuedTokenProvider>
      <TaskDetail
        taskId={panels.taskId}
        capturing={capturing === "task"}
        captureTarget={captureTarget}
        onClose={panels.close}
        onOpenTask={panels.openTask}
        onCaptured={(created, stay) => {
          // A run of captures holds the panel still; a single one hands the
          // reader the record it just made, at its own address.
          if (!stay) panels.openTask(created)
        }}
      />
      <ProjectPanel
        projectId={panels.projectId}
        capturing={capturing === "project"}
        onClose={panels.close}
        onCreated={(project) => panels.openProject(project.id)}
      />
      <TagPanel
        tagId={panels.tagId}
        capturing={capturing === "tag"}
        onClose={panels.close}
        onCreated={(tag) => panels.openTag(tag.id)}
        onOpenTag={panels.openTag}
      />
      <BotPanel botId={panels.botId} onClose={panels.close} />
    </IssuedTokenProvider>
  )
}
