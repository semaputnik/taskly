import { Bot } from "lucide-react"

import type { TagPublic } from "@/client"
import { Badge } from "@/components/ui/badge"

/**
 * Which bot user brought a tag into being, where one did: an agent's
 * vocabulary, told apart from the user's own (FR-01.28).
 */
export function BotCreator({ tag }: { tag: TagPublic }) {
  const bot = tag.created_by_bot_user
  if (!bot) return null
  return (
    <Badge
      variant="outline"
      className="text-muted-foreground gap-1 font-normal"
      title={`Created by the bot user ${bot.name}`}
    >
      <Bot aria-hidden />
      <span className="sr-only">Created by the bot user </span>
      {bot.name}
      {bot.deleted && " (deleted)"}
    </Badge>
  )
}
