import { useQuery } from "@tanstack/react-query"

import { ProjectsService } from "@/client"
import { type CaptureTarget, useCapture, useCaptureShortcut } from "./capture"
import { TaskDetail } from "./TaskDetail"

/**
 * The task panel, mounted once for the whole authenticated app.
 *
 * It lives here rather than on each screen that lists tasks so that every
 * route can open a record over itself — the Stay-Put Rule — and so that
 * capture works from wherever the reader had the thought, including the
 * screens that list no tasks at all.
 */
export function TaskPanel() {
  const { taskId, capturing, filteredProjectId, start, close, openTask } =
    useCapture()

  useCaptureShortcut(start)

  // Asked for to name the destination, and asked for as soon as the screen is
  // narrowed to a project rather than when capture opens: a capture that
  // beats the answer would file the task in the Inbox while the panel was
  // still saying which project it was going to. Archived projects are not
  // among them, which is exactly why a list filtered to one falls back to the
  // Inbox rather than capturing into a project the API would refuse
  // (FR-05.12).
  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () =>
      (await ProjectsService.readProjects({ query: { skip: 0, limit: 100 } }))
        .data,
    enabled: capturing || Boolean(filteredProjectId),
  })

  const filtered = projects?.data.find(
    (project) => project.id === filteredProjectId,
  )
  const target: CaptureTarget = {
    projectId: filtered?.id,
    // The default is stated rather than assumed, from the moment the panel
    // opens (FR-05.4).
    projectName: filtered?.name ?? "Inbox",
  }

  return (
    <TaskDetail
      taskId={taskId}
      capturing={capturing}
      captureTarget={target}
      onClose={close}
      onOpenTask={openTask}
      onCaptured={(created, stay) => {
        // A run of captures holds the panel still; a single one hands the
        // reader the record it just made, at its own address.
        if (!stay) openTask(created)
      }}
    />
  )
}
