import { Link } from "@tanstack/react-router"
import type { ReactNode } from "react"

import type { ActivityEntryPublic } from "@/client"
import { type RecordKind, recordLink } from "@/components/Records/panels"
import { cn } from "@/lib/utils"
import { entryWords } from "./entryWords"

function detail<T>(entry: ActivityEntryPublic, key: string): T | undefined {
  return entry.details[key] as T | undefined
}

interface ActivityDescriptionProps {
  entry: ActivityEntryPublic
  currentUserId?: string
}

/**
 * What an entry names: the task, project, tag, or task a comment or file is
 * on.
 */
function subjectName(entry: ActivityEntryPublic): string {
  if (entry.entity_type === "project" || entry.entity_type === "tag") {
    return detail<string>(entry, "name") ?? "Untitled project"
  }
  if (entry.entity_type === "comment" || entry.entity_type === "attachment") {
    return detail<{ title: string }>(entry, "task")?.title ?? "a task"
  }
  return detail<string>(entry, "title") ?? "Untitled task"
}

/**
 * The record an entry links to: its own entity, or for a comment or a file,
 * the task it is on.
 */
function recordOf(
  entry: ActivityEntryPublic,
): { kind: RecordKind; id: string } | null {
  switch (entry.entity_type) {
    case "task":
    case "project":
    case "tag":
      return { kind: entry.entity_type, id: entry.entity_id }
    case "comment":
    case "attachment": {
      const task = detail<{ id?: string }>(entry, "task")
      return task?.id ? { kind: "task", id: task.id } : null
    }
    default:
      return null
  }
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
