"use client";

import { useMemo, useState, type ReactNode } from "react";
import { Download, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { downloadCsv, toCsv } from "@/lib/csv";

export interface Column<T> {
  key: string;
  header: string;
  align?: "left" | "right";
  render: (row: T) => ReactNode;
  /** Optional plain-text value used for search and CSV export. */
  value?: (row: T) => string | number;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowId: (row: T) => string;
  searchable?: boolean;
  searchPlaceholder?: string;
  exportName?: string;
  pageSize?: number;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  searchable = true,
  searchPlaceholder = "Search…",
  exportName,
  pageSize = 10,
  onRowClick,
}: DataTableProps<T>) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!query.trim()) return rows;
    const q = query.toLowerCase();
    return rows.filter((row) =>
      columns.some((col) => {
        const raw = col.value ? col.value(row) : "";
        return String(raw).toLowerCase().includes(q);
      }),
    );
  }, [rows, query, columns]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize);

  const handleExport = () => {
    const exportRows = filtered.map((row) => {
      const record: Record<string, string | number> = {};
      for (const col of columns) {
        record[col.header] = col.value ? col.value(row) : "";
      }
      return record;
    });
    downloadCsv(`${exportName ?? "export"}.csv`, toCsv(exportRows));
  };

  return (
    <div className="rounded-lg border border-border bg-surface">
      {searchable || exportName ? (
        <div className="flex items-center gap-2 border-b border-border px-3 py-2">
          {searchable ? (
            <div className="relative max-w-xs flex-1">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-secondary" />
              <Input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(0);
                }}
                placeholder={searchPlaceholder}
                className="pl-7"
                aria-label="Search table"
              />
            </div>
          ) : null}
          <span className="text-xs text-secondary">{filtered.length} rows</span>
          {exportName ? (
            <Button variant="secondary" size="sm" className="ml-auto" onClick={handleExport}>
              <Download className="h-3.5 w-3.5" />
              Export CSV
            </Button>
          ) : null}
        </div>
      ) : null}

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {columns.map((col) => (
              <TableHead key={col.key} className={col.align === "right" ? "text-right" : undefined}>
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {pageRows.map((row) => (
            <TableRow
              key={getRowId(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={onRowClick ? "cursor-pointer" : undefined}
            >
              {columns.map((col) => (
                <TableCell
                  key={col.key}
                  className={col.align === "right" ? "text-right tabular" : undefined}
                >
                  {col.render(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
          {pageRows.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={columns.length} className="py-8 text-center text-sm text-secondary">
                No matching records.
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      {filtered.length > pageSize ? (
        <div className="flex items-center justify-between border-t border-border px-3 py-2 text-xs text-secondary">
          <span>
            Page {safePage + 1} of {pageCount}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={safePage === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={safePage >= pageCount - 1}
              onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}