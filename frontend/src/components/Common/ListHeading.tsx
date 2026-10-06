/**
 * A page section's heading: 13px, 600, over a hairline, its count in mono. A
 * note sits at the right in the quiet ink, or an action where the section has
 * one of its own.
 */
export function ListHeading({
  children,
  count,
  note,
  action,
  id,
}: {
  children: string
  count?: number
  note?: string
  action?: React.ReactNode
  id?: string
}) {
  return (
    <h2
      id={id}
      className="border-rule-strong flex items-baseline gap-2 border-b pb-2 text-[13px] font-semibold"
    >
      {children}
      {count !== undefined && (
        <span className="text-ink-3 font-mono text-xs font-normal tabular-nums">
          {count}
        </span>
      )}
      {note && (
        <span className="text-ink-3 ml-auto text-[13px] font-normal">
          {note}
        </span>
      )}
      {action && <span className="ml-auto font-normal">{action}</span>}
    </h2>
  )
}
