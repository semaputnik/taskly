import { useQuery } from "@tanstack/react-query"
import { Bot } from "lucide-react"
import { BotsService, type BotUserRef, type TaskPublic } from "@/client"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

// The form's values: nobody, the user, or a bot user's id as it is.
const UNASSIGNED = "unassigned"
export const ASSIGNED_TO_ME = "me"

/** What the form starts from for a task. */
export function assigneeFormValue(task: TaskPublic): string {
  if (task.assignee_bot_user) return task.assignee_bot_user.id
  return task.assignee_id ? ASSIGNED_TO_ME : UNASSIGNED
}

/** The `assignee_id` the API takes for a form value. */
export function toAssigneeId(
  value: string | undefined,
  currentUserId: string | undefined,
): string | null {
  if (!value || value === UNASSIGNED) return null
  return value === ASSIGNED_TO_ME ? (currentUserId ?? null) : value
}

export function useBotUsers() {
  return useQuery({
    queryKey: ["bots"],
    queryFn: async () =>
      (await BotsService.readBotUsers({ query: { skip: 0, limit: 100 } })).data,
  })
}

interface AssigneeSelectProps {
  value: string | undefined
  onChange: (value: string) => void
  currentUserEmail?: string
  /**
   * The bot user the task is already assigned to. A deleted one stays on its
   * tasks (FR-08.21) but is no longer among the bot users to pick, so it is
   * offered here, marked deleted, only to keep what the task has.
   */
  current?: BotUserRef | null
  /** Styling for the trigger, so the control can sit flat in a property list. */
  className?: string
}

/** Who a task can be assigned to: the user or one of their bot users. */
export function AssigneeSelect({
  value,
  onChange,
  currentUserEmail,
  current,
  className,
}: AssigneeSelectProps) {
  const { data: bots } = useBotUsers()
  const botOptions = (bots?.data ?? []).map((bot) => ({
    id: bot.id,
    name: bot.name,
    deleted: false,
  }))
  if (current?.deleted) {
    botOptions.push(current)
  }

  return (
    <Select onValueChange={onChange} value={value}>
      <SelectTrigger className={cn("w-full", className)} aria-label="Assignee">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
        <SelectItem value={ASSIGNED_TO_ME}>Me ({currentUserEmail})</SelectItem>
        {botOptions.map((bot) => (
          <SelectItem key={bot.id} value={bot.id} disabled={bot.deleted}>
            <Bot className="text-muted-foreground" aria-hidden />
            {bot.deleted ? `${bot.name} (deleted)` : bot.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
