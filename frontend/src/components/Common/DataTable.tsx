import {
  type ColumnDef,
  flexRender,
  type RowData,
  tableFeatures,
  useTable,
} from "@tanstack/react-table"

import { type RecordKind, useRecordPanels } from "@/components/Records/panels"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

// v9's core row model is implicit. Paging is the server's: a table that pages
// an array it was handed can only ever page what it was handed, and would
// report that window as the total.
const features = tableFeatures({})

export type DataTableFeatures = typeof features

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
   * The kind of record a row opens. The row whose record is open in the
   * column is tinted, as a line on the day page is.
   */
  opens?: RecordKind
  /**
   * What opening a row does, in words. A row that acts is a control, and a
   * control without a name is unusable to anyone not looking at the screen.
   */
  rowLabel?: (row: TData) => string
}

/**
 * A row can hold checkboxes, menus and links, and clicking one of those means
 * that control — not "open the row". Asking the event where it landed keeps
 * the rule in one place, rather than making every cell remember to stop
 * propagation.
 */
const INTERACTIVE = "button, a, input, select, textarea"

/**
 * A cell's content, called rather than mounted when it is a plain function.
 *
 * `flexRender` mounts a function as a component, and the column definitions
 * are rebuilt on every render of the table, so each render would hand React a
 * new component type and remount every cell — dropping whatever a control in
 * it was holding, like an open prompt or an announcement.
 */
function renderCell<TProps extends object>(
  cell: unknown,
  context: TProps,
): React.ReactNode {
  return typeof cell === "function"
    ? (cell as (props: TProps) => React.ReactNode)(context)
    : flexRender(cell as never, context)
}

function fromRowItself(event: React.MouseEvent<HTMLElement>): boolean {
  const target = event.target as HTMLElement | null
  return !target?.closest(INTERACTIVE)
}

export function DataTable<TData extends RowData>({
  columns,
  data,
  empty,
  onRowClick,
  opens,
  rowLabel,
}: DataTableProps<TData>) {
  const table = useTable({ features, data, columns })
  const { idOf } = useRecordPanels()
  const openId = opens ? idOf(opens) : null
  const columnCount = columns.length

  return (
    <Table>
      <TableHeader>
        {table.getHeaderGroups().map((headerGroup) => (
          <TableRow key={headerGroup.id} className="hover:bg-transparent">
            {headerGroup.headers.map((header) => (
              <TableHead key={header.id}>
                {header.isPlaceholder
                  ? null
                  : flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
              </TableHead>
            ))}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.length ? (
          table.getRowModel().rows.map((row) => {
            return (
              <TableRow
                key={row.id}
                data-open={
                  openId !== null &&
                  (row.original as { id?: string }).id === openId
                    ? ""
                    : undefined
                }
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
                {row.getAllCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {renderCell(cell.column.columnDef.cell, cell.getContext())}
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
  )
}
