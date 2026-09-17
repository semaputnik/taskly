import { Link } from "@tanstack/react-router"
import { Bot } from "lucide-react"

import type { ActivityEntryPublic } from "@/client"
import { recordLink } from "@/components/Records/panels"
import { Badge } from "@/components/ui/badge"

interface ActorLabelProps {
  entry: ActivityEntryPublic
  currentUserId?: string
  /** Drop the "Bot" badge where the surrounding copy already says so. */
  showBadge?: boolean
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
}: ActorLabelProps) {
  if (entry.actor_bot_user_id) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <Bot className="text-muted-foreground size-4" aria-hidden />
        <Link
          {...recordLink("bot", entry.actor_bot_user_id)}
          className="font-medium underline-offset-4 hover:underline"
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
