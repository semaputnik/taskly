import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  type DueDateScope,
  ProjectsService,
  type TaskPublic,
  TasksService,
  type TaskUpdate,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
  checkRecurrence,
  DueDateScopeDialog,
  RecurrenceFields,
  recurrenceFormValues,
  recurrenceShape,
  sameRecurrence,
  toRecurrence,
} from "./recurrence"
import { TagsField } from "./TagsField"

const NO_PRIORITY = "none"
const UNASSIGNED = "unassigned"
const ASSIGNED_TO_ME = "me"

const formSchema = z
  .object({
    title: z.string().min(1, { message: "Title is required" }),
    description: z.string().optional(),
    project_id: z.string().optional(),
    due_date: z.string().optional(),
    priority: z.string().optional(),
    assignee: z.string().optional(),
    tags: z.array(z.string()),
    ...recurrenceShape,
  })
  .superRefine(checkRecurrence)

type FormData = z.infer<typeof formSchema>

interface EditTaskProps {
  task: TaskPublic
  onSuccess: () => void
}

const EditTask = ({ task, onSuccess }: EditTaskProps) => {
  const [isOpen, setIsOpen] = useState(false)
  // An update held back until the user says how far a new due date reaches.
  const [awaitingScope, setAwaitingScope] = useState<TaskUpdate | null>(null)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { user: currentUser } = useAuth()

  // A subtask has no project of its own: it follows the task at the top of
  // its tree, which is the one that can be moved (FR-02.4).
  const isSubtask = task.parent_id !== null && task.parent_id !== undefined

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: async () =>
      (await ProjectsService.readProjects({ query: { skip: 0, limit: 100 } }))
        .data,
    enabled: !isSubtask,
  })

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      title: task.title,
      description: task.description ?? "",
      project_id: task.project_id,
      due_date: task.due_date ?? "",
      priority: task.priority ?? NO_PRIORITY,
      assignee: task.assignee_id ? ASSIGNED_TO_ME : UNASSIGNED,
      tags: task.tags ?? [],
      ...recurrenceFormValues(task.recurrence),
    },
  })

  const mutation = useMutation({
    mutationFn: (data: TaskUpdate) =>
      TasksService.updateTask({ path: { task_id: task.id }, body: data }),
    onSuccess: () => {
      showSuccessToast("Task updated successfully")
      setAwaitingScope(null)
      setIsOpen(false)
      onSuccess()
    },
    onError: (error: Error) => {
      setAwaitingScope(null)
      handleError.call(showErrorToast, error)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      // A tag typed here is new to the account, and one dropped off the last
      // task carrying it is gone: autocomplete has to catch up either way.
      queryClient.invalidateQueries({ queryKey: ["tags"] })
    },
  })

  const onSubmit = (data: FormData) => {
    const recurrence = toRecurrence(data)
    const dueDate = data.due_date || null
    // Editing an existing task: an omitted key means "leave unchanged", so a
    // cleared field must be sent as `null`, not dropped as `undefined`.
    const body: TaskUpdate = {
      title: data.title,
      description: data.description || null,
      project_id: isSubtask ? undefined : data.project_id,
      due_date: dueDate,
      priority:
        data.priority && data.priority !== NO_PRIORITY
          ? (data.priority as TaskUpdate["priority"])
          : null,
      assignee_id: data.assignee === ASSIGNED_TO_ME ? currentUser?.id : null,
      tags: data.tags,
      recurrence: isSubtask ? undefined : recurrence,
    }

    // Moving an open occurrence on its own schedule has to say whether the
    // routine moves with it; a changed rule restarts the schedule anyway.
    const reschedules =
      task.recurrence &&
      !task.completed &&
      dueDate !== (task.due_date ?? null) &&
      sameRecurrence(recurrence, task.recurrence)
    if (reschedules) {
      setAwaitingScope(body)
      return
    }
    mutation.mutate(body)
  }

  const onScopeChosen = (scope: DueDateScope) => {
    if (awaitingScope) {
      mutation.mutate({ ...awaitingScope, due_date_scope: scope })
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        Edit Task
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>Edit Task</DialogTitle>
              <DialogDescription>
                Update the task details below.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Title <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="Task title" type="text" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Input placeholder="Description" type="text" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {!isSubtask && (
                <FormField
                  control={form.control}
                  name="project_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Project</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {projects?.data.map((project) => (
                            <SelectItem key={project.id} value={project.id}>
                              {project.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              <FormField
                control={form.control}
                name="due_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Due date</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {!isSubtask && (
                <RecurrenceFields
                  control={form.control}
                  disabled={task.completed}
                />
              )}

              <FormField
                control={form.control}
                name="priority"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Priority</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={NO_PRIORITY}>No priority</SelectItem>
                        <SelectItem value="P1">P1</SelectItem>
                        <SelectItem value="P2">P2</SelectItem>
                        <SelectItem value="P3">P3</SelectItem>
                        <SelectItem value="P4">P4</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="tags"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Tags</FormLabel>
                    <FormControl>
                      <TagsField
                        value={field.value}
                        onChange={field.onChange}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="assignee"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Assignee</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
                        <SelectItem value={ASSIGNED_TO_ME}>
                          Me ({currentUser?.email})
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Save
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
      <DueDateScopeDialog
        open={awaitingScope !== null}
        onOpenChange={(open) => !open && setAwaitingScope(null)}
        onChoose={onScopeChosen}
        pending={mutation.isPending}
      />
    </Dialog>
  )
}

export default EditTask
