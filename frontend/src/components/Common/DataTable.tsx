import {
  type ColumnDef,
  flexRender,
  type RowData,
  tableFeatures,
  useTable,
} from "@tanstack/react-table"
import {
  ArrowDown,
  ArrowUp,
  ChevronsUpDown,
  MoveHorizontal,
} from "lucide-react"

import { Checkbox } from "@/components/ui/checkbox"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

// v9's core row model is implicit. Paging is the server's: a table that pages
// an array it was handed can only ever page what it was handed, and would
// report that window as the total.
const features = tableFeatures({})

export type DataTableFeatures = typeof features

/** Selecting rows, for a table whose rows can be acted on as a batch. */
export interface DataTableSelection<TData> {
  /** The selected ids, which may reach beyond the page on screen. */
  ids: ReadonlySet<string>
  idOf: (row: TData) => string
  label: (row: TData) => string
  onToggle: (id: string, selected: boolean) => void
  /** Select or clear every row on this page. */
  onTogglePage: (ids: string[], selected: boolean) => void
}

/** Sorting a table by its headers, applied by the server. */
export interface DataTableSorting {
  /** Column id → the field the API sorts by. */
  fields: Record<string, string>
  field?: string
  descending?: boolean
  onSort: (field: string) => void
}

interface DataTableProps<TData extends RowData> {
  columns: ColumnDef<DataTableFeatures, TData, unknown>[]
  data: TData[]
  /**
   * What to show instead of rows. Only the caller knows whether the list is
   * empty because nothing exists yet or because a filter excluded everything,
   * and those two need different words — so the table does not guess.
   */
  empty?: React.ReactNode
  /** Makes rows open something. Clicks on a row's own controls are ignored. */
  onRowClick?: (row: TData) => void
  /**
   * What opening a row does, in words. A row that acts is a control, and a
   * control without a name is unusable to anyone not looking at the screen.
   */
  rowLabel?: (row: TData) => string
  /**
   * Draw the table's own skeleton while the data is on its way. It is built
   * from these columns, so it cannot describe a table that is not coming, and
   * the page does not jump when the rows land.
   */
  pending?: boolean
  /** How many rows to expect, so the skeleton reserves the right height. */
  pendingRows?: number
  selection?: DataTableSelection<TData>
  sorting?: DataTableSorting
  /** Names the sideways scroll, for a table too wide for a narrow screen. */
  scrollLabel?: string
}

/**
 * A row can hold checkboxes, menus and links, and clicking one of those means
 * that control — not "open the row". Asking the event where it landed keeps
 * the rule in one place, rather than making every cell remember to stop
 * propagation.
 */
const INTERACTIVE = 'button, a, input, select, textarea, [role="checkbox"]'

function fromRowItself(event: React.MouseEvent<HTMLElement>): boolean {
  const target = event.target as HTMLElement | null
  return !target?.closest(INTERACTIVE)
}

export function DataTable<TData extends RowData>({
  columns,
  data,
  empty,
  onRowClick,
  rowLabel,
  pending = false,
  pendingRows = 5,
  selection,
  sorting,
  scrollLabel,
}: DataTableProps<TData>) {
  const table = useTable({ features, data, columns })
  const pageIds = selection ? data.map(selection.idOf) : []
  const wholePage =
    pageIds.length > 0 && pageIds.every((id) => selection?.ids.has(id))
  const columnCount = columns.length + (selection ? 1 : 0)

  return (
    <>
      {/* The row is wider than a phone, and a table that simply stops at the
          screen edge looks like a table that ends there. Naming the scroll
          makes it a region the keyboard can reach, and the container's edge
          shadows say there is more where it came from. */}
      <Table scrollLabel={scrollLabel}>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="hover:bg-transparent">
              {selection && (
                <TableHead className="w-10">
                  <Checkbox
                    checked={wholePage}
                    disabled={pageIds.length === 0}
                    aria-label="Select every task on this page"
                    onCheckedChange={(checked) =>
                      selection.onTogglePage(pageIds, checked === true)
                    }
                  />
                </TableHead>
              )}
              {headerGroup.headers.map((header) => {
                const field = sorting?.fields[header.column.id]
                const active = field !== undefined && sorting?.field === field
                const content = header.isPlaceholder
                  ? null
                  : flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )
                return (
                  <TableHead
                    key={header.id}
                    aria-sort={
                      active
                        ? sorting?.descending
                          ? "descending"
                          : "ascending"
                        : field
                          ? "none"
                          : undefined
                    }
                  >
                    {field && sorting ? (
                      <button
                        type="button"
                        onClick={() => sorting.onSort(field)}
                        className="hover:text-foreground focus-visible:ring-ring -mx-1 flex items-center gap-1 rounded px-1 outline-none focus-visible:ring-2"
                      >
                        {content}
                        {active ? (
                          sorting.descending ? (
                            <ArrowDown className="size-3.5" aria-hidden />
                          ) : (
                            <ArrowUp className="size-3.5" aria-hidden />
                          )
                        ) : (
                          <ChevronsUpDown
                            className="size-3.5 opacity-50"
                            aria-hidden
                          />
                        )}
                      </button>
                    ) : (
                      content
                    )}
                  </TableHead>
                )
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {pending ? (
            <PendingRows
              rows={pendingRows}
              columns={columnCount}
              key="pending"
            />
          ) : table.getRowModel().rows.length ? (
            table.getRowModel().rows.map((row) => {
              const id = selection?.idOf(row.original)
              const selected =
                id !== undefined && Boolean(selection?.ids.has(id))
              return (
                <TableRow
                  key={row.id}
                  data-state={selected ? "selected" : undefined}
                  className={
                    onRowClick
                      ? "focus-visible:ring-ring cursor-pointer outline-none focus-visible:ring-2"
                      : undefined
                  }
                  // A row that opens a record takes focus, answers Enter and
                  // Space, and says what it opens. It stays a row: giving it a
                  // button's role would take the table's structure away from
                  // every reader who relies on it.
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-label={rowLabel?.(row.original)}
                  onClick={
                    onRowClick
                      ? (event) => {
                          if (fromRowItself(event)) onRowClick(row.original)
                        }
                      : undefined
                  }
                  onKeyDown={
                    onRowClick
                      ? (event) => {
                          if (event.key !== "Enter" && event.key !== " ") return
                          if (event.target !== event.currentTarget) return
                          event.preventDefault()
                          onRowClick(row.original)
                        }
                      : undefined
                  }
                >
                  {selection && id !== undefined && (
                    <TableCell className="w-10">
                      <Checkbox
                        checked={selected}
                        aria-label={selection.label(row.original)}
                        onCheckedChange={(checked) =>
                          selection.onToggle(id, checked === true)
                        }
                      />
                    </TableCell>
                  )}
                  {row.getAllCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              )
            })
          ) : (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={columnCount} className="p-0">
                {empty ?? (
                  <p className="text-muted-foreground py-16 text-center">
                    No results found.
                  </p>
                )}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {scrollLabel && (
        // Said in words as well as drawn: on a phone the row is wider than
        // the screen, and a table that appears to end at the edge is the one
        // thing this must not be.
        <p className="text-muted-foreground flex items-center gap-1 text-xs md:hidden">
          <MoveHorizontal className="size-3.5" aria-hidden />
          Swipe sideways for the rest of each row
        </p>
      )}
    </>
  )
}

/**
 * The table's own loading state, with as many rows as are expected: a
 * skeleton that describes a different table makes the page jump when the real
 * one lands, which is the largest layout shift a list can produce.
 */
function PendingRows({ rows, columns }: { rows: number; columns: number }) {
  return Array.from({ length: rows }).map((_, rowIndex) => (
    <TableRow key={rowIndex} className="hover:bg-transparent">
      {Array.from({ length: columns }).map((_, cellIndex) => (
        <TableCell key={cellIndex}>
          <Skeleton className={cn("h-4", cellIndex === 0 ? "w-4" : "w-24")} />
        </TableCell>
      ))}
    </TableRow>
  ))
}
