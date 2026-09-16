import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { EmptyState } from "./EmptyState";
import { Mono } from "./Mono";
import styles from "./Table.module.css";

export interface Column<Row> {
  key: string;
  header: ReactNode;
  render: (row: Row) => ReactNode;
  /** Column width hint; tables scroll horizontally in their own container. */
  width?: string | undefined;
  align?: "left" | "right" | undefined;
  mono?: boolean | undefined;
  /** Hide on phones so the row still fits without scrolling. */
  optional?: boolean | undefined;
}

export interface TableProps<Row> {
  columns: ReadonlyArray<Column<Row>>;
  rows: ReadonlyArray<Row>;
  rowKey: (row: Row) => string | number;
  onRowClick?: ((row: Row) => void) | undefined;
  empty?: ReactNode | undefined;
  className?: string | undefined;
}

export function Table<Row>({ columns, rows, rowKey, onRowClick, empty, className }: TableProps<Row>) {
  if (rows.length === 0) {
    return <>{empty ?? <EmptyState title="Nothing here yet." />}</>;
  }
  return (
    <div className={cx(styles["wrap"], className)}>
      <table className={styles["table"]}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} style={{ width: column.width }} className={cx(column.align === "right" && styles["right"], column.optional && styles["optional"])}>
                <Mono upper>{column.header}</Mono>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className={cx(onRowClick && styles["interactive"])} onClick={onRowClick ? () => onRowClick(row) : undefined}>
              {columns.map((column) => (
                <td key={column.key} className={cx(column.align === "right" && styles["right"], column.mono && styles["mono"], column.optional && styles["optional"])}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
