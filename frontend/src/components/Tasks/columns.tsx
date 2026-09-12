import { useMutation, useQueryClient } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"

import { type TaskPublic, TasksService } from "@/client"
import type { DataTableFeatures } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { TaskActionsMenu } from "./TaskActionsMenu"

function CompletedCell({ task }: { task: TaskPublic }) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (completed: boolean) =>
      TasksService.updateTask({
        path: { task_id: task.id },
        body: { completed },
      }),
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  return (
    <Checkbox
      checked={task.completed}
      onCheckedChange={(checked) => mutation.mutate(checked === true)}
      aria-label={
        task.completed ? "Mark as not completed" : "Mark as completed"
      }
    />
  )
}

export function getColumns(
  projectNames: Record<string, string>,
): ColumnDef<DataTableFeatures, TaskPublic>[] {
  return [
    {
      id: "completed",
      header: () => <span className="sr-only">Completed</span>,
      cell: ({ row }) => <CompletedCell task={row.original} />,
    },
    {
      accessorKey: "title",
      header: "Title",
      cell: ({ row }) => (
        <span
          className={cn(
            "font-medium",
            row.original.completed && "line-through text-muted-foreground",
          )}
        >
          {row.original.title}
        </span>
      ),
    },
    {
      id: "project",
      header: "Project",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {projectNames[row.original.project_id] ?? "Unknown"}
        </span>
      ),
    },
    {
      accessorKey: "due_date",
      header: "Due date",
      cell: ({ row }) => {
        const dueDate = row.original.due_date
        return (
          <span className={cn("text-muted-foreground", !dueDate && "italic")}>
            {dueDate || "No due date"}
          </span>
        )
      },
    },
    {
      accessorKey: "priority",
      header: "Priority",
      cell: ({ row }) => {
        const priority = row.original.priority
        return priority ? (
          <Badge variant="outline">{priority}</Badge>
        ) : (
          <span className="text-muted-foreground italic">No priority</span>
        )
      },
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <TaskActionsMenu task={row.original} />
        </div>
      ),
    },
  ]
}
