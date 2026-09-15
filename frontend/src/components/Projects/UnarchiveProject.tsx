import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ArchiveRestore } from "lucide-react"

import { type ProjectPublic, ProjectsService } from "@/client"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface UnarchiveProjectProps {
  project: ProjectPublic
}

/** Brings a project and its tasks back into daily use, exactly as they were. */
const UnarchiveProject = ({ project }: UnarchiveProjectProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () =>
      ProjectsService.unarchiveProject({ path: { project_id: project.id } }),
    onSuccess: () => {
      showSuccessToast(`“${project.name}” is back in your projects`)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return (
    <LoadingButton
      variant="outline"
      size="sm"
      loading={mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      <ArchiveRestore />
      Unarchive
    </LoadingButton>
  )
}

export default UnarchiveProject
