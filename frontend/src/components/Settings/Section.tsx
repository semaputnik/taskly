import { ListHeading } from "@/components/Common/ListHeading"
import { textLink } from "@/components/Dashboard/shared"
import { cn } from "@/lib/utils"

/** A section's action, in words, as the mock sets it: ink, 13.5px, medium. */
export const act = cn(
  textLink,
  "text-ink text-[13.5px] font-medium whitespace-nowrap disabled:pointer-events-none disabled:opacity-50 pointer-coarse:-my-3 pointer-coarse:py-3",
)

/** The quieter of two actions on a line: the one that takes something away. */
export const actQuiet = cn(act, "text-ink-3 hover:text-ink font-normal")

/**
 * A field edited in place, set as a line: no frame, a hairline beneath, and
 * under focus the hairline drawn in ink and doubled in weight (the same mark
 * as the sign-in screens' `FieldLine`). 16px under a coarse pointer, so a
 * phone does not zoom in on it.
 */
export const lineInput = cn(
  "text-ink placeholder:text-ink-3 h-[30px] w-full min-w-0 rounded-none border-0 border-b border-rule-strong bg-transparent px-0 text-base outline-none md:text-sm",
  "focus:border-ink focus:shadow-[0_1px_0_0_var(--ink)] aria-[invalid=true]:border-late aria-[invalid=true]:shadow-[0_1px_0_0_var(--late)]",
  "pointer-coarse:h-11",
)

/**
 * The commit and the way out of an edit in place, as the page's own text
 * actions: Save in ink, Cancel quiet. More actions of the form (Test) go
 * between them as `children`.
 */
export function EditActions({
  save,
  pending,
  onCancel,
  children,
}: {
  save: string
  pending: boolean
  onCancel: () => void
  children?: React.ReactNode
}) {
  return (
    <div className="flex h-[30px] items-center gap-3.5 pointer-coarse:h-11">
      <button
        type="submit"
        className={act}
        disabled={pending}
        aria-busy={pending}
      >
        {save}
      </button>
      {children}
      <button
        type="button"
        className={actQuiet}
        disabled={pending}
        onClick={onCancel}
      >
        Cancel
      </button>
    </div>
  )
}

/**
 * One section of the Settings document: a heading over a hairline, with its
 * count and its own action at the right where it has them, and what it holds
 * below. The section is named by its heading, so a screen reader can jump to
 * it and an address (`/settings#users`) can land on it.
 */
export function SettingsSection({
  id,
  title,
  count,
  action,
  children,
}: {
  id: string
  title: string
  count?: number
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      className="scroll-mt-6 pt-[22px] pb-1.5"
    >
      <ListHeading id={`${id}-heading`} count={count} action={action}>
        {title}
      </ListHeading>
      <div className="pt-1.5">{children}</div>
    </section>
  )
}

/** A quiet line under a section's content. */
export function Note({ children }: { children: React.ReactNode }) {
  return <p className="text-ink-3 mt-2 text-[12.5px] text-pretty">{children}</p>
}
