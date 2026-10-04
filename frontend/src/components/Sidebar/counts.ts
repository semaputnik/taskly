import { useQuery } from "@tanstack/react-query"

import { OPEN_STATUSES } from "@/components/Tasks/statuses"
import { botsQuery, projectsQuery, tasksQuery } from "@/lib/serverState"

/** Past this the figure stops growing in the navigation; the screen has it. */
const MOST = 999

export interface NavCount {
  /** What the navigation shows beside the screen's name. */
  figure: string
  /** What a screen reader hears after the name, in words. */
  description: string
}

/**
 * The count beside a screen's name, where a count means something.
 *
 * Nothing is shown while the figure is on its way or when there is nothing
 * to count: an empty screen is said by the screen itself, and a `0` beside
 * every new account's navigation is noise.
 */
export function navCount(
  count: number | undefined,
  noun: string,
): NavCount | null {
  if (!count) return null
  return {
    figure: count > MOST ? `${MOST}+` : String(count),
    description: `${count} ${noun}${count === 1 ? "" : "s"}`,
  }
}

/**
 * The counts the navigation shows: open tasks (what the task list holds when
 * nothing narrows it), live projects and bot users. Projects and bots share
 * the screens' own query keys; the task count asks for one row under the
 * tasks root. Either way a change that makes a screen stale refreshes its
 * count too.
 */
export function useNavCounts(): Partial<Record<string, NavCount | null>> {
  const tasks = useQuery(
    tasksQuery({ status: OPEN_STATUSES, skip: 0, limit: 1 }),
  ).data?.count
  const projects = useQuery(projectsQuery()).data?.count
  const bots = useQuery(botsQuery()).data?.count
  return {
    "/tasks": navCount(tasks, "open task"),
    "/projects": navCount(projects, "project"),
    "/bots": navCount(bots, "bot user"),
  }
}
