import { describe, expect, test } from "bun:test"
import { AxiosError, AxiosHeaders } from "axios"

import {
  batchRefusals,
  isRefusal,
  isSessionGone,
  Refusal,
  refusalCode,
  refusalMessage,
} from "./apiErrors"

function answered(status: number, detail: unknown): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError(
    `Request failed with status code ${status}`,
    "ERR_BAD_REQUEST",
    config,
    {},
    {
      status,
      statusText: "",
      headers: {},
      config,
      data: { detail },
    },
  )
}

const responses = {
  sessionGone: answered(401, "Could not validate credentials"),
  outsideScope: answered(403, {
    code: "outside_scope",
    message: "The project “Garden” is not in this bot user's scope.",
  }),
  superuserSelfDelete: answered(
    403,
    "Super users are not allowed to delete themselves",
  ),
  notFound: answered(404, "Task not found"),
  openSubtasks: answered(409, {
    code: "task_has_uncompleted_subtasks",
    message: "This task has open subtasks.",
  }),
  invalid: answered(422, [
    { loc: ["body", "title"], msg: "Field required", type: "missing" },
  ]),
  bulk: answered(409, {
    code: "bulk_refused",
    message: "2 of the tasks could not be changed, so none of them were.",
    refusals: [
      { task_id: "a", code: "project_archived", message: "“A” is archived." },
      { task_id: "b", code: "not_found", message: "Gone." },
    ],
  }),
  rateLimited: answered(429, "Too many requests"),
  network: new AxiosError("Network Error", "ERR_NETWORK"),
  plain: new Error(""),
}

describe("is the session gone", () => {
  test("only a 401 says so", () => {
    for (const [name, error] of Object.entries(responses)) {
      expect([name, isSessionGone(error)]).toEqual([
        name,
        name === "sessionGone",
      ])
    }
  })
})

describe("was it refused for what was asked", () => {
  test("a 4xx is, except what may pass on its own", () => {
    const refused = Object.entries(responses)
      .filter(([, error]) => isRefusal(error))
      .map(([name]) => name)
    expect(refused).toEqual([
      "sessionGone",
      "outsideScope",
      "superuserSelfDelete",
      "notFound",
      "openSubtasks",
      "invalid",
      "bulk",
    ])
  })
})

describe("which code", () => {
  test("is the one the detail carries, if any", () => {
    expect(refusalCode(responses.outsideScope)).toBe("outside_scope")
    expect(refusalCode(responses.openSubtasks)).toBe(Refusal.OPEN_SUBTASKS)
    expect(refusalCode(responses.bulk)).toBe(Refusal.BULK_REFUSED)
    for (const error of [
      responses.sessionGone,
      responses.notFound,
      responses.invalid,
      responses.network,
      responses.plain,
      undefined,
    ]) {
      expect(refusalCode(error)).toBeUndefined()
    }
  })
})

describe("what to tell the reader", () => {
  test("is what the API said, in whatever shape it said it", () => {
    expect(refusalMessage(responses.sessionGone)).toBe(
      "Could not validate credentials",
    )
    expect(refusalMessage(responses.outsideScope)).toBe(
      "The project “Garden” is not in this bot user's scope.",
    )
    expect(refusalMessage(responses.superuserSelfDelete)).toBe(
      "Super users are not allowed to delete themselves",
    )
    expect(refusalMessage(responses.invalid)).toBe("Field required")
  })

  test("says the server was not reached when nothing answered", () => {
    expect(refusalMessage(responses.network)).toBe("Network Error")
    expect(refusalMessage(responses.plain)).toBe(
      "The request did not reach the server.",
    )
  })
})

describe("per-item refusals", () => {
  test("are a batch's, and nothing else's", () => {
    expect(batchRefusals(responses.bulk)).toEqual([
      { task_id: "a", code: "project_archived", message: "“A” is archived." },
      { task_id: "b", code: "not_found", message: "Gone." },
    ])
    expect(batchRefusals(responses.openSubtasks)).toBeNull()
    expect(batchRefusals(responses.network)).toBeNull()
  })
})
