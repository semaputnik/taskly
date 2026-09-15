import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Archive } from "lucide-react"

import { type ProjectPublic, ProjectsService } from "@/client"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ArchiveProjectProps {
  project: ProjectPublic
  onSuccess: () => void
}

/**
 * Moves a project and its tasks into the archive. Unarchiving from the
 * archive view reverses it exactly, so there is nothing to confirm (FR-05.10).
 */
const ArchiveProject = ({ project, onSuccess }: ArchiveProjectProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () =>
      ProjectsService.archiveProject({ path: { project_id: project.id } }),
    onSuccess: () => {
      showSuccessToast(`“${project.name}” moved to the archive`)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return (
    <DropdownMenuItem
      disabled={mutation.isPending}
      onSelect={(e) => e.preventDefault()}
      onClick={() => mutation.mutate()}
    >
      <Archive />
      Archive Project
    </DropdownMenuItem>
  )
}

export default ArchiveProject
