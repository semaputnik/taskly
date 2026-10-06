/** A page section's heading: 13px, 600, over a hairline, its count in mono. */
export function ListHeading({
  children,
  count,
  note,
}: {
  children: string
  count: number
  note?: string
}) {
  return (
    <h2 className="border-rule-strong flex items-baseline gap-2 border-b pb-2 text-[13px] font-semibold">
      {children}
      <span className="text-ink-3 font-mono text-xs font-normal tabular-nums">
        {count}
      </span>
      {note && (
        <span className="text-ink-3 ml-auto text-[13px] font-normal">
          {note}
        </span>
      )}
    </h2>
  )
}
