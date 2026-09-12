import type { TaskPublic } from "@/client"

export interface TaskTree {
  /** Tasks in tree order: every task immediately followed by its subtasks. */
  tasks: TaskPublic[]
  /** How deep each task sits, keyed by task id. Root tasks are 0. */
  depths: Record<string, number>
}

/**
 * Arrange a flat list of tasks into tree order, keeping the order the API
 * returned within each set of siblings.
 *
 * A task whose parent is not in the list — the list is a page of the user's
 * tasks, so a parent can be missing — is shown as a root rather than dropped.
 */
export function buildTaskTree(tasks: TaskPublic[]): TaskTree {
  const present = new Set(tasks.map((task) => task.id))
  const children = new Map<string, TaskPublic[]>()
  const roots: TaskPublic[] = []

  for (const task of tasks) {
    const parentId =
      task.parent_id && present.has(task.parent_id) ? task.parent_id : null
    if (parentId === null) {
      roots.push(task)
      continue
    }
    const siblings = children.get(parentId)
    if (siblings) {
      siblings.push(task)
    } else {
      children.set(parentId, [task])
    }
  }

  const ordered: TaskPublic[] = []
  const depths: Record<string, number> = {}

  const visit = (task: TaskPublic, depth: number) => {
    ordered.push(task)
    depths[task.id] = depth
    for (const child of children.get(task.id) ?? []) {
      visit(child, depth + 1)
    }
  }
  for (const root of roots) {
    visit(root, 0)
  }

  return { tasks: ordered, depths }
}
