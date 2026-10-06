import { Link } from "@tanstack/react-router"
import { Bot } from "lucide-react"

import type { ActivityEntryPublic } from "@/client"
import { recordLink } from "@/components/Records/panels"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface ActorLabelProps {
  entry: ActivityEntryPublic
  currentUserId?: string
  /** Drop the "Bot" badge where the surrounding copy already says so. */
  showBadge?: boolean
  /** Drop the bot glyph where weight and ink already set a bot apart. */
  showIcon?: boolean
  /** Strike the bot user's name through: it has been deleted. */
  deleted?: boolean
}

/**
 * Who made the change: you, or one of your bot users by name (FR-10.2). A bot
 * is named as it was called at the time, so the line still reads after it is
 * renamed or deleted.
 *
 * The name is the way to the bot user itself — an unexpected change is read
 * here and answered there — and it opens over this screen rather than taking
 * the reader out of the log they are reading (The Stay-Put Rule).
 */
export function ActorLabel({
  entry,
  currentUserId,
  showBadge = true,
  showIcon = true,
  deleted = false,
}: ActorLabelProps) {
  if (entry.actor_bot_user_id) {
    return (
      <span className="inline-flex items-center gap-1.5">
        {showIcon && (
          <Bot className="text-muted-foreground size-4" aria-hidden />
        )}
        <Link
          {...recordLink("bot", entry.actor_bot_user_id)}
          className={cn(
            "font-medium underline-offset-4 hover:underline",
            deleted && "line-through",
          )}
        >
          {entry.actor_bot_user_name ?? "A bot user"}
        </Link>
        {showBadge && (
          <Badge variant="outline" className="text-xs">
            Bot
          </Badge>
        )}
      </span>
    )
  }
  return <>{entry.actor_id === currentUserId ? "You" : "Someone else"}</>
}
