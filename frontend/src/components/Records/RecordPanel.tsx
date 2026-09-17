import { type LucideIcon, Trash2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"

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
import { Toaster } from "@/components/ui/sonner"
import { Textarea } from "@/components/ui/textarea"
import { PANEL_TOASTER_ID, settlePanelNotices } from "@/lib/panelNotices"
import { cn } from "@/lib/utils"
import type { RecordLoad } from "./panels"

/**
 * The one shape a record is read and acted on in.
 *
 * Tasks had this and the other three record types had an overflow menu and a
 * family of single-purpose dialogs — rename in one, archive in another,
 * delete in a third. A menu is what a surface reaches for when it has not
 * decided where its actions belong. Here every action has a home: a field is
 * changed in the field, and delete is one destructive control at the foot of
 * the panel, as far from the close control as the panel allows.
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
  /**
   * The one destructive act. It sits at the foot of the panel, never in the
   * corner: that corner is where a hand goes to dismiss, and a stray click
   * there must close the panel rather than start a deletion.
   */
  destructive,
  pending,
  failure,
  onRetry,
  /** What the record is called in the sentence saying it cannot be shown. */
  kind = "record",
  children,
}: {
  open: boolean
  onClose: () => void
  name: string
  destructive?: React.ReactNode
  kind?: string
  children?: React.ReactNode
} & RecordLoad) {
  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent
        side="right"
        className="w-full gap-0 overflow-y-auto p-0 outline-none sm:max-w-xl"
        // Opening a record puts focus on the panel itself, not on its first
        // control: that would be the name field, which a reader who only came
        // to look must not find already in their hands. Tab starts from here,
        // and capture claims its own field once the panel is open.
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          ;(event.target as HTMLElement).focus({ preventScroll: true })
        }}
      >
        {/* The record the panel is showing, announced on arrival. */}
        <SheetTitle className="sr-only">{name}</SheetTitle>
        {failure ? (
          <div role="alert" className="flex flex-col items-start gap-3 p-6">
            <p className="font-medium">
              {failure === "missing"
                ? `This ${kind} could not be opened`
                : `This ${kind} could not be loaded`}
            </p>
            <p className="text-muted-foreground text-sm text-pretty">
              {failure === "missing"
                ? "It may have been deleted, or the link points at something that is not yours. Deleted records can be restored from the activity log."
                : `The server did not answer this time. Nothing about the ${kind} has changed.`}
            </p>
            <div className="flex gap-2">
              {failure === "unavailable" && onRetry && (
                <Button size="sm" onClick={onRetry}>
                  Try again
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        ) : pending ? (
          <div className="flex flex-col gap-4 p-6">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-7 w-3/4" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <>
            {children}
            {destructive && (
              <div className="mt-auto flex flex-wrap gap-2 border-t px-6 py-4">
                {destructive}
              </div>
            )}
          </>
        )}
        <PanelNotices />
      </SheetContent>
    </Sheet>
  )
}

/**
 * The toaster for notices that offer an action, inside the panel where the
 * modal sheet still lets the reader reach them — by pointer, by Tab, and by
 * its Alt+T hotkey.
 */
function PanelNotices() {
  useEffect(() => settlePanelNotices, [])
  // No close button: Undo is the first stop inside a notice, and a notice that
  // is left alone runs out on its own.
  return (
    <Toaster
      id={PANEL_TOASTER_ID}
      toastOptions={{
        classNames: {
          actionButton: "pointer-coarse:h-11! pointer-coarse:px-4!",
        },
      }}
    />
  )
}

/**
 * The control that opens a record's delete confirmation.
 *
 * It says what it does in words rather than as a bare icon: it is the one
 * control on the panel whose consequence reaches past the panel.
 */
export function DeleteTrigger({
  label,
  onClick,
}: {
  label: string
  onClick: () => void
}) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className="text-muted-foreground hover:text-destructive -ml-2.5 pointer-coarse:h-11"
      onClick={onClick}
    >
      <Trash2 />
      {label}
    </Button>
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
      <SheetDescription className="flex min-w-0 items-center gap-1 pr-10 text-sm pointer-coarse:pr-14">
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
 *
 * The label sits beside the value's first line, not the middle of it: a value
 * that wraps — a task's tags — keeps its label where the eye expects it. Both
 * sides are at least one control tall, so a single-line row is centred as it
 * always was.
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
    <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] items-start gap-2 py-1 md:grid-cols-[8rem_1fr]">
      <label
        htmlFor={htmlFor}
        className="text-muted-foreground flex min-h-9 items-center gap-2 text-sm pointer-coarse:min-h-11"
      >
        <Icon className="size-4 shrink-0" aria-hidden />
        {label}
      </label>
      <div className="grid min-h-9 min-w-0 items-center text-sm pointer-coarse:min-h-11">
        {children}
      </div>
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
  return (
    <span className={cn("text-muted-foreground", valueInset)}>{children}</span>
  )
}

/**
 * Where a value's text starts in a property row: a control's padding plus its
 * border, so a read-only value or a link lines up with the select above it
 * rather than a few pixels short of it.
 */
export const valueInset = "px-[calc(--spacing(3)+1px)]"

/** The banded section a record's description sits in, on a record and a draft. */
export function DescriptionSection({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="border-t px-6 py-5">
      <h3 className={cn("mb-2 text-sm font-medium", valueInset)}>
        Description
      </h3>
      {children}
    </div>
  )
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
  // Whether the field holds words the reader typed and has not yet saved or
  // abandoned. Only those are ever sent: focus alone is not an edit, so a
  // field that was merely visited keeps following the server — a save made a
  // moment ago, or a bot editing the same record — and leaving it sends
  // nothing. A ref, because Escape and the blur it causes happen within one
  // event, before a re-render could tell the blur that the edit was dropped.
  const typed = useRef(false)
  useEffect(() => {
    if (!typed.current) setDraft(value)
  }, [value])

  const type = (next: string) => {
    typed.current = true
    setDraft(next)
  }

  const abandon = () => {
    typed.current = false
    setDraft(value)
  }

  const commit = async () => {
    if (!typed.current) return
    if (draft === value) {
      typed.current = false
      return
    }
    const saved = await onCommit(draft)
    // A refused save keeps the typed words in the field, still unsaved.
    typed.current = saved === false
  }

  const shared = {
    id,
    "aria-label": ariaLabel,
    value: draft,
    placeholder,
    onBlur: () => void commit(),
    className: cn(ghost, className),
  }

  return multiline ? (
    <Textarea
      {...shared}
      rows={3}
      onChange={(e) => type(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Escape") abandon()
      }}
    />
  ) : (
    <Input
      {...shared}
      onChange={(e) => type(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur()
        if (e.key === "Escape") abandon()
      }}
    />
  )
}

/** The panel's own heading for a record's title, when it is a control. */
export const titleFieldClass =
  "h-auto px-2 py-1.5 text-xl leading-snug font-semibold md:text-xl"
