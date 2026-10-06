import { describe, expect, test } from "bun:test"

import type { BotWebhooks, WebhookDeliveryPublic } from "@/client"
import {
  deliveryFailing,
  deliveryInWords,
  webhookStateInWords,
} from "./webhookWords"

const delivery = (
  patch: Partial<WebhookDeliveryPublic> = {},
): WebhookDeliveryPublic => ({
  id: "d",
  event: "task.ready",
  attempted_at: new Date(2026, 9, 6, 7, 41).toISOString(),
  success: true,
  state: "delivered",
  attempts: 1,
  status_code: 200,
  duration_ms: 300,
  ...patch,
})

const hooks = (patch: Partial<BotWebhooks> = {}): BotWebhooks => ({
  task: {},
  comment: {},
  has_secret: false,
  ...patch,
})

describe("webhook state on a bot user's line", () => {
  test("says nothing for a bot user with no webhook", () => {
    expect(webhookStateInWords(hooks())).toBeNull()
  })

  test("names the one that is set, or says both", () => {
    expect(
      webhookStateInWords(hooks({ task: { url: "https://a.test" } })),
    ).toBe("task webhook set")
    expect(
      webhookStateInWords(hooks({ comment: { url: "https://a.test" } })),
    ).toBe("comment webhook set")
    expect(
      webhookStateInWords(
        hooks({
          task: { url: "https://a.test" },
          comment: { url: "https://b.test" },
        }),
      ),
    ).toBe("both webhooks set")
  })

  test("a last delivery that failed is flagged, one that arrived is not", () => {
    expect(
      deliveryFailing(
        hooks({ task: { url: "https://a.test", last_delivery: delivery() } }),
      ),
    ).toBe(false)
    expect(
      deliveryFailing(
        hooks({
          comment: {
            url: "https://a.test",
            last_delivery: delivery({
              success: false,
              state: "pending",
              status_code: 503,
            }),
          },
        }),
      ),
    ).toBe(true)
    expect(deliveryFailing(hooks())).toBe(false)
  })
})

describe("a delivery in words", () => {
  const now = new Date(2026, 9, 6, 12, 0)
  const at = (days: number) => new Date(2026, 9, 6 - days, 7, 41).toISOString()

  test("delivered says when, the status and how long it took", () => {
    const said = deliveryInWords(delivery(), now)
    expect(said.verdict).toBe("Delivered")
    expect(said.failing).toBe(false)
    expect(said.detail).toMatch(/^today \d.* · 200 in 300 ms$/)
  })

  test("a slow one is said in seconds", () => {
    expect(
      deliveryInWords(delivery({ duration_ms: 1840 }), now).detail,
    ).toMatch(/200 in 1\.8 s$/)
  })

  test("a test is said to be one", () => {
    expect(
      deliveryInWords(delivery({ event: "test", attempted_at: at(1) }), now)
        .detail,
    ).toMatch(/^test · yesterday \d/)
  })

  test("an older one is dated the product's way, not as today", () => {
    expect(
      deliveryInWords(delivery({ attempted_at: at(10) }), now).detail,
    ).not.toMatch(/^(today|yesterday)/i)
  })

  test("a failure gives the status, or the error when nothing answered", () => {
    expect(
      deliveryInWords(
        delivery({
          success: false,
          state: "failed",
          status_code: 500,
          attempts: 6,
        }),
        now,
      ),
    ).toMatchObject({ verdict: "Failed", failing: true })
    expect(
      deliveryInWords(
        delivery({
          success: false,
          state: "failed",
          status_code: null,
          error: "timed out after 10 s",
          duration_ms: null,
        }),
        now,
      ).detail,
    ).toMatch(/timed out after 10 s$/)
  })

  test("a refusing status is said once, in the server's words", () => {
    const said = deliveryInWords(
      delivery({
        success: false,
        state: "failed",
        status_code: 500,
        error: "The receiver answered 500",
        duration_ms: 120,
      }),
      now,
    )
    expect(said.detail).toMatch(/The receiver answered 500 in 120 ms$/)
    expect(said.detail).not.toContain("500 The")
  })

  test("one that will be tried again says so, and which attempt it was", () => {
    const said = deliveryInWords(
      delivery({
        success: false,
        state: "pending",
        status_code: 503,
        attempts: 2,
        next_attempt_at: new Date(2026, 9, 6, 12, 5).toISOString(),
      }),
      now,
    )
    expect(said.verdict).toBe("Failed, retrying")
    expect(said.failing).toBe(true)
    expect(said.detail).toContain("attempt 2")
    expect(said.detail).toContain("next try")
  })
})
