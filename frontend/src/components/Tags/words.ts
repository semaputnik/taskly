import type { TagPublic } from "@/client"
import { allTasks, totalTasks } from "./counts"

/**
 * What the Tags page says in words: the sentence under the heading, who made
 * a tag, a look-alike group's line and what deleting costs. Plain functions,
 * so the wording can be read and tested apart from the page.
 */

const plural = (count: number, one: string, many = `${one}s`) =>
  `${count} ${count === 1 ? one : many}`

/** "urgent", "urgent and Urgent", "a, b and c". */
export function nameList(names: string[]): string {
  if (names.length < 2) return names.join("")
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
}

/**
 * The sentence under the heading. `lead` is set in ink, `rest` in grey.
 * `lookAlike` is how many tags sit in a group offered for merging.
 */
export function counts(
  tagCount: number,
  lookAlike: number,
): { lead: string; rest: string } {
  if (tagCount === 0) {
    return {
      lead: "No tags yet.",
      rest: "Type one onto a task, or start with New tag.",
    }
  }
  return {
    lead: `${plural(tagCount, "tag")}.`,
    rest: `${lookAlike === 0 ? "None look alike." : `${lookAlike} look alike.`} Tags are created by typing them onto a task, too.`,
  }
}

/** Who made a tag: "created by you", or by the bot user's name. */
export function createdBy(
  tag: Pick<TagPublic, "created_by_bot_user">,
  you = "you",
): string {
  const bot = tag.created_by_bot_user
  if (!bot) return `created by ${you}`
  return `created by ${bot.name}${bot.deleted ? " (deleted)" : ""}`
}

/** A group's open counts in the order of its names: "3 and 1 tasks". */
export function groupCounts(tags: Pick<TagPublic, "task_count">[]): string {
  const counts = tags.map((tag) => tag.task_count ?? 0)
  const last = counts[counts.length - 1]
  const words = nameList(counts.map(String))
  return `${words} ${counts.length === 1 && last === 1 ? "task" : "tasks"}`
}

/** The group's suggested survivor: the most used spelling, the first on a tie. */
export function suggestedSurvivor<T extends TagPublic>(tags: T[]): T {
  return tags.reduce((best, tag) =>
    totalTasks(tag) > totalTasks(best) ? tag : best,
  )
}

/** The Tasks row of the column: "4 open · 2 in archived projects". */
export function tasksInWords(
  tag: Pick<TagPublic, "task_count" | "archived_task_count">,
): string {
  const parts = [`${tag.task_count ?? 0} open`]
  const archived = tag.archived_task_count ?? 0
  if (archived > 0) {
    parts.push(
      `${archived} in ${archived === 1 ? "an archived project" : "archived projects"}`,
    )
  }
  return parts.join(" · ")
}

/** What deleting takes, said at the foot of the column before the act. */
export function deletionReach(
  tag: Pick<TagPublic, "task_count" | "archived_task_count">,
): string {
  if (totalTasks(tag) === 0) {
    return "No task carries it. Deleting can't be undone."
  }
  return `Deleting takes it off ${allTasks(tag)}. This can't be undone.`
}
