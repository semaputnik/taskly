import { describe, expect, test } from "bun:test"
import { partialMatchKey, type QueryKey } from "@tanstack/react-query"

import {
  activityQuery,
  botQuery,
  botsQuery,
  type Change,
  currentUserQuery,
  nearTagsQuery,
  projectQuery,
  projectsQuery,
  scopeProjectsQuery,
  staleKeys,
  tagDuplicatesQuery,
  tagMergePreviewQuery,
  tagQuery,
  tagSearchQuery,
  tagsQuery,
  tagVocabularyQuery,
  taskQuery,
  tasksQuery,
} from "./serverState"

/** Whether reporting `change` refreshes the query under `key`. */
const refreshes = (change: Change, key: QueryKey) =>
  staleKeys(change).some((stale) => partialMatchKey(key, stale))

const project = projectQuery("p1").queryKey
const otherProject = projectQuery("p2").queryKey
const task = taskQuery("t1").queryKey
const otherTask = taskQuery("t2").queryKey
const bot = botQuery("b1").queryKey
const keys = {
  currentUser: currentUserQuery().queryKey,
  projects: projectsQuery().queryKey,
  archivedProjects: projectsQuery({ archived: true }).queryKey,
  scopeProjects: scopeProjectsQuery().queryKey,
  tasks: tasksQuery({ status: ["todo"] }).queryKey,
  tags: tagsQuery().queryKey,
  tag: tagQuery("g1").queryKey,
  bots: botsQuery().queryKey,
  activity: activityQuery({ skip: 0, limit: 5 }).queryKey,
}

describe("what a change refreshes", () => {
  test("a task change refreshes lists, that task, counts and the log", () => {
    const change: Change = { type: "task changed", taskId: "t1" }
    for (const key of [
      keys.tasks,
      task,
      keys.activity,
      keys.projects,
      keys.archivedProjects,
      project,
      keys.tags,
      keys.tag,
    ]) {
      expect(refreshes(change, key)).toBe(true)
    }
    expect(refreshes(change, otherTask)).toBe(false)
    expect(refreshes(change, keys.bots)).toBe(false)
    expect(refreshes(change, keys.currentUser)).toBe(false)
  })

  test("creating or deleting a task moves project and tag counts", () => {
    for (const change of [
      { type: "task created" },
      { type: "task deleted", taskId: "t1" },
      { type: "tasks changed in bulk" },
    ] satisfies Change[]) {
      expect(refreshes(change, keys.projects)).toBe(true)
      expect(refreshes(change, project)).toBe(true)
      expect(refreshes(change, keys.tags)).toBe(true)
      expect(refreshes(change, keys.activity)).toBe(true)
      expect(refreshes(change, keys.tasks)).toBe(true)
    }
  })

  test("a batch refreshes every open task", () => {
    expect(refreshes({ type: "tasks changed in bulk" }, otherTask)).toBe(true)
  })

  test("a tag change reaches every task that carries it", () => {
    const change: Change = { type: "tag changed" }
    for (const key of [keys.tags, keys.tag, keys.tasks, task, keys.activity]) {
      expect(refreshes(change, key)).toBe(true)
    }
    expect(refreshes(change, keys.projects)).toBe(false)
  })

  test("a project change reaches that project, its tasks and the log", () => {
    const change: Change = { type: "project changed", projectId: "p1" }
    for (const key of [
      keys.projects,
      keys.scopeProjects,
      project,
      keys.tasks,
      task,
      keys.activity,
    ]) {
      expect(refreshes(change, key)).toBe(true)
    }
    expect(refreshes(change, otherProject)).toBe(false)
  })

  test("a bot user change reaches its tasks and the log", () => {
    const change: Change = { type: "bot user changed", botId: "b1" }
    for (const key of [keys.bots, bot, keys.tasks, task, keys.activity]) {
      expect(refreshes(change, key)).toBe(true)
    }
    expect(refreshes(change, botQuery("b2").queryKey)).toBe(false)
  })

  test("a restore brings back tasks, projects and counts", () => {
    const change: Change = { type: "deletion restored" }
    for (const key of [
      keys.tasks,
      task,
      keys.projects,
      project,
      keys.tags,
      keys.activity,
    ]) {
      expect(refreshes(change, key)).toBe(true)
    }
  })

  test("dismissing duplicates refreshes the suggestions alone", () => {
    const change: Change = { type: "tag duplicates dismissed" }
    expect(refreshes(change, tagDuplicatesQuery().queryKey)).toBe(true)
    expect(refreshes(change, keys.tags)).toBe(false)
  })

  test("an account change refreshes everything", () => {
    for (const key of Object.values(keys)) {
      expect(refreshes({ type: "account changed" }, key)).toBe(true)
    }
  })
})

describe("query keys", () => {
  const fixed: QueryKey[] = [
    tagsQuery().queryKey,
    tagVocabularyQuery().queryKey,
    tagDuplicatesQuery().queryKey,
    nearTagsQuery("x").queryKey,
    tagMergePreviewQuery("g1", ["g2"]).queryKey,
  ]

  test("no typed tag search can land on another tag key", () => {
    for (const text of [
      "",
      "vocabulary",
      "duplicates",
      "near",
      "list",
      "search",
      "merge-preview",
      "x",
    ]) {
      const search = tagSearchQuery(text).queryKey
      for (const other of fixed) {
        expect(partialMatchKey(search, other)).toBe(false)
        expect(partialMatchKey(other, search)).toBe(false)
      }
    }
  })

  test("the same request shares one key", () => {
    expect(tasksQuery({ limit: 5 }).queryKey).toEqual(
      tasksQuery({ limit: 5 }).queryKey,
    )
    expect(projectsQuery().queryKey).toEqual(
      projectsQuery({ archived: false }).queryKey,
    )
    expect(projectsQuery().queryKey).not.toEqual(
      projectsQuery({ archived: true }).queryKey,
    )
  })
})
