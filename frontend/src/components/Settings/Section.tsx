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
