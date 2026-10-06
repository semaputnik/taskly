import {
  type ColumnDef,
  flexRender,
  type RowData,
  tableFeatures,
  useTable,
} from "@tanstack/react-table"

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
}

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

export function DataTable<TData extends RowData>({
  columns,
  data,
  empty,
}: DataTableProps<TData>) {
  const table = useTable({ features, data, columns })
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
              <TableRow key={row.id}>
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
