import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { ProjectPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import ArchiveProject from "./ArchiveProject"
import EditProject from "./EditProject"

interface ProjectActionsMenuProps {
  project: ProjectPublic
}

export const ProjectActionsMenu = ({ project }: ProjectActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditProject project={project} onSuccess={() => setOpen(false)} />
        {/* The Inbox takes every task created without a project, so it has to
            stay writable. */}
        {!project.is_inbox && (
          <ArchiveProject project={project} onSuccess={() => setOpen(false)} />
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
