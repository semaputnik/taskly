import { ChevronDown, ChevronUp, Trash2, X } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { RecordLoad } from "./panels"
import { SaveCue, SaveCueProvider } from "./saveCue"
import type { Neighbours } from "./walk"

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
 * It is a column beside the page, not a sheet over it: the page stays live,
 * with no scrim and no focus trap, so a reader can read down a list and open
 * the next line without closing anything. Where there is no room beside the
 * page — a phone, a narrow window — the column takes the whole screen.
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

/**
 * The column's side gutters: 36px beside the page, 16px on a phone, so the bar,
 * the title, the properties and every section start on one edge.
 */
export const gutter = "px-4 md:px-9"

/**
 * A property's value as a text button: 30px tall, flat at rest, tinted on
 * hover, with its chevron always in view in Ink 3 — a value that can change
 * says so at rest, where there is no hover to reveal it — and darkening to ink
 * on hover and focus. Written for a select's trigger (the chevron is its last
 * child); the margin pulls the text back onto the label column's edge, so the
 * tint reaches past the text and the text does not move.
 */
export const quiet =
  "record-control data-[size=default]:h-[30px] data-[size=default]:pointer-coarse:h-11 w-fit max-w-full -ml-2 gap-1.5 border-transparent bg-transparent px-2 py-0 text-[15px] shadow-none hover:bg-hover focus-visible:border-ring dark:bg-transparent dark:hover:bg-hover [&>svg:last-child]:size-3 [&>svg:last-child]:opacity-100 hover:[&>svg:last-child]:text-ink! focus-visible:[&>svg:last-child]:text-ink! data-[state=open]:[&>svg:last-child]:text-ink!"

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
  /** The records on either side of this one in the list it was opened from. */
  walk,
  onWalk,
  /** Where the record sits and who opened it, at the left of the bar. */
  bar,
  children,
}: {
  open: boolean
  onClose: () => void
  name: string
  destructive?: React.ReactNode
  kind?: string
  walk?: Neighbours | null
  onWalk?: (id: string) => void
  bar?: React.ReactNode
  children?: React.ReactNode
} & RecordLoad) {
  // Mounted only while open, so opening and closing are the column's mount
  // and unmount, and focus follows them.
  if (!open) return null
  return (
    <SaveCueProvider>
      <Column
        name={name}
        kind={kind}
        onClose={onClose}
        walk={walk}
        onWalk={onWalk}
        bar={bar}
      >
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
              <div className={cn("mt-auto", gutter)}>
                <div className="flex flex-wrap gap-2 border-t py-4">
                  {destructive}
                </div>
              </div>
            )}
          </>
        )}
      </Column>
    </SaveCueProvider>
  )
}

/**
 * The column itself: a landmark named for the record, a bar that is always
 * in reach, and the record scrolling beneath it on its own.
 *
 * Beside the page it sits in the shell's third grid track, held in place
 * while the page scrolls; below 1200px — no room for the navigation (200px),
 * the column (560px) and a page that can still be read — it is fixed over
 * everything, which is what "the whole screen" is.
 */
function Column({
  name,
  kind,
  onClose,
  walk,
  onWalk,
  bar,
  children,
}: {
  name: string
  kind: string
  onClose: () => void
  walk?: Neighbours | null
  onWalk?: (id: string) => void
  bar?: React.ReactNode
  children: React.ReactNode
}) {
  const column = useRef<HTMLElement>(null)
  useColumnFocus(column, name)
  useColumnKeys(column, { onClose, walk, onWalk })

  return (
    <aside
      ref={column}
      aria-label={name}
      tabIndex={-1}
      data-record-column
      className={cn(
        "bg-page border-rule-strong fixed inset-0 z-50 flex flex-col overflow-y-auto overscroll-contain outline-none",
        // Written out in full, as Tailwind finds classes by reading them.
        "min-[1200px]:sticky min-[1200px]:inset-auto min-[1200px]:top-0 min-[1200px]:z-auto min-[1200px]:h-svh min-[1200px]:w-[560px] min-[1200px]:self-start min-[1200px]:border-l",
      )}
    >
      <div className="bg-page sticky top-0 z-10 flex h-14 shrink-0 items-center gap-3 pr-3 pl-4 md:pr-[29px] md:pl-9 min-[1200px]:h-[52px]">
        {/* One bar: where the record sits, then the controls that act on the
            column. The context truncates; the controls never move. */}
        <div className="text-ink-3 relative flex min-w-0 flex-1 items-center gap-1.5 text-[13px]">
          {bar}
          <SaveCue />
        </div>
        <span className="flex shrink-0 items-center gap-1">
          {walk && (
            <span className="text-ink-3 mr-1 font-mono text-xs tabular-nums">
              {walk.position} of {walk.count}
            </span>
          )}
          {walk && onWalk && (
            <>
              <BarButton
                label={`Previous ${kind}`}
                disabled={!walk.previous}
                onClick={() => walk.previous && onWalk(walk.previous)}
              >
                <ChevronUp aria-hidden />
              </BarButton>
              <BarButton
                label={`Next ${kind}`}
                disabled={!walk.next}
                onClick={() => walk.next && onWalk(walk.next)}
              >
                <ChevronDown aria-hidden />
              </BarButton>
            </>
          )}
          <BarButton label="Close" onClick={onClose}>
            <X aria-hidden />
          </BarButton>
        </span>
      </div>
      {/* The record's name as the heading the sections beneath descend from. */}
      <h2 className="sr-only">{name}</h2>
      {children}
    </aside>
  )
}

/**
 * A control in the column's bar: 28px under a mouse, 44px under a thumb. At
 * the end of the list a walking control says so without leaving, so focus
 * that is on it stays where it is.
 */
function BarButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string
  disabled?: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-disabled={disabled || undefined}
      onClick={() => !disabled && onClick()}
      className={cn(
        "text-ink-3 focus-visible:ring-ring/50 grid size-7 place-items-center rounded-md outline-none focus-visible:ring-[3px] pointer-coarse:size-11 [&_svg]:size-4",
        disabled ? "opacity-40" : "hover:bg-hover hover:text-ink",
      )}
    >
      {children}
    </button>
  )
}

// Where focus was when the column opened, to give it back when the column
// closes. Module state, because switching from one kind of record to another
// unmounts one column and mounts the next in a single commit, and that is
// still one visit: the way back is to the line that started it.
let opener: HTMLElement | null = null
let closing: ReturnType<typeof setTimeout> | undefined

/**
 * Opening puts focus on the column itself, not on its first field: that would
 * be a name the reader who only came to look finds already in their hands.
 * Tab starts from here, and capture claims its own field once the column is
 * open. Closing returns focus to the line that opened it — unless the reader
 * has since put it somewhere of their own on the page.
 */
function useColumnFocus(
  column: React.RefObject<HTMLElement | null>,
  name: string,
) {
  useEffect(() => {
    const element = column.current
    if (!element) return
    if (closing !== undefined) {
      clearTimeout(closing)
      closing = undefined
    } else {
      const active = document.activeElement
      opener =
        active instanceof HTMLElement &&
        active !== document.body &&
        !element.contains(active)
          ? active
          : null
    }
    element.focus({ preventScroll: true })
    return () => {
      closing = setTimeout(() => {
        closing = undefined
        const target = opener
        opener = null
        const active = document.activeElement
        if (target?.isConnected && (!active || active === document.body)) {
          target.focus({ preventScroll: true })
        }
      }, 0)
    }
  }, [column])

  // The line that is open is where focus belongs on closing: after a walk, or
  // when a click left focus on nothing, it is not the first opener. The
  // router marks the open task's link, so that is where to look.
  // biome-ignore lint/correctness/useExhaustiveDependencies: `name` is how a walk is noticed
  useEffect(() => {
    const line = document.querySelector<HTMLElement>(
      'main a[aria-current="page"]',
    )
    if (line) opener = line
  }, [name])
}

/** A keyboard that is typing, picking or navigating a widget keeps its keys. */
const KEEPS_ARROWS = [
  "input",
  "textarea",
  "select",
  '[contenteditable=""]',
  '[contenteditable="true"]',
  "[aria-haspopup]",
  '[role="menu"]',
  '[role="listbox"]',
  '[role="combobox"]',
  '[role="slider"]',
  '[role="spinbutton"]',
  '[role="tablist"]',
  '[role="radiogroup"]',
  '[role="textbox"]',
  '[role="grid"]',
  '[role="tree"]',
].join(",")

/** A layer that is open over the page owns the keyboard until it is gone. */
const OPEN_LAYER = [
  '[role="dialog"][data-state="open"]',
  '[role="alertdialog"][data-state="open"]',
  '[role="menu"][data-state="open"]',
  '[role="listbox"]',
].join(",")

/** Where notices are shown. */
const NOTICES_SELECTOR = "[data-sonner-toaster]"

const EDITABLE =
  'input, textarea, select, [contenteditable=""], [contenteditable="true"]'

/**
 * Escape closes the column; ↓ and ↑ walk its list.
 *
 * Both give way to anything that has already answered the key — a menu or a
 * popover has called `preventDefault` by now — and the arrows only act when
 * focus is not in a text field, a select or an open menu, so they never steal
 * typing, caret movement or menu navigation.
 */
function useColumnKeys(
  column: React.RefObject<HTMLElement | null>,
  {
    onClose,
    walk,
    onWalk,
  }: {
    onClose: () => void
    walk?: Neighbours | null
    onWalk?: (id: string) => void
  },
) {
  // Read at the key press, so the listener is added once and never races a
  // render.
  const latest = useRef({ onClose, walk, onWalk })
  latest.current = { onClose, walk, onWalk }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing) return
      const target = event.target instanceof Element ? event.target : null
      if (target?.closest(NOTICES_SELECTOR)) return

      if (event.key === "Escape") {
        // A field on the page beside the column keeps its own Escape.
        if (target?.matches(EDITABLE) && !column.current?.contains(target)) {
          return
        }
        latest.current.onClose()
        return
      }

      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
        return
      }
      const { walk, onWalk } = latest.current
      if (!walk || !onWalk) return
      if (target?.closest(KEEPS_ARROWS) || document.querySelector(OPEN_LAYER)) {
        return
      }
      const to = event.key === "ArrowDown" ? walk.next : walk.previous
      if (!to) return
      event.preventDefault()
      onWalk(to)
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [column])
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
 * One property: its label in a 96px column, ink-3, and the value beside it.
 *
 * The label names its value. Where the value is one control, the label is that
 * control's `<label>`; where it is several (tags) or none (a read-only date),
 * the value is a group the label names. Both sides are 30px tall, so a
 * single-line row is centred; a value that wraps keeps its label on the first
 * line.
 */
export function PropertyRow({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor?: string
  children: React.ReactNode
}) {
  const labelId = useId()
  const text =
    "text-ink-3 flex h-[30px] items-center text-[13px] pointer-coarse:h-11"
  const value =
    "flex min-h-[30px] min-w-0 items-center gap-2 pointer-coarse:min-h-11"
  return (
    <div className="grid grid-cols-[88px_minmax(0,1fr)] items-start gap-x-4 md:grid-cols-[96px_minmax(0,1fr)]">
      {htmlFor ? (
        <>
          <label htmlFor={htmlFor} className={text}>
            {label}
          </label>
          <div className={value}>{children}</div>
        </>
      ) : (
        <>
          <span id={labelId} className={text}>
            {label}
          </span>
          {/* Not a `fieldset`: a fieldset's own box takes the row's minimum
              height but its content does not, so a short value sat at the top
              of a tall row (the Created row on a phone) instead of level
              with its label. */}
          {/* biome-ignore lint/a11y/useSemanticElements: a fieldset cannot centre its content, see above */}
          <div role="group" aria-labelledby={labelId} className={value}>
            {children}
          </div>
        </>
      )}
    </div>
  )
}

/** The property list of a record: a hairline above, a lighter one below. */
export function PropertyList({ children }: { children: React.ReactNode }) {
  return (
    // The rule sits on an inner box, so it runs between the gutters like every
    // other rule in the column.
    <div className={gutter}>
      <div className="border-rule-strong flex flex-col gap-0.5 border-t pt-2.5 pb-3.5">
        {children}
      </div>
    </div>
  )
}

/**
 * A value the record cannot change, said in words rather than shown as a
 * disabled control: a control that cannot be used still asks to be tried.
 */
export function ReadOnlyValue({ children }: { children: React.ReactNode }) {
  return <span className="text-ink-3 text-[15px]">{children}</span>
}

/** A section heading: 13px, 600, over a hairline. */
export function SectionHeading({
  children,
  count,
  action,
}: {
  children: React.ReactNode
  count?: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <h3 className="border-rule-strong flex items-baseline gap-2 border-b pb-2 text-[13px] font-semibold">
      {children}
      {count !== undefined && (
        <span className="text-ink-3 font-mono text-xs font-normal tabular-nums">
          {count}
        </span>
      )}
      {action && <span className="ml-auto font-normal">{action}</span>}
    </h3>
  )
}

/**
 * One section of a record: a heading over a hairline with its count in mono
 * and, at the right, the section's own action. The section is a named region,
 * so a screen reader can jump to it and a spec can find it.
 */
export function RecordSection({
  title,
  count,
  action,
  children,
}: {
  title: string
  count?: React.ReactNode
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section aria-label={title} className={cn("pt-[18px] pb-1", gutter)}>
      <SectionHeading count={count} action={action}>
        {title}
      </SectionHeading>
      {children}
    </section>
  )
}

/** The section a record's description sits in, on a record and a draft. */
export function DescriptionSection({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <RecordSection title="Description">
      <div className="pt-2">{children}</div>
    </RecordSection>
  )
}

/** Text that saves when you leave it, and forgets the edit on Escape. */
export function EditableText({
  value,
  onCommit,
  multiline,
  wrap,
  className,
  placeholder,
  id,
  ariaLabel,
  required,
}: {
  value: string
  /**
   * Said under the field when it is left empty: the old words come back and
   * this tells why. Without it an emptied field is saved as empty.
   */
  required?: string
  /**
   * Save the new value. Resolving to `false` says the save was refused, and
   * the field then keeps what was typed instead of snapping back to what the
   * server still holds — the words are the reader's, and the toast says what
   * went wrong.
   */
  onCommit: (next: string) => undefined | Promise<boolean>
  multiline?: boolean
  /**
   * One line of text that wraps when it is long, as a title does: Enter saves
   * it rather than breaking the line, and a pasted break becomes a space.
   */
  wrap?: boolean
  className?: string
  placeholder?: string
  id?: string
  ariaLabel?: string
}) {
  const [draft, setDraft] = useState(value)
  const [problem, setProblem] = useState("")
  const problemId = useId()
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
    setProblem("")
    setDraft(next)
  }

  const abandon = () => {
    typed.current = false
    setProblem("")
    setDraft(value)
  }

  const commit = async () => {
    if (!typed.current) return
    if (required && !draft.trim()) {
      abandon()
      setProblem(required)
      return
    }
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
    ...(required && {
      "aria-invalid": problem ? true : undefined,
      "aria-describedby": problemId,
    }),
  }

  // The reason is under the field, in a region that is always there so that
  // putting words in it is announced.
  const reason = required && (
    <p
      id={problemId}
      aria-live="polite"
      className="text-late not-empty:pt-0.5 text-[13px]"
    >
      {problem}
    </p>
  )

  if (wrap) {
    return (
      <div className="min-w-0">
        <Textarea
          {...shared}
          rows={1}
          onChange={(e) => type(e.target.value.replace(/\s*\n\s*/g, " "))}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) {
              e.preventDefault()
              e.currentTarget.blur()
            }
            if (e.key === "Escape") abandon()
          }}
        />
        {reason}
      </div>
    )
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

/**
 * A task's title: 22px, 600, wrapping rather than scrolling, flat until it is
 * reached for. For a textarea one row tall that grows with its text; the
 * margin puts its text on the gutter's edge.
 */
export const taskTitleClass =
  "min-h-0 resize-none -ml-2 px-2 py-1 text-[22px] leading-[1.25] font-semibold tracking-[-0.015em] md:text-[22px]"

/**
 * The line a task opens with: its status mark, which is the control that
 * closes it, and its title beside it. The draft has no mark yet.
 */
export function TitleRow({
  mark,
  children,
}: {
  mark?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div
      className={cn(
        "grid items-start gap-3 pt-2 pb-[18px]",
        mark ? "grid-cols-[22px_minmax(0,1fr)]" : "grid-cols-1",
        gutter,
      )}
    >
      {mark && <span className="mt-[7px] flex">{mark}</span>}
      {children}
    </div>
  )
}
