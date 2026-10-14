import { Link } from "@tanstack/react-router"
import type { ReactNode } from "react"

import type { ActivityEntryPublic } from "@/client"
import { recordLink } from "@/components/Records/panels"
import { cn } from "@/lib/utils"
import { entryWords, recordOf, subjectName } from "./entryWords"

interface ActivityDescriptionProps {
  entry: ActivityEntryPublic
  currentUserId?: string
}

/**
 * One entry as a sentence. The vocabulary — the verb, the pluralisations,
 * the field labels, all 24 actions — lives in `entryWords`, in the voice
 * that names its subject; this component supplies only the one thing that
 * voice cannot: the subject itself, as a link to the record (The Real
 * Address Rule — its panel opens on the screen the reader is already on,
 * over any other it replaces, so following a link from a long log does not
 * cost them their place in it), struck through when the record is gone.
 *
 * It is built from what the entry recorded at the time, so it reads the
 * same after the task is renamed, moved or deleted; only the link depends
 * on the thing still being there.
 */
export function ActivityDescription({
  entry,
  currentUserId,
}: ActivityDescriptionProps) {
  const words = entryWords(entry, "names-its-subject", currentUserId)
  // Every one of the 24 actions has a case in this voice, so this is never
  // actually null; the compiler does not know that, since `entryWords`'
  // return type is shared with the voice that does say nothing for some
  // actions. Render nothing rather than throw if a future action arrives
  // here with no case yet.
  if (!words) return null
  const name = subjectName(entry)
  const linkClass = "font-medium underline-offset-4 hover:underline"

  const record = entry.entity_exists ? recordOf(entry) : null
  const subject: ReactNode = record ? (
    <Link {...recordLink(record.kind, record.id)} className={linkClass}>
      {name}
    </Link>
  ) : (
    // A name whose record is gone is struck through: it is still what the
    // line is about, and it can no longer be opened.
    <span
      className={cn(
        "font-medium",
        // Only for an entry about the record itself: for a comment or a
        // file, `entity_exists` says whether that is still there, not the
        // task the line names.
        ["task", "project", "tag"].includes(entry.entity_type) &&
          "text-ink-3 line-through",
      )}
    >
      {name}
    </span>
  )

  return (
    <>
      {words.verb}
      {words.subject && <> {subject}</>}
      {words.after}
    </>
  )
}
