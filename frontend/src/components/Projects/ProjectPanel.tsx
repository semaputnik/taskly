import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import { Archive, CheckSquare, Clock } from "lucide-react"

import {
  type ProjectPublic,
  ProjectsService,
  type ProjectUpdate,
} from "@/client"
import { NewRecord } from "@/components/Records/NewRecord"
import {
  EditableText,
  PropertyList,
  PropertyRow,
  ReadOnlyValue,
  RecordHeader,
  RecordPanel,
  recordLoad,
  titleFieldClass,
} from "@/components/Records/RecordPanel"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
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
  const query = useQuery({
    queryKey: ["project", projectId],
    queryFn: async () =>
      (
        await ProjectsService.readProject({
          path: { project_id: projectId as string },
        })
      ).data,
    enabled: Boolean(projectId),
  })
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
          invalidate={["projects"]}
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
              className="px-2 underline-offset-4 hover:underline"
            >
              {project.task_count === 1
                ? "1 task"
                : `${project.task_count} tasks`}
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
                {new Date(project.created_at).toLocaleDateString()}
              </time>
            ) : (
              "Unknown"
            )}
          </ReadOnlyValue>
        </PropertyRow>
      </PropertyList>

      <div className="border-t px-6 py-5">
        <h3 className="mb-2 px-2 text-sm font-medium">Description</h3>
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
      </div>
    </>
  )
}

/**
 * Archiving is a state of the project, not a step on the way to deleting it:
 * one control, both ways, read where the state is.
 */
function ArchiveToggle({ project }: { project: ProjectPublic }) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () =>
      project.is_archived
        ? ProjectsService.unarchiveProject({ path: { project_id: project.id } })
        : ProjectsService.archiveProject({ path: { project_id: project.id } }),
    onSuccess: () =>
      showSuccessToast(
        project.is_archived
          ? `“${project.name}” is back in your projects`
          : `“${project.name}” moved to the archive`,
      ),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      queryClient.invalidateQueries({ queryKey: ["project", project.id] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return (
    <div className="flex flex-wrap items-center gap-2 px-2">
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
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (body: ProjectUpdate) =>
      ProjectsService.updateProject({
        path: { project_id: project.id },
        body,
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      queryClient.invalidateQueries({ queryKey: ["project", project.id] })
      // A project's name shows on every task in it.
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
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
