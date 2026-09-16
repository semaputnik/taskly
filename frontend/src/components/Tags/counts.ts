import type { TagPublic } from "@/client"

/** How many tasks something reaches, live and archived apart. */
export type TaskCounts = Pick<TagPublic, "task_count" | "archived_task_count">

/** "1 task", "3 tasks". */
export function taskCountLabel(count: number): string {
  return count === 1 ? "1 task" : `${count} tasks`
}

/**
 * What a tag's live count leaves out, said beside it: the tasks archived with
 * their project. The count itself is the live tasks, because it links to the
 * task list and has to agree with it (FR-01.26).
 */
export function archivedNote(tag: TaskCounts): string | null {
  const archived = tag.archived_task_count ?? 0
  return archived > 0 ? `+ ${archived} in archived projects` : null
}

/**
 * Every task a tag is on, live and archived alike — what deleting or merging
 * it reaches — as the count and, where archived tasks are among them, where
 * they are: ["3 tasks", "1 of them in an archived project"].
 */
export function taskReach(counts: TaskCounts): [string, string | null] {
  const archived = counts.archived_task_count ?? 0
  const total = totalTasks(counts)
  if (archived === 0) return [taskCountLabel(total), null]
  const where = archived === 1 ? "an archived project" : "archived projects"
  if (total === 1) return ["1 task", `in ${where}`]
  return [
    taskCountLabel(total),
    total === archived ? `all in ${where}` : `${archived} of them in ${where}`,
  ]
}

/** `taskReach` as one phrase: "3 tasks, 1 of them in an archived project". */
export function allTasks(counts: TaskCounts): string {
  const [count, where] = taskReach(counts)
  return where ? `${count}, ${where}` : count
}

export function totalTasks(tag: TaskCounts): number {
  return (tag.task_count ?? 0) + (tag.archived_task_count ?? 0)
}
