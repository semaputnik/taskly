import { Link } from "@tanstack/react-router"
import type { ReactNode } from "react"

import type { ActivityEntryPublic } from "@/client"
import { type RecordKind, recordLink } from "@/components/Records/panels"
import { cn } from "@/lib/utils"
import { entryWords } from "./entryWords"

interface ActivityDescriptionProps {
  entry: ActivityEntryPublic
  currentUserId?: string
}

/**
 * What an entry names: the task, project, tag, or task a comment or file is
 * on. Switches on `details.kind` — the discriminated union's own tag
 * (#299's spike) — the same way `recordOf` below does, rather than reading
 * `entry.entity_type` or which field happens to be on `details`.
 */
function subjectName(entry: ActivityEntryPublic): string {
  const { details } = entry
  switch (details.kind) {
    case "project_created":
    case "project_changed":
    case "project_deleted":
    case "project_restored":
      return details.name ?? "Untitled project"
    case "tag_created":
    case "tag_renamed":
    case "tag_deleted":
    case "tag_merged":
      // "Untitled project" covers a nameless tag too — an existing
      // wording quirk, preserved rather than fixed, since nothing
      // user-visible changes in this ticket.
      return details.name ?? "Untitled project"
    case "comment_added":
    case "comment_edited":
    case "comment_deleted":
    case "attachment_added":
    case "attachment_deleted":
      return details.task.title ?? "a task"
    // A batch names no single task; a row the backend could not make
    // sense of at all names nothing either (`to_public`'s own fallback).
    case "task_deleted_batch":
    case "task_restored_batch":
    case "tasks_bulk_changed":
    case "unrecognized":
      return "Untitled task"
    default:
      return details.title ?? "Untitled task"
  }
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
      const { details } = entry
      // Narrowed by `kind` rather than `"task" in details`: `task_created`'s
      // own snapshot also has a `task` field, but it is a `TaskSnapshot`
      // (named only by its fields, not its id) rather than the `TaskRef` a
      // comment or an attachment names its task by.
      switch (details.kind) {
        case "comment_added":
        case "comment_edited":
        case "comment_deleted":
        case "attachment_added":
        case "attachment_deleted":
          return { kind: "task", id: details.task.id }
        default:
          return null
      }
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
