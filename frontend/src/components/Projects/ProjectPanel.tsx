import { useMutation, useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"

import {
  type ProjectPublic,
  ProjectsService,
  type ProjectUpdate,
} from "@/client"
import { act } from "@/components/Common/RecordWork"
import { useRecordPanel } from "@/components/Records/panels"
import {
  DescriptionSection,
  EditableText,
  gutter,
  PropertyList,
  PropertyRow,
  ReadOnlyValue,
  RecordPanel,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { useWalk } from "@/components/Records/walk"
import { formatDayOf } from "@/lib/dates"
import { botsQuery, useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import DeleteProject from "./DeleteProject"
import { NewProject } from "./NewProject"
import { KeptTasks, OpenTasks, ProjectActivity } from "./ProjectWork"
import { botsIn, tasksInWords } from "./words"

/**
 * A project as one document: what it holds and who works in it, whether it is
 * in use, then its description, its open tasks with a line to add one, and
 * what has happened in it.
 *
 * There are no tabs and no Save: the name is edited in place, and every change
 * saves as it is made. A project is fetched by id rather than read out of the
 * page behind, because a link may point at one the list in view excludes — an
 * archived one, most of all.
 */
export function ProjectPanel() {
  const {
    id,
    capturing,
    record: project,
    panels,
    shell,
  } = useRecordPanel("project")
  // The projects listed on the page behind, so ↓ and ↑ walk them.
  const walk = useWalk(id)

  return (
    <RecordPanel
      {...shell}
      walk={walk}
      onWalk={(to) => panels.walkTo(to, "project")}
      destructive={
        project && !project.is_inbox && !capturing ? (
          <DeleteProject project={project} onSuccess={shell.onClose} />
        ) : undefined
      }
      bar={
        capturing ? (
          <>
            <span className="shrink-0">New project</span>
            <span aria-hidden>·</span>
            <span className="truncate">Not saved yet</span>
          </>
        ) : project ? (
          <>
            <span className="truncate">Project</span>
            {project.created_at && (
              <>
                <span aria-hidden>·</span>
                <span className="shrink-0 whitespace-nowrap">
                  created {formatDayOf(project.created_at)}
                </span>
              </>
            )}
          </>
        ) : undefined
      }
    >
      {capturing ? (
        <NewProject />
      ) : project ? (
        <ProjectRecord project={project} />
      ) : null}
    </RecordPanel>
  )
}

function ProjectRecord({ project }: { project: ProjectPublic }) {
  const save = useProjectUpdate(project)
  const { data: bots } = useQuery(botsQuery())
  const working = botsIn(project.id, bots?.data ?? [])

  return (
    <>
      <div className={cn("pt-2 pb-[18px]", gutter)}>
        {
          // The Inbox's name is fixed, and an archived project is frozen
          // whole until it is unarchived (FR-05.12): both read as prose, not
          // as a control that would be refused.
          project.is_inbox || project.is_archived ? (
            <p className="-ml-2 px-2 py-1.5 text-xl leading-snug font-semibold">
              {project.name}
            </p>
          ) : (
            <EditableText
              value={project.name}
              ariaLabel="Project name"
              onCommit={async (name) =>
                name.trim() ? save({ name: name.trim() }) : false
              }
              className={cn(titleFieldClass, "-ml-2")}
            />
          )
        }
      </div>

      <PropertyList>
        <PropertyRow label="Tasks">
          <span className="text-ink-2 text-sm tabular-nums">
            {project.is_archived
              ? `${project.task_count ?? 0} kept`
              : tasksInWords(project)}
          </span>
          {project.is_archived ? (
            (project.task_count ?? 0) > 0 && (
              <RouterLink
                to="/projects/$projectId/tasks"
                params={{ projectId: project.id }}
                className={act}
              >
                Read the kept tasks <span aria-hidden>→</span>
              </RouterLink>
            )
          ) : (
            <RouterLink
              to="/tasks"
              search={{ project_id: project.id }}
              className={act}
            >
              Open the list <span aria-hidden>→</span>
            </RouterLink>
          )}
        </PropertyRow>

        <PropertyRow label="Bot users">
          <span className="text-ink-2 py-1 text-sm text-pretty">
            {working.length > 0 ? (
              working.join(", ")
            ) : (
              <span className="text-ink-3">No bot user has it in scope</span>
            )}
          </span>
        </PropertyRow>

        <PropertyRow label="State">
          {project.is_inbox ? (
            // The Inbox takes every task created without a project, so an
            // archived, read-only Inbox could no longer do its job (FR-05.4),
            // and it keeps its name and stays (FR-05.6).
            <ReadOnlyValue>
              Always in use. The Inbox cannot be renamed, archived or deleted,
              because every task filed without a project lands in it.
            </ReadOnlyValue>
          ) : (
            <ArchiveToggle project={project} />
          )}
        </PropertyRow>
      </PropertyList>

      <DescriptionSection>
        {project.is_archived ? (
          <ReadOnlyValue>
            {project.description || "No description"}
          </ReadOnlyValue>
        ) : (
          <EditableText
            multiline
            value={project.description ?? ""}
            placeholder="Add a description"
            ariaLabel="Project description"
            onCommit={(description) =>
              save({ description: description.trim() || null })
            }
          />
        )}
      </DescriptionSection>

      {project.is_archived ? (
        <KeptTasks key={`tasks-${project.id}`} project={project} />
      ) : (
        <OpenTasks key={`tasks-${project.id}`} project={project} />
      )}
      <ProjectActivity key={`activity-${project.id}`} project={project} />
    </>
  )
}

/**
 * Archiving is a state of the project, not a step on the way to deleting it:
 * one control, both ways, read where the state is.
 */
function ArchiveToggle({ project }: { project: ProjectPublic }) {
  const reportChange = useReportChange()

  const mutation = useMutation({
    mutationFn: () =>
      project.is_archived
        ? ProjectsService.unarchiveProject({ path: { project_id: project.id } })
        : ProjectsService.archiveProject({ path: { project_id: project.id } }),
    onSuccess: () =>
      toastSuccess(
        project.is_archived
          ? `“${project.name}” is back in your projects`
          : `“${project.name}” moved to the archive`,
      ),
    onError: (error) => toastError(error),
    onSettled: () =>
      reportChange({ type: "project changed", projectId: project.id }),
  })

  return (
    <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1">
      <span className="text-ink-2 text-sm">
        {project.is_archived
          ? "Archived — read-only until it comes back"
          : "Active"}
      </span>
      <button
        type="button"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
        className={act}
      >
        {project.is_archived ? "Unarchive" : "Archive"}
      </button>
    </div>
  )
}

/** Saving one field of a project, the way the panel saves every field. */
function useProjectUpdate(project: ProjectPublic) {
  const reportChange = useReportChange()

  const mutation = useMutation({
    mutationFn: (body: ProjectUpdate) =>
      ProjectsService.updateProject({
        path: { project_id: project.id },
        body,
      }),
    onError: (error) => toastError(error),
    // A project's name shows on every task in it.
    onSettled: () =>
      reportChange({ type: "project changed", projectId: project.id }),
  })

  return async (body: ProjectUpdate) => {
    try {
      await mutation.mutateAsync(body)
      return true
    } catch {
      return false
    }
  }
}
