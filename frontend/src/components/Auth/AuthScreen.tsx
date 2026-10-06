import { Link } from "@tanstack/react-router"
import { AppearanceChoice } from "@/components/Common/AppearanceChoice"
import { Wordmark } from "@/components/Common/Wordmark"
import { cn } from "@/lib/utils"

/**
 * A screen of the unauthenticated world: a centred column on the page
 * ground, the wordmark at its top, one heading, one sentence and what is to
 * be done, and at the foot where this is and how it looks. No card, no
 * split, no mark (the brief, slice 5).
 *
 * The foot says "Self-hosted at" the page's own host, since that is the
 * address every passkey is bound to (FR-12.4), and sets the appearance
 * control where an account with a saved preference does not yet exist.
 */
export function AuthScreen({
  heading,
  lede,
  children,
}: {
  heading: string
  lede: string
  children: React.ReactNode
}) {
  return (
    <main className="bg-page text-ink mx-auto flex min-h-svh w-full max-w-[420px] flex-col px-4 pt-8 pb-6 sm:px-0 sm:pt-10 sm:pb-8">
      <Wordmark asLink={false} />
      {/* The heading stands at one offset on every screen, so moving between
          sign in, sign up and recovery does not move it. */}
      <div className="flex flex-1 flex-col gap-3 pt-[clamp(40px,16vh,140px)] pb-10">
        <h1 className="text-[26px] leading-tight font-semibold tracking-[-0.02em]">
          {heading}
        </h1>
        <p className="text-ink-3 leading-normal">{lede}</p>
        {children}
      </div>
      <footer className="text-ink-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[12.5px]">
        <span>Self-hosted at {window.location.host}</span>
        <span className="flex items-center gap-3.5">
          Appearance
          <AppearanceChoice className="text-[12.5px]" />
        </span>
      </footer>
    </main>
  )
}

/** The one filled action of a screen: ink on the page, a thumb's height. */
export const authAction =
  "mt-3 h-11 w-full gap-2.5 rounded-lg text-[15px] font-medium pointer-coarse:h-12"

/** The links beneath the action: quiet text, the next step in ink. */
export function AuthLinks({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-ink-3 mt-2 flex flex-col gap-1.5 text-[13.5px]">
      {children}
    </div>
  )
}

export function AuthLink({
  lead,
  to,
  children,
}: {
  lead?: string
  to: "/login" | "/signup" | "/recover"
  children: React.ReactNode
}) {
  return (
    <span>
      {lead && `${lead} `}
      <Link
        to={to}
        className={cn(
          "text-ink focus-visible:ring-ring/50 rounded-sm font-medium underline underline-offset-[3px] outline-none focus-visible:ring-[3px]",
          "pointer-coarse:-my-3 pointer-coarse:inline-block pointer-coarse:py-3",
        )}
      >
        {children}
      </Link>
    </span>
  )
}

/**
 * What a screen says in a browser without passkey support, in place of its
 * action. There is no other way in, so it says so plainly rather than
 * offering one (FR-12.12).
 */
export function PasskeysUnsupported() {
  return (
    <p
      data-testid="passkeys-unsupported"
      className="text-ink-2 border-rule mt-4 border-t pt-3 text-[13.5px] leading-normal"
    >
      This browser can't use passkeys. Taskly signs in with passkeys only, so
      open it in a browser that supports them, such as a current Chrome, Safari,
      Firefox or Edge.
    </p>
  )
}

/**
 * A field set as a line: its label at the left, the value beside it, one
 * hairline beneath. Under focus the hairline is drawn in ink and doubled in
 * weight: the focus mark of the world, set on the line rather than around it.
 */
export function FieldLine({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor: string
  children: React.ReactNode
}) {
  return (
    <div className="border-rule-strong focus-within:border-ink flex h-11 items-center border-b focus-within:shadow-[0_1px_0_0_var(--ink)]">
      <label
        htmlFor={htmlFor}
        className="text-ink-3 mr-3 w-[76px] shrink-0 text-[12.5px]"
      >
        {label}
      </label>
      {children}
    </div>
  )
}

/** The input inside a `FieldLine`: no frame of its own. */
export const fieldInput =
  "placeholder:text-ink-3 text-ink h-full min-w-0 flex-1 bg-transparent text-base outline-none"
