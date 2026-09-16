import type { TagPublic } from "@/client"

/** "1 task", "3 tasks". */
export function tasks(count: number): string {
  return count === 1 ? "1 task" : `${count} tasks`
}

/**
 * What a tag's live count leaves out, said beside it: the tasks archived with
 * their project. The count itself is the live tasks, because it links to the
 * task list and has to agree with it (semaputnik/taskly#85).
 */
export function archivedNote(tag: TagPublic): string | null {
  const archived = tag.archived_task_count ?? 0
  return archived > 0 ? `+ ${archived} in archived projects` : null
}

/**
 * Every task a tag is on, live and archived alike — what deleting or merging
 * it reaches — in words: "3 tasks, 1 of them in an archived project".
 */
export function allTasks(tag: TagPublic): string {
  const archived = tag.archived_task_count ?? 0
  const total = (tag.task_count ?? 0) + archived
  if (archived === 0) return tasks(total)
  const where = archived === 1 ? "an archived project" : "archived projects"
  if (total === 1) return `1 task, in ${where}`
  return total === archived
    ? `${tasks(total)}, all in ${where}`
    : `${tasks(total)}, ${archived} of them in ${where}`
}

export function totalTasks(tag: TagPublic): number {
  return (tag.task_count ?? 0) + (tag.archived_task_count ?? 0)
}
