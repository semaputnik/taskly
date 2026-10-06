import type { BotWebhooks, WebhookDeliveryPublic, WebhookKind } from "@/client"
import { dayHeading, formatTimeOf } from "@/lib/dates"

/**
 * What a bot user's webhooks and their deliveries say, in words: the state on
 * its line in the Bots list, and the last delivery under each URL in its
 * column. Plain functions, so the wording is read and tested apart from the
 * page.
 */

/** The two webhooks as the column labels them, and as a sentence names them. */
export const WEBHOOKS: {
  kind: WebhookKind
  label: string
  /** What an unset one means for the bot user, said in the empty row. */
  unset: string
  /** What it is called in a sentence: "the task webhook". */
  noun: string
}[] = [
  {
    kind: "task",
    label: "Task ready",
    unset: "this bot user is not told about tasks that become ready for it",
    noun: "task webhook",
  },
  {
    kind: "comment",
    label: "Comment",
    unset: "this bot user is not told about comments",
    noun: "comment webhook",
  },
]

/** Which webhooks are set, for the bot user's line; `null` when neither is. */
export function webhookStateInWords(webhooks: BotWebhooks): string | null {
  const task = Boolean(webhooks.task.url)
  const comment = Boolean(webhooks.comment.url)
  if (task && comment) return "both webhooks set"
  if (task) return "task webhook set"
  if (comment) return "comment webhook set"
  return null
}

/** Whether the last delivery of either webhook did not get through. */
export function deliveryFailing(webhooks: BotWebhooks): boolean {
  return [webhooks.task, webhooks.comment].some(
    (hook) => hook.last_delivery && !hook.last_delivery.success,
  )
}

/** "today 07:41", "yesterday 18:02", or the day and time after that. */
function whenInWords(at: string, now: Date): string {
  const day = dayHeading(at, now)
  const time = formatTimeOf(at)
  const named = day === "Today" || day === "Yesterday" ? day.toLowerCase() : day
  return `${named} ${time}`
}

function durationInWords(ms: number): string {
  return ms < 1
    ? "under 1 ms"
    : ms < 1000
      ? `${ms} ms`
      : `${(ms / 1000).toFixed(1)} s`
}

/**
 * One delivery, as the line under a webhook's URL says it. `verdict` is the
 * word in front, `failing` says whether it is drawn as a failure, and `detail`
 * is the rest: what kind of event, when, and what came back.
 */
export function deliveryInWords(
  delivery: WebhookDeliveryPublic,
  now = new Date(),
): { verdict: string; failing: boolean; detail: string } {
  const failing = !delivery.success
  const verdict = !failing
    ? "Delivered"
    : delivery.state === "pending"
      ? "Failed, retrying"
      : "Failed"

  // What came back: the server's own explanation when it has one (it already
  // names a refusing status), otherwise the status alone, and how long it took.
  const answer =
    delivery.error ??
    (delivery.status_code != null ? String(delivery.status_code) : null)
  const outcome = answer
    ? `${answer}${delivery.duration_ms != null ? ` in ${durationInWords(delivery.duration_ms)}` : ""}`
    : null

  const retry =
    delivery.state === "pending" && failing
      ? [
          `attempt ${delivery.attempts}`,
          delivery.next_attempt_at &&
            `next try ${whenInWords(delivery.next_attempt_at, now)}`,
        ]
      : []

  const detail = [
    delivery.event === "test" && "test",
    whenInWords(delivery.attempted_at, now),
    outcome,
    ...retry,
  ]
    .filter(Boolean)
    .join(" · ")
  return { verdict, failing, detail }
}
