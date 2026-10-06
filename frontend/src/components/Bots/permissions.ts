import type { BotPermissions } from "@/client"

type Permission = keyof BotPermissions

/**
 * Everything a bot user can be granted, in the order the column lists it:
 * tasks, then comments, then tags. `note` is what a grant comes with that a
 * reader would otherwise find out by trying.
 */
export const PERMISSIONS: {
  key: Permission
  label: string
  note?: string
}[] = [
  { key: "read_tasks", label: "Read tasks" },
  { key: "create_tasks", label: "Create tasks" },
  { key: "update_tasks", label: "Update tasks" },
  { key: "delete_tasks", label: "Delete tasks" },
  { key: "add_comments", label: "Add comments", note: "append-only" },
  { key: "create_tags", label: "Create tags" },
]

/**
 * What no setting is behind, drawn dashed where the grants are so the list
 * reads as the whole of it: reading tags is always allowed, since every bot
 * user reads its owner's whole vocabulary, and renaming or deleting them is
 * never allowed, like anything on projects or on comments already written
 * (FR-08.9, FR-08.10, ADR-0003).
 */
export const FIXED_PERMISSIONS = [
  { label: "Read tags", note: "always" },
  { label: "Rename or delete tags", note: "never" },
] as const

/** A scope's permissions with nothing granted: where a draft starts. */
export const NO_PERMISSIONS: BotPermissions = Object.fromEntries(
  PERMISSIONS.map(({ key }) => [key, false]),
) as unknown as BotPermissions
