import type { BotPermissions } from "@/client"

type Permission = keyof BotPermissions

// Everything a bot user can be granted, gathered by the kind of access it
// gives. What it can never do — anything on projects, editing or deleting
// comments, renaming or deleting tags — has no checkbox, because there is no
// setting behind it. Reading tags has none either: every bot user reads its
// owner's whole vocabulary (FR-08.9, FR-08.10, ADR-0003).
export const PERMISSION_GROUPS: {
  title: string
  permissions: { key: Permission; label: string }[]
}[] = [
  {
    title: "Tasks",
    permissions: [
      { key: "read_tasks", label: "Read tasks" },
      { key: "create_tasks", label: "Create tasks" },
      { key: "update_tasks", label: "Update tasks" },
      { key: "delete_tasks", label: "Delete tasks" },
    ],
  },
  {
    title: "Comments",
    permissions: [{ key: "add_comments", label: "Add comments" }],
  },
  {
    title: "Tags",
    permissions: [{ key: "create_tags", label: "Create tags" }],
  },
]

/** The same grants as one list, for the surfaces that only name them. */
export const PERMISSIONS = PERMISSION_GROUPS.flatMap(
  (group) => group.permissions,
)
