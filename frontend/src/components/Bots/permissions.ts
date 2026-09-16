import type { BotPermissions } from "@/client"

type Permission = keyof BotPermissions

// Everything a bot user can be granted. What it can never do — anything on
// projects, editing or deleting comments, renaming or deleting tags — has no
// checkbox, because there is no setting behind it. Reading tags has none
// either: every bot user reads its owner's whole vocabulary (FR-08.9,
// FR-08.10, ADR-0003).
export const PERMISSIONS: { key: Permission; label: string }[] = [
  { key: "read_tasks", label: "Read tasks" },
  { key: "create_tasks", label: "Create tasks" },
  { key: "update_tasks", label: "Update tasks" },
  { key: "delete_tasks", label: "Delete tasks" },
  { key: "add_comments", label: "Add comments" },
  { key: "create_tags", label: "Create tags" },
]
