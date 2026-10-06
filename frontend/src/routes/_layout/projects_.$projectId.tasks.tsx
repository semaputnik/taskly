import { useQuery } from "@tanstack/react-query"
import {
  createFileRoute,
  Navigate,
  Link as RouterLink,
} from "@tanstack/react-router"

import { textLink } from "@/components/Dashboard/shared"
import { recordLink } from "@/components/Records/panels"
import { taskCountLabel } from "@/components/Tags/counts"
import {
  CompactTaskRow,
  CompactTaskRowPending,
} from "@/components/Tasks/CompactTaskRow"
import { buildTaskTree } from "@/components/Tasks/tree"
import { Skeleton } from "@/components/ui/skeleton"
import { projectQuery, tasksQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout/projects_/$projectId/tasks")({
  component: KeptTasks,
  head: () => ({
    meta: [
      {
        title: "Kept tasks - Taskly",
      },
    ],
  }),
})

/** How many kept tasks are read: the first page, as every list is. */
const LIMIT = 100

/**
 * The tasks an archived project keeps, read-only: the one place archived work
 * is shown. It is a view of its own rather than a filter on the task list, so
 * archived tasks never mix into daily views by accident (FR-05.14), and
 * nothing here can be changed until the project is unarchived (FR-05.12).
 * Done tasks are shown as well: the archive keeps everything.
 */
function KeptTasks() {
  const { projectId } = Route.useParams()
  const {
    data: project,
    isPending,
    isError,
  } = useQuery(projectQuery(projectId))
  const archived = project?.is_archived === true
  const { data: tasks } = useQuery({
    ...tasksQuery({
      archived: true,
      project_id: projectId,
      skip: 0,
      limit: LIMIT,
    }),
    enabled: archived,
  })

  // A live project's tasks are in the task list, which is where they can be
  // worked on.
  if (project && !archived) {
    return <Navigate to="/tasks" search={{ project_id: projectId }} replace />
  }

  const tree = tasks ? buildTaskTree(tasks.data) : undefined

  return (
    <div className="page-column">
      <p className="mb-3 text-[13px]">
        <RouterLink
          to="/projects"
          className={cn(textLink, "text-ink-3 hover:text-ink")}
        >
          <span aria-hidden>← </span>Projects
        </RouterLink>
      </p>

      {isPending ? (
        <div aria-hidden>
          <Skeleton className="mb-3 h-6 w-56" />
          {Array.from({ length: 4 }).map((_, index) => (
            <CompactTaskRowPending key={index} flush />
          ))}
        </div>
      ) : isError || !project ? (
        <div role="alert" className="border-rule border-b py-8">
          <p className="font-medium">This project could not be opened</p>
          <p className="text-ink-3 mt-1">
            It may have been deleted, or the link points at something that is
            not yours. Deleted projects can be restored from the{" "}
            <RouterLink
              to="/activity"
              className={cn(textLink, "text-ink underline")}
            >
              activity log
            </RouterLink>
            .
          </p>
        </div>
      ) : (
        <>
          <h1 className="mb-1 text-[22px] leading-[1.2] font-semibold tracking-[-0.015em]">
            {project.name}
          </h1>
          <p className="text-ink-3 mb-6">
            <span className="text-ink font-medium">
              {taskCountLabel(project.task_count ?? 0)} kept.
            </span>{" "}
            Archived, so read-only until it is unarchived.{" "}
            <RouterLink
              {...recordLink("project", project.id)}
              className={cn(textLink, "text-ink underline")}
            >
              Open the project
            </RouterLink>
          </p>

          {!tasks || !tree ? (
            <div aria-hidden>
              {Array.from({ length: 4 }).map((_, index) => (
                <CompactTaskRowPending key={index} flush />
              ))}
            </div>
          ) : tasks.count === 0 ? (
            <p className="text-ink-3 border-rule border-b py-8">
              Nothing is kept with this project.
            </p>
          ) : (
            <ul aria-label={`Tasks kept in ${project.name}`}>
              {tree.tasks.map((task) => (
                <CompactTaskRow
                  key={task.id}
                  task={task}
                  depth={tree.depths[task.id]}
                  readOnly
                  flush
                  asItem
                />
              ))}
            </ul>
          )}
          {tasks && tasks.count > LIMIT && (
            <p className="text-ink-3 pt-3.5 text-[13px]">
              Showing the first {LIMIT} of {tasks.count}.
            </p>
          )}
        </>
      )}
    </div>
  )
}
