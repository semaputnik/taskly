import { useSuspenseQueries } from "@tanstack/react-query"

import type { TaskStatus } from "@/client"
import {
  CompactTaskRow,
  CompactTaskRowPending,
} from "@/components/Tasks/CompactTaskRow"
import { projectsQuery, tasksQuery } from "@/lib/serverState"
import { Group, MoreLink, PREVIEW_ROWS } from "./sheet"

const IN_PROGRESS: TaskStatus[] = ["in_progress"]

/** The sheet's one request, most pressing first. */
export const inProgressQuery = () =>
  tasksQuery({ status: IN_PROGRESS, sort: "priority", limit: PREVIEW_ROWS })

/** The sheet while its tasks are on their way. */
export function InProgressPending() {
  return (
    <div className="bg-card overflow-hidden rounded-lg border">
      <Group label="In progress" count={0}>
        {Array.from({ length: 2 }).map((_, index) => (
          <CompactTaskRowPending key={index} />
        ))}
      </Group>
    </div>
  )
}

/**
 * What the owner already has their hands on, most pressing first. It stands
 * beside the queue rather than inside it: Overdue and Due today still list an
 * in-progress task that is late or due, because being started is not being on
 * time, and this sheet answers a different question — what am I in the middle
 * of. It is drawn even when empty, so the column beside the queue keeps its
 * shape from one day to the next.
 */
export function InProgress() {
  // The projects are the queue's own request, shared through the cache.
  const [tasks, projects] = useSuspenseQueries({
    queries: [inProgressQuery(), projectsQuery()],
  })

  const names = Object.fromEntries(
    projects.data.data.map((project) => [project.id, project.name]),
  )
  const count = tasks.data.count

  return (
    <div className="bg-card overflow-hidden rounded-lg border">
      <Group label="In progress" count={count}>
        {count === 0 ? (
          <p className="text-muted-foreground px-4 py-3 text-sm">
            Nothing in progress. Starting a task moves it here.
          </p>
        ) : (
          <>
            {tasks.data.data.map((task) => (
              <CompactTaskRow
                key={task.id}
                task={task}
                projectName={names[task.project_id]}
              />
            ))}
            {count > PREVIEW_ROWS && (
              <MoreLink
                count={count - PREVIEW_ROWS}
                search={{ status: IN_PROGRESS, sort: "priority" }}
              />
            )}
          </>
        )}
      </Group>
    </div>
  )
}
