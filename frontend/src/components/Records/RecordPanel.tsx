import type { LucideIcon } from "lucide-react"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

/**
 * The one shape a record is read and acted on in.
 *
 * Tasks had this and the other three record types had an overflow menu and a
 * family of single-purpose dialogs — rename in one, archive in another,
 * delete in a third. A menu is what a surface reaches for when it has not
 * decided where its actions belong. Here every action has a home: a field is
 * changed in the field, and delete is one destructive control in the corner.
 *
 * Everything that makes a panel a panel lives here, so a record type adopts
 * the pattern rather than reimplementing it (The One Address Rule).
 */

/**
 * Controls in a panel are flat until you reach for them.
 *
 * A property list of bordered inputs reads as a form to fill in; this is a
 * record to read that happens to be editable. `record-control` is what the
 * coarse-pointer rule in `index.css` hangs the touch affordance on, so a
 * control that can change is recognisable where there is no hover to reveal
 * it — and a read-only value, which never carries this, stays plainly not a
 * control.
 */
export const ghost =
  "record-control border-transparent bg-transparent shadow-none hover:bg-accent focus-visible:border-ring dark:bg-transparent dark:hover:bg-accent/50"

export function RecordPanel({
  open,
  onClose,
  /** What the panel is called when it is announced. */
  name,
  /** The one destructive act, in the corner beside close. */
  destructive,
  pending,
  /**
   * The record could not be read — it was deleted, or it belongs to somebody
   * else. A link that fails has to say so; a skeleton that never resolves
   * leaves the reader waiting for something that is never coming.
   */
  missing,
  /** What that record is called in the sentence saying it is gone. */
  kind = "record",
  children,
}: {
  open: boolean
  onClose: () => void
  name: string
  destructive?: React.ReactNode
  pending?: boolean
  missing?: boolean
  kind?: string
  children?: React.ReactNode
}) {
  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent
        side="right"
        className="w-full gap-0 overflow-y-auto p-0 sm:max-w-xl"
      >
        {/* The record the panel is showing, announced on arrival. */}
        <SheetTitle className="sr-only">{name}</SheetTitle>
        {missing ? (
          <div className="flex flex-col items-start gap-3 p-6">
            <p className="font-medium">This {kind} could not be opened</p>
            <p className="text-muted-foreground text-sm text-pretty">
              It has been deleted, or the link points at something that is not
              yours. Deleted records can be restored from the activity log.
            </p>
            <Button variant="outline" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        ) : pending ? (
          <div className="flex flex-col gap-4 p-6">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-7 w-3/4" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <>
            {/* Delete is a corner control like the close button, on the same
                line as one rather than floating in the header's flow beneath
                it. It is alone there: every other change to a record is made
                in the field it belongs to. */}
            {destructive && (
              <div className="absolute top-1.5 right-9 z-10">{destructive}</div>
            )}
            {children}
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

/**
 * Where the record sits, and its name as a control: the two things every
 * panel opens with, bordered off from the properties below.
 */
export function RecordHeader({
  breadcrumb,
  title,
}: {
  breadcrumb: React.ReactNode
  title?: React.ReactNode
}) {
  return (
    <SheetHeader className="gap-3 border-b p-6">
      <SheetDescription className="flex min-w-0 items-center gap-1 pr-20 text-sm">
        {breadcrumb}
      </SheetDescription>
      {title}
    </SheetHeader>
  )
}

/**
 * One property: an icon and its label in a column, the value beside it.
 *
 * The label column is proportional until there is room for a fixed one — on a
 * phone, 8rem of label leaves a third of the screen for the value it labels.
 */
export function PropertyRow({
  icon: Icon,
  label,
  htmlFor,
  children,
}: {
  icon: LucideIcon
  label: string
  htmlFor?: string
  children: React.ReactNode
}) {
  return (
    <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] items-center gap-2 py-1 md:grid-cols-[8rem_1fr]">
      <label
        htmlFor={htmlFor}
        className="text-muted-foreground flex items-center gap-2 text-sm"
      >
        <Icon className="size-4 shrink-0" aria-hidden />
        {label}
      </label>
      <div className="min-w-0 text-sm">{children}</div>
    </div>
  )
}

/** The property list of a record: hairline-separated rows. */
export function PropertyList({ children }: { children: React.ReactNode }) {
  return <div className="divide-y px-6 py-2">{children}</div>
}

/**
 * A value the record cannot change, said in words rather than shown as a
 * disabled control — a control that cannot be used still asks to be tried.
 */
export function ReadOnlyValue({ children }: { children: React.ReactNode }) {
  return <span className="text-muted-foreground px-2">{children}</span>
}

/** Text that saves when you leave it, and forgets the edit on Escape. */
export function EditableText({
  value,
  onCommit,
  multiline,
  className,
  placeholder,
  id,
  ariaLabel,
}: {
  value: string
  /**
   * Save the new value. Resolving to `false` says the save was refused, and
   * the field then keeps what was typed instead of snapping back to what the
   * server still holds — the words are the reader's, and the toast says what
   * went wrong.
   */
  onCommit: (next: string) => undefined | Promise<boolean>
  multiline?: boolean
  className?: string
  placeholder?: string
  id?: string
  ariaLabel?: string
}) {
  const [draft, setDraft] = useState(value)
  // The field is fed by the server after every save, and by a bot editing the
  // same record; re-sync unless the reader is the one holding the value.
  const [editing, setEditing] = useState(false)
  useEffect(() => {
    if (!editing) setDraft(value)
  }, [value, editing])

  const commit = async () => {
    if (draft === value) {
      setEditing(false)
      return
    }
    const saved = await onCommit(draft)
    setEditing(saved === false)
  }

  const shared = {
    id,
    "aria-label": ariaLabel,
    value: draft,
    placeholder,
    onFocus: () => setEditing(true),
    onBlur: () => void commit(),
    className: cn(ghost, className),
  }

  return multiline ? (
    <Textarea
      {...shared}
      rows={3}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          setDraft(value)
          setEditing(false)
          e.currentTarget.blur()
        }
      }}
    />
  ) : (
    <Input
      {...shared}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur()
        if (e.key === "Escape") {
          setDraft(value)
          setEditing(false)
          e.currentTarget.blur()
        }
      }}
    />
  )
}

/** The panel's own heading for a record's title, when it is a control. */
export const titleFieldClass =
  "h-auto px-2 py-1.5 text-xl leading-snug font-semibold md:text-xl"
