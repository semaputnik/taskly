import { afterEach, describe, expect, setSystemTime, test } from "bun:test"
import { QueryClient, QueryObserver, queryOptions } from "@tanstack/react-query"

import { configureServerState, warmQuery } from "./serverState"

/** A query whose requests are counted, answering at once. */
function counted(key: string) {
  const calls = { count: 0 }
  const options = queryOptions({
    queryKey: [key],
    queryFn: async () => {
      calls.count += 1
      return { answer: calls.count }
    },
  })
  return { calls, options }
}

/** A screen mounting on the query: an observer, as `useQuery` makes one. */
async function mount(client: QueryClient, options: object) {
  const observer = new QueryObserver(client, options as never)
  const unsubscribe = observer.subscribe(() => {})
  // Let a fetch the mount started settle.
  await new Promise((resolve) => setTimeout(resolve, 0))
  return unsubscribe
}

function client() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  configureServerState(queryClient)
  return queryClient
}

afterEach(() => setSystemTime())

describe("a request started ahead of its screen", () => {
  test("is asked once, not again by the screen that mounts on it", async () => {
    const queryClient = client()
    const { calls, options } = counted("warm")
    await warmQuery(queryClient, options)
    await mount(queryClient, options)
    expect(calls.count).toBe(1)
  })

  test("is asked again by a screen that mounts on it much later", async () => {
    const queryClient = client()
    const { calls, options } = counted("late")
    setSystemTime(new Date("2026-10-06T09:00:00Z"))
    await warmQuery(queryClient, options)
    setSystemTime(new Date("2026-10-06T09:01:00Z"))
    await mount(queryClient, options)
    expect(calls.count).toBe(2)
  })

  test("leaves an answer already cached alone, and the screen asks as before", async () => {
    const queryClient = client()
    const { calls, options } = counted("cached")
    await queryClient.fetchQuery(options)
    await warmQuery(queryClient, options)
    expect(calls.count).toBe(1)
    await mount(queryClient, options)
    expect(calls.count).toBe(2)
  })

  test("is asked again once a change has made it stale", async () => {
    const queryClient = client()
    const { calls, options } = counted("changed")
    await warmQuery(queryClient, options)
    await queryClient.invalidateQueries({ queryKey: options.queryKey })
    await mount(queryClient, options)
    expect(calls.count).toBe(2)
  })

  test("that fails is the screen's to ask again", async () => {
    const queryClient = client()
    let calls = 0
    const options = queryOptions({
      queryKey: ["fails"],
      queryFn: async () => {
        calls += 1
        if (calls === 1) throw new Error("unavailable")
        return "answer"
      },
    })
    expect(await warmQuery(queryClient, options)).toBeUndefined()
    await mount(queryClient, options)
    expect(calls).toBe(2)
    const answer: unknown = queryClient.getQueryData(options.queryKey)
    expect(answer).toBe("answer")
  })
})
