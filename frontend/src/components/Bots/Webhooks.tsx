import { useMutation } from "@tanstack/react-query"
import { type FormEvent, useEffect, useId, useRef, useState } from "react"

import { BotsService, type BotUserPublic, type WebhookKind } from "@/client"
import { RecordSection } from "@/components/Records/RecordPanel"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { isRefusal, refusalMessage } from "@/lib/apiErrors"
import { useReportChange } from "@/lib/serverState"
import { toastError, toastSuccess } from "@/lib/toasts"
import { cn } from "@/lib/utils"
import { useShowWebhookSecret } from "./IssuedToken"
import { deliveryInWords, WEBHOOKS } from "./webhookWords"

/**
 * What the owner does with a text-sized action: flat at rest, a quiet tint on
 * hover, and a thumb-sized target on a touch screen.
 */
const action =
  "text-ink-2 hover:text-ink h-8 px-2 text-[13px] font-medium pointer-coarse:h-11"

/**
 * The webhooks of a bot user (F-11): where Taskly calls it back, what the
 * last call did, and the secret that signs them. Each of the two is set,
 * changed, cleared and tested here; the secret is made with the first URL and
 * shown once, here or after a regeneration.
 *
 * A deleted bot user keeps the section, read-only: its webhooks were cleared
 * when it was deleted (FR-11.13), and the section says so rather than going
 * missing.
 */
export function WebhooksSection({ bot }: { bot: BotUserPublic }) {
  const { webhooks } = bot
  const anySet = Boolean(webhooks.task.url || webhooks.comment.url)

  return (
    <RecordSection
      title="Webhooks"
      action={
        !bot.deleted && webhooks.has_secret ? (
          <RegenerateSecret bot={bot} />
        ) : undefined
      }
    >
      <div>
        {WEBHOOKS.map((spec) => (
          <WebhookRow key={spec.kind} bot={bot} {...spec} />
        ))}
      </div>
      <p className="text-ink-3 pt-2 text-[12.5px] text-pretty">
        {bot.deleted
          ? "Webhooks were cleared when this bot user was deleted. Nothing is sent to it."
          : anySet
            ? "Every delivery is signed with this bot user's secret, which was shown once when it was made."
            : "The first URL set makes this bot user's secret, which signs every delivery and is shown once."}
      </p>
    </RecordSection>
  )
}

function WebhookRow({
  bot,
  kind,
  label,
  noun,
  unset,
}: {
  bot: BotUserPublic
  kind: WebhookKind
  label: string
  unset: string
  noun: string
}) {
  const hook = bot.webhooks[kind]
  const url = hook.url ?? null
  const [editing, setEditing] = useState(false)
  const test = useTestWebhook(bot, kind)
  const last = hook.last_delivery ? deliveryInWords(hook.last_delivery) : null

  return (
    <section
      aria-label={`${label} webhook`}
      className="border-rule grid gap-x-4 gap-y-1 border-b py-2.5 last:border-b-0 sm:grid-cols-[96px_minmax(0,1fr)]"
    >
      <h4 className="text-ink-3 pt-1 text-[13px] font-normal">{label}</h4>
      <div className="flex min-w-0 flex-col gap-1">
        {editing ? (
          <UrlForm
            bot={bot}
            kind={kind}
            label={label}
            current={url}
            onDone={() => setEditing(false)}
          />
        ) : (
          <>
            {url ? (
              <p className="pt-1 font-mono text-[12.5px] leading-snug break-all">
                {url}
              </p>
            ) : (
              <p className="text-ink-3 pt-0.5 text-sm text-pretty">
                Not set · {unset}
              </p>
            )}
            {url && (
              // Polite, because a test changes it while the reader's eyes are
              // on the button that sent it.
              <p
                aria-live="polite"
                className="text-ink-3 text-[12.5px] leading-snug text-pretty"
              >
                {last ? (
                  <>
                    <span
                      className={cn(
                        "mr-3 font-medium",
                        last.failing ? "text-late" : "text-done",
                      )}
                    >
                      {last.verdict}
                    </span>
                    <span>{last.detail}</span>
                  </>
                ) : (
                  <span>No delivery yet</span>
                )}
              </p>
            )}
            {!bot.deleted && (
              <div className="-ml-2 flex flex-wrap items-center">
                {url ? (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      className={action}
                      disabled={test.isPending}
                      onClick={() => test.mutate()}
                    >
                      {test.isPending ? "Sending…" : "Send a test"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className={action}
                      onClick={() => setEditing(true)}
                    >
                      Change
                    </Button>
                    <ClearWebhook bot={bot} kind={kind} noun={noun} />
                  </>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    className={action}
                    onClick={() => setEditing(true)}
                  >
                    Set a URL
                  </Button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}

/**
 * The field a URL is typed in. The server holds the rules (FR-11.3), so a
 * refusal is shown where the address was typed, in the server's words, with
 * what was typed kept for correcting.
 */
function UrlForm({
  bot,
  kind,
  label,
  current,
  onDone,
}: {
  bot: BotUserPublic
  kind: WebhookKind
  label: string
  current: string | null
  onDone: () => void
}) {
  const [value, setValue] = useState(current ?? "")
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const errorId = useId()
  const showSecret = useShowWebhookSecret()
  const reportChange = useReportChange()

  useEffect(() => input.current?.focus(), [])

  const mutation = useMutation({
    mutationFn: (url: string) =>
      BotsService.setBotUserWebhook({
        path: { bot_user_id: bot.id, kind },
        body: { url },
      }),
    onSuccess: ({ data }) => {
      onDone()
      // The secret is in this response and nowhere else.
      if (data.secret) showSecret({ botName: bot.name, secret: data.secret })
      reportChange({ type: "bot webhooks changed", botId: bot.id })
    },
    onError: (failure) => {
      // A refusal is about the address, so it is said at the address; a
      // failure to reach the server is not, and is a notice.
      if (isRefusal(failure)) setError(refusalMessage(failure))
      else toastError(failure)
    },
  })

  const save = (event: FormEvent) => {
    event.preventDefault()
    const url = value.trim()
    if (!url) {
      setError("Enter the address to call, starting with http:// or https://.")
      return
    }
    if (url === current) {
      onDone()
      return
    }
    setError(null)
    mutation.mutate(url)
  }

  return (
    <form
      noValidate
      onSubmit={save}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          // Forgets the edit and nothing more: the column stays open.
          event.preventDefault()
          event.stopPropagation()
          onDone()
        }
      }}
      className="flex flex-col gap-2"
    >
      <Input
        ref={input}
        aria-label={`${label} URL`}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        inputMode="url"
        autoComplete="off"
        autoCapitalize="none"
        spellCheck={false}
        placeholder="https://"
        value={value}
        onChange={(event) => {
          setValue(event.target.value)
          setError(null)
        }}
        className="h-9 font-mono text-base md:text-[12.5px]"
      />
      {error && (
        <p
          id={errorId}
          role="alert"
          className="text-late text-[12.5px] leading-snug text-pretty"
        >
          {error}
        </p>
      )}
      <div className="-ml-2 flex items-center">
        <LoadingButton
          type="submit"
          size="sm"
          className="mr-1 ml-2 pointer-coarse:h-11"
          loading={mutation.isPending}
        >
          Save
        </LoadingButton>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={action}
          disabled={mutation.isPending}
          onClick={onDone}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}

/**
 * Sends a test event to the URL at once. A failed test is still an answer:
 * the server records it as the last delivery, and the row shows it.
 */
function useTestWebhook(bot: BotUserPublic, kind: WebhookKind) {
  const reportChange = useReportChange()
  return useMutation({
    mutationFn: () =>
      BotsService.testBotUserWebhook({
        path: { bot_user_id: bot.id, kind },
      }),
    onError: (failure) => toastError(failure),
    onSettled: () =>
      reportChange({ type: "bot webhooks changed", botId: bot.id }),
  })
}

/**
 * Clears one webhook. Events still waiting for it are discarded and, when it
 * was the last one set, so is the secret — which cannot be got back — so it
 * is confirmed first, with what is lost said before the button.
 */
function ClearWebhook({
  bot,
  kind,
  noun,
}: {
  bot: BotUserPublic
  kind: WebhookKind
  noun: string
}) {
  const [isOpen, setIsOpen] = useState(false)
  const reportChange = useReportChange()
  const other = kind === "task" ? bot.webhooks.comment : bot.webhooks.task
  const last = !other.url

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.clearBotUserWebhook({
        path: { bot_user_id: bot.id, kind },
      }),
    onSuccess: () => {
      toastSuccess(`The ${noun} was cleared`)
      setIsOpen(false)
    },
    onError: (failure) => toastError(failure),
    onSettled: () =>
      reportChange({ type: "bot webhooks changed", botId: bot.id }),
  })

  return (
    <ConfirmDialog
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      trigger={
        <Button
          variant="ghost"
          size="sm"
          className={cn(action, "hover:text-late")}
          onClick={() => setIsOpen(true)}
        >
          Clear
        </Button>
      }
      title={`Clear the ${noun} of ${bot.name}?`}
      confirm="Clear webhook"
      destructive
      pending={mutation.isPending}
      onConfirm={() => mutation.mutate()}
    >
      Taskly stops calling this address, and deliveries still waiting for it are
      discarded.
      {last
        ? " It is the last webhook set, so the secret is discarded too: the next URL set makes a new one, shown once."
        : " The other webhook and the secret stay as they are."}
    </ConfirmDialog>
  )
}

/**
 * Makes a new secret. The receiver still checks the old one, so this is a
 * step to take with the receiver in hand: it is confirmed, and the new
 * secret is shown once.
 */
function RegenerateSecret({ bot }: { bot: BotUserPublic }) {
  const [isOpen, setIsOpen] = useState(false)
  const showSecret = useShowWebhookSecret()
  const reportChange = useReportChange()

  const mutation = useMutation({
    mutationFn: () =>
      BotsService.regenerateBotUserWebhookSecret({
        path: { bot_user_id: bot.id },
      }),
    onSuccess: ({ data }) => {
      setIsOpen(false)
      showSecret({ botName: bot.name, secret: data.secret })
      reportChange({ type: "bot webhooks changed", botId: bot.id })
    },
    onError: (failure) => toastError(failure),
  })

  return (
    <ConfirmDialog
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      trigger={
        <Button
          variant="ghost"
          size="sm"
          className="text-ink-3 hover:text-ink -my-1.5 -mr-2 h-8 px-2 text-[13px] font-normal pointer-coarse:h-11"
          onClick={() => setIsOpen(true)}
        >
          Regenerate secret
        </Button>
      }
      title={`Regenerate the webhook secret of ${bot.name}?`}
      confirm="Regenerate"
      pending={mutation.isPending}
      onConfirm={() => mutation.mutate()}
    >
      From the next delivery on, requests are signed with a new secret, and a
      receiver still checking the old one will refuse them. The new secret is
      shown once.
    </ConfirmDialog>
  )
}

/**
 * The question both irreversible webhook steps ask first: what is about to
 * be lost, said before the button that does it.
 */
function ConfirmDialog({
  isOpen,
  onOpenChange,
  trigger,
  title,
  children,
  confirm,
  destructive = false,
  pending,
  onConfirm,
}: {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  trigger: React.ReactNode
  title: string
  children: React.ReactNode
  confirm: string
  destructive?: boolean
  pending: boolean
  onConfirm: () => void
}) {
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      {trigger}
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{children}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={pending}>
              Cancel
            </Button>
          </DialogClose>
          <LoadingButton
            variant={destructive ? "destructive" : undefined}
            loading={pending}
            onClick={onConfirm}
          >
            {confirm}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
