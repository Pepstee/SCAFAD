import { ReactNode } from "react";
import { clsx } from "@/lib/format";

export interface ColumnDef<T> {
  key: string;
  header: ReactNode;
  align?: "left" | "right" | "center";
  width?: string;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  rows: T[];
  columns: ColumnDef<T>[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyState?: ReactNode;
  className?: string;
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  onRowClick,
  emptyState,
  className,
}: DataTableProps<T>) {
  if (rows.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-surface-muted">
        {emptyState ?? "No rows to display"}
      </div>
    );
  }
  return (
    <div className={clsx("w-full overflow-x-auto", className)}>
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-surface-border text-left text-[11px] uppercase tracking-wide text-surface-muted">
            {columns.map((col) => (
              <th
                key={col.key}
                className={clsx(
                  "px-3 py-2 font-medium",
                  col.align === "right" && "text-right",
                  col.align === "center" && "text-center"
                )}
                style={col.width ? { width: col.width } : undefined}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={clsx(
                "border-b border-surface-border/60 transition-colors",
                onRowClick && "cursor-pointer hover:bg-surface-subtle"
              )}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={clsx(
                    "px-3 py-2 text-ink",
                    col.align === "right" && "text-right",
                    col.align === "center" && "text-center"
                  )}
                >
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
