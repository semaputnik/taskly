import { afterEach, beforeEach, describe, expect, test } from "bun:test"
import {
  AxiosError,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios"

import type { TaskPublic } from "@/client"
import { client } from "@/client/client.gen"
import type { Change } from "@/lib/serverState"
import {
  createTask,
  deleteTask,
  PRIORITIES,
  setStatus,
  updateTask,
} from "./writes"

// The HTTP layer, replaced: each test says what the API answers, and reads
// back what was sent.
type Answer = { status: number; data: unknown }
let answer: Answer
let sent: { method?: string; url?: string; data?: unknown; params?: unknown }[]
const originalAdapter = client.instance.defaults.adapter

beforeEach(() => {
  answer = { status: 200, data: {} }
  sent = []
  client.instance.defaults.adapter = async (
    config: InternalAxiosRequestConfig,
  ) => {
    sent.push({
      method: config.method,
      url: config.url,
      data: config.data ? JSON.parse(config.data) : undefined,
      params: config.params,
    })
    const response: AxiosResponse = {
      ...answer,
      statusText: "",
      headers: {},
      config,
    }
    if (answer.status >= 400) {
      throw new AxiosError("refused", "ERR_BAD_REQUEST", config, {}, response)
    }
    return response
  }
})

afterEach(() => {
  client.instance.defaults.adapter = originalAdapter
})

const reports: Change[] = []
const report = (change: Change) => reports.push(change)
beforeEach(() => {
  reports.length = 0
})

const task = (overrides: Partial<TaskPublic> = {}): TaskPublic => ({
  id: "t1",
  title: "Water the plants",
  project_id: "p1",
  status: "todo",
  due_date: "2026-09-20",
  recurrence: null,
  ...overrides,
})

const recurring = task({
  id: "r1",
  title: "Take out the bins",
  recurrence: { frequency: "weekly" },
})

describe("a single task", () => {
  test("a saved update resolves to saved and reports the task", async () => {
    answer = { status: 200, data: task({ title: "Water the ferns" }) }

    const outcome = await updateTask(report, task(), {
      title: "Water the ferns",
    })

    expect(outcome.saved).toBe(true)
    expect(sent).toHaveLength(1)
    expect(sent[0].method).toBe("patch")
    expect(sent[0].data).toEqual({ title: "Water the ferns" })
    expect(reports).toEqual([{ type: "task changed", taskId: "t1" }])
  })

  test("a refused update resolves to refused, and still reports", async () => {
    answer = { status: 422, data: { detail: [{ msg: "Too long" }] } }

    const outcome = await updateTask(report, task(), { title: "x" })

    expect(outcome).toMatchObject({ saved: false, reason: "failed" })
    expect(reports).toEqual([{ type: "task changed", taskId: "t1" }])
  })

  test("moving an open occurrence's date waits for a scope", async () => {
    const waiting = await updateTask(report, recurring, {
      due_date: "2026-09-21",
    })

    expect(waiting).toEqual({ saved: false, reason: "needs scope" })
    expect(sent).toHaveLength(0)
    expect(reports).toHaveLength(0)

    answer = { status: 200, data: recurring }
    const saved = await updateTask(
      report,
      recurring,
      { due_date: "2026-09-21" },
      "this_occurrence",
    )
    expect(saved.saved).toBe(true)
    expect(sent[0].data).toEqual({
      due_date: "2026-09-21",
      due_date_scope: "this_occurrence",
    })
  })

  test("no scope is asked for a done occurrence or a new rule", async () => {
    for (const [target, body] of [
      [{ ...recurring, status: "done" as const }, { due_date: "2026-09-21" }],
      [
        recurring,
        { due_date: "2026-09-21", recurrence: { frequency: "daily" as const } },
      ],
      [task(), { due_date: "2026-09-21" }],
    ] as const) {
      const outcome = await updateTask(report, target, body)
      expect(outcome.saved).toBe(true)
    }
    expect(sent).toHaveLength(3)
  })

  test("an open-subtasks refusal is its own reason", async () => {
    answer = {
      status: 409,
      data: { detail: { code: "task_has_uncompleted_subtasks", message: "" } },
    }

    const outcome = await setStatus(report, task(), "done")

    expect(outcome).toEqual({ saved: false, reason: "open subtasks" })
    expect(sent[0].data).toEqual({ status: "done" })
    expect(reports).toEqual([{ type: "task changed", taskId: "t1" }])
  })

  test("a subtask cascade is its own reason", async () => {
    answer = {
      status: 409,
      data: { detail: { code: "task_has_subtasks", message: "" } },
    }

    const outcome = await deleteTask(report, task(), false)

    expect(outcome).toEqual({ saved: false, reason: "has subtasks" })
    expect(sent[0]).toMatchObject({
      method: "delete",
      url: "/api/v1/tasks/t1?delete_subtasks=false",
    })
    expect(reports).toEqual([{ type: "task deleted", taskId: "t1" }])
  })

  test("a creation reports a created task", async () => {
    answer = { status: 200, data: task() }

    const outcome = await createTask(report, { title: "Water the plants" })

    expect(outcome).toEqual({ saved: true, data: task() })
    expect(reports).toEqual([{ type: "task created" }])
  })
})

test("the priorities are the API's, highest first", () => {
  expect(PRIORITIES).toEqual(["P1", "P2", "P3", "P4"])
})
