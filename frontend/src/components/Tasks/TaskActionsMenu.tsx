import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { TaskPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import AddTask from "./AddTask"
import DeleteTask from "./DeleteTask"
import EditTask from "./EditTask"
import TaskAttachments from "./TaskAttachments"
import TaskComments from "./TaskComments"

interface TaskActionsMenuProps {
  task: TaskPublic
}

export const TaskActionsMenu = ({ task }: TaskActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditTask task={task} onSuccess={() => setOpen(false)} />
        <AddTask parent={task} onSuccess={() => setOpen(false)} />
        <TaskComments task={task} onSuccess={() => setOpen(false)} />
        <TaskAttachments task={task} onSuccess={() => setOpen(false)} />
        <DeleteTask task={task} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
