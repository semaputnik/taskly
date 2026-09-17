import { useMutation, useQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { Archive, CheckSquare, Clock } from "lucide-react"

import {
  type ProjectPublic,
  ProjectsService,
  type ProjectUpdate,
} from "@/client"
import { NewRecord } from "@/components/Records/NewRecord"
import {
  DescriptionSection,
  EditableText,
  PropertyList,
  PropertyRow,
  ReadOnlyValue,
  RecordHeader,
  RecordPanel,
  recordLoad,
  titleFieldClass,
  valueInset,
} from "@/components/Records/RecordPanel"
import { taskCountLabel } from "@/components/Tags/counts"
import { LoadingButton } from "@/components/ui/loading-button"
import { formatDayOf } from "@/lib/dates"
import { projectQuery, useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import DeleteProject from "./DeleteProject"

/**
 * A project as a record: read, renamed, archived and deleted in one place.
 *
 * Before this a project had no address at all — its name lived in a row, its
 * actions behind that row's overflow menu, and each action in a dialog of its
 * own. Nothing could link to a project.
 */
export function ProjectPanel({
  projectId,
  capturing,
  onClose,
  onCreated,
}: {
  projectId: string | null
  capturing: boolean
  onClose: () => void
  onCreated: (project: ProjectPublic) => void
}) {
  // Fetched by id rather than read out of the table: a link may point at a
  // project the list in view excludes — an archived one, most of all.
  const query = useQuery(projectQuery(projectId))
  const project = query.data

  return (
    <RecordPanel
      open={Boolean(projectId) || capturing}
      onClose={onClose}
      name={capturing ? "New project" : (project?.name ?? "Project")}
      kind="project"
      {...recordLoad(query, !capturing && Boolean(projectId))}
      destructive={
        project && !project.is_inbox ? (
          <DeleteProject project={project} onSuccess={onClose} />
        ) : undefined
      }
    >
      {capturing ? (
        <NewRecord
          kind="Project"
          label="Project name"
          placeholder="What is it for?"
          hint="Enter creates it and opens it here, where its description, its archive state and the tasks it holds are read."
          create={(name) =>
            ProjectsService.createProject({ body: { name } }) as Promise<{
              data: ProjectPublic
            }>
          }
          change={{ type: "project created" }}
          onCreated={onCreated}
        />
      ) : project ? (
        <ProjectRecord project={project} />
      ) : null}
    </RecordPanel>
  )
}

function ProjectRecord({ project }: { project: ProjectPublic }) {
  const save = useProjectUpdate(project)
  const readOnly = project.is_inbox || project.is_archived

  return (
    <>
      <RecordHeader
        breadcrumb="Project"
        title={
          // The Inbox's name is fixed, and an archived project is frozen
          // whole until it is unarchived (FR-05.12): both read as prose, not
          // as a control that would be refused.
          readOnly ? (
            <p className="px-2 py-1.5 text-xl leading-snug font-semibold">
              {project.name}
            </p>
          ) : (
            <EditableText
              value={project.name}
              ariaLabel="Project name"
              onCommit={async (name) =>
                name.trim() ? save({ name: name.trim() }) : false
              }
              className={titleFieldClass}
            />
          )
        }
      />

      <PropertyList>
        <PropertyRow icon={CheckSquare} label="Tasks">
          {(project.task_count ?? 0) > 0 ? (
            <RouterLink
              to="/tasks"
              search={{ project_id: project.id }}
              className={cn(valueInset, "underline-offset-4 hover:underline")}
            >
              {taskCountLabel(project.task_count ?? 0)}
            </RouterLink>
          ) : (
            <ReadOnlyValue>No tasks</ReadOnlyValue>
          )}
        </PropertyRow>

        <PropertyRow icon={Archive} label="Archive">
          {project.is_inbox ? (
            // The Inbox takes every task created without a project, so an
            // archived, read-only Inbox could no longer do its job (FR-05.4).
            <ReadOnlyValue>
              The Inbox is always in use, so it is never archived or renamed
            </ReadOnlyValue>
          ) : (
            <ArchiveToggle project={project} />
          )}
        </PropertyRow>

        <PropertyRow icon={Clock} label="Created">
          <ReadOnlyValue>
            {project.created_at ? (
              <time dateTime={project.created_at}>
                {formatDayOf(project.created_at)}
              </time>
            ) : (
              "Unknown"
            )}
          </ReadOnlyValue>
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
    <div className={cn("flex flex-wrap items-center gap-2", valueInset)}>
      <span>
        {project.is_archived
          ? "Archived — read-only until it comes back"
          : "In use"}
      </span>
      <LoadingButton
        variant="outline"
        size="sm"
        loading={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {project.is_archived ? "Unarchive" : "Archive"}
      </LoadingButton>
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
