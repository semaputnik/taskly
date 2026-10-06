import { useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"

import type { TagPublic } from "@/client"
import { Empty, more, Pending } from "@/components/Common/RecordWork"
import { textLink } from "@/components/Dashboard/shared"
import { RecordSection } from "@/components/Records/RecordPanel"
import { CompactTaskRow } from "@/components/Tasks/CompactTaskRow"
import { OPEN_STATUSES } from "@/components/Tasks/statuses"
import { scopeProjectsQuery, tasksQuery } from "@/lib/serverState"
import { cn } from "@/lib/utils"

const PREVIEW = 5

/**
 * The first open tasks that carry the tag, as task lines, with the way on to
 * the whole list narrowed to it. It asks for what the list asks for, so the
 * count over it is the number the link shows.
 */
export function OpenTasks({ tag }: { tag: TagPublic }) {
  const { data, isPending, isError, refetch } = useQuery(
    tasksQuery({
      tag: tag.name,
      status: OPEN_STATUSES,
      sort: "priority",
      skip: 0,
      limit: PREVIEW,
    }),
  )
  const rest = data ? data.count - data.data.length : 0
  // A tag crosses projects, so each line says which one it is in.
  const { data: projects } = useQuery(scopeProjectsQuery())
  const names = Object.fromEntries(
    (projects ?? []).map((project) => [project.id, project.name]),
  )

  return (
    <RecordSection title="Open tasks" count={data?.count}>
      {isPending ? (
        <Pending />
      ) : isError || !data ? (
        <p role="alert" className="text-ink-2 pt-2 text-sm">
          Its tasks could not be loaded.{" "}
          <button
            type="button"
            onClick={() => void refetch()}
            className={cn(textLink, "text-ink underline")}
          >
            Try again
          </button>
        </p>
      ) : data.count === 0 ? (
        <Empty>
          No open task carries it. Type it onto a task and it shows here.
        </Empty>
      ) : (
        <>
          <ul aria-label={`Open tasks tagged ${tag.name}`}>
            {data.data.map((task) => (
              <CompactTaskRow
                key={task.id}
                task={task}
                projectName={names[task.project_id]}
                receipt
                flush
                asItem
              />
            ))}
          </ul>
          {rest > 0 && (
            <RouterLink to="/tasks" search={{ tag: tag.name }} className={more}>
              {rest} more in the list <span aria-hidden>→</span>
            </RouterLink>
          )}
        </>
      )}
    </RecordSection>
  )
}
