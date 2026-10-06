import type { BotUserPublic, ProjectPublic } from "@/client"
import { nameList, plural } from "@/components/Common/words"
import { taskCountLabel } from "@/components/Tags/counts"

/**
 * What the Projects page says in words: the sentence of counts under the
 * heading, the facts on a project's line, and the bot users that work in it.
 * Plain functions, so the wording can be read and tested apart from the page.
 */

type Counted = Pick<
  ProjectPublic,
  "open_count" | "overdue_count" | "backlog_count" | "review_count" | "name"
>

/**
 * The sentence under the heading: how many projects and open tasks, then
 * whether anything is overdue and where. `lead` is set in ink, `rest` in grey.
 */
export function counts(projects: Counted[]): { lead: string; rest: string } {
  const open = projects.reduce((sum, p) => sum + (p.open_count ?? 0), 0)
  const late = projects.filter((p) => (p.overdue_count ?? 0) > 0)
  const overdue = late.reduce((sum, p) => sum + (p.overdue_count ?? 0), 0)
  return {
    lead: `${plural(projects.length, "project")}, ${plural(open, "open task")}.`,
    rest:
      overdue === 0
        ? "Nothing is overdue."
        : `${overdue} ${overdue === 1 ? "is" : "are"} overdue, in ${nameList(late.map((p) => p.name))}.`,
  }
}

/** The bot users whose scope names the project, by name. */
export function botsIn(
  projectId: string,
  bots: Pick<BotUserPublic, "name" | "scope">[],
): string[] {
  return bots
    .filter((bot) => bot.scope.project_ids.includes(projectId))
    .map((bot) => bot.name)
}

/** "inbox-triage works here", "inbox-triage, release-bot work here". */
export function botsInWords(names: string[]): string | null {
  if (names.length === 0) return null
  return `${names.join(", ")} ${names.length === 1 ? "works" : "work"} here`
}

/** A line's facts, in the order they matter: late first, then where work waits. */
export function metaFacts(
  project: Counted,
  names: string[],
): { text: string; late?: boolean }[] {
  const facts: { text: string; late?: boolean }[] = []
  if ((project.overdue_count ?? 0) > 0) {
    facts.push({ text: `${project.overdue_count} overdue`, late: true })
  }
  if ((project.backlog_count ?? 0) > 0) {
    facts.push({ text: `${project.backlog_count} in Backlog` })
  }
  if ((project.review_count ?? 0) > 0) {
    facts.push({ text: `${project.review_count} in Review` })
  }
  const bots = botsInWords(names)
  if (bots) facts.push({ text: bots })
  return facts
}

/** The Tasks row of the column: "9 open · 1 overdue · 6 done". */
export function tasksInWords(project: Counted & { done_count?: number }) {
  const parts = [`${project.open_count ?? 0} open`]
  if ((project.overdue_count ?? 0) > 0) {
    parts.push(`${project.overdue_count} overdue`)
  }
  parts.push(`${project.done_count ?? 0} done`)
  return parts.join(" · ")
}

/** The link on an archived project's line: "4 tasks". */
export function keptInWords(project: Pick<ProjectPublic, "task_count">) {
  return taskCountLabel(project.task_count ?? 0)
}

/** What deleting costs, said before the act. */
export function deletionReach(taskCount: number): string {
  if (taskCount === 0) return "It holds no tasks."
  return `Its ${taskCount === 1 ? "task goes" : `${taskCount} tasks go`} with it.`
}
