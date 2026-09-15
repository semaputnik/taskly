import type { BotPermissions } from "@/client"

type Permission = keyof BotPermissions

// Everything a bot user can be granted. What it can never do — anything on
// projects, editing or deleting comments — has no checkbox, because there is
// no setting behind it (FR-08.9, FR-08.10).
export const PERMISSIONS: { key: Permission; label: string }[] = [
  { key: "read_tasks", label: "Read tasks" },
  { key: "create_tasks", label: "Create tasks" },
  { key: "update_tasks", label: "Update tasks" },
  { key: "delete_tasks", label: "Delete tasks" },
  { key: "add_comments", label: "Add comments" },
]
