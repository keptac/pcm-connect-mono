import { useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

function joinClasses(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

const TABLE_PAGE_SIZE_OPTIONS = [10, 25, 50];

export type PaginationResult<T> = {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
  startIndex: number;
  endIndex: number;
  pageItems: T[];
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
};

export function usePagination<T>(items: T[] | undefined, initialPageSize = TABLE_PAGE_SIZE_OPTIONS[0]): PaginationResult<T> {
  const source = items || [];
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);

  useEffect(() => {
    setPage(1);
  }, [items]);

  const totalItems = source.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  const pageItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return source.slice(start, start + pageSize);
  }, [page, pageSize, source]);

  const startIndex = totalItems === 0 ? 0 : ((page - 1) * pageSize) + 1;
  const endIndex = totalItems === 0 ? 0 : Math.min(page * pageSize, totalItems);

  function setPageSize(nextPageSize: number) {
    setPageSizeState(nextPageSize);
    setPage(1);
  }

  return {
    page,
    pageSize,
    totalItems,
    totalPages,
    startIndex,
    endIndex,
    pageItems,
    setPage,
    setPageSize
  };
}

export function PageHeader({
  eyebrow,
  title,
  actions
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="display-title">{title}</h1>
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
    </div>
  );
}

export function Panel({
  className,
  children
}: {
  className?: string;
  children: ReactNode;
}) {
  return <section className={joinClasses("panel", className)}>{children}</section>;
}

export function MetricCard({
  label,
  value,
  tone = "forest"
}: {
  label: string;
  value: ReactNode;
  tone?: "forest" | "gold" | "ink" | "coral";
  helper?: ReactNode;
}) {
  return (
    <div className={joinClasses("metric-card", `metric-${tone}`)}>
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
    </div>
  );
}

export function StatusBadge({
  label,
  tone = "neutral"
}: {
  label: string;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
}) {
  return <span className={joinClasses("status-badge", `status-${tone}`)}>{label}</span>;
}

function EditIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3.75 13.75V16.25H6.25L14.5 8L12 5.5L3.75 13.75Z" />
      <path d="M10.75 6.75L13.25 9.25" />
      <path d="M11.25 4.25L13 2.5C13.6904 1.80964 14.8096 1.80964 15.5 2.5L17.5 4.5C18.1904 5.19036 18.1904 6.30964 17.5 7L15.75 8.75" />
    </svg>
  );
}

function DeleteIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4.5 5.5H15.5" />
      <path d="M7.5 5.5V4.5C7.5 3.94772 7.94772 3.5 8.5 3.5H11.5C12.0523 3.5 12.5 3.94772 12.5 4.5V5.5" />
      <path d="M6.5 5.5V14.5C6.5 15.6046 7.39543 16.5 8.5 16.5H11.5C12.6046 16.5 13.5 15.6046 13.5 14.5V5.5" />
      <path d="M8.5 8.25V13" />
      <path d="M11.5 8.25V13" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 3.75V11.5" />
      <path d="M7 8.75L10 11.75L13 8.75" />
      <path d="M4.5 14.25V15.25C4.5 15.8023 4.94772 16.25 5.5 16.25H14.5C15.0523 16.25 15.5 15.8023 15.5 15.25V14.25" />
    </svg>
  );
}

export function TableActionButton({
  label,
  tone,
  onClick,
  disabled = false
}: {
  label: string;
  tone: "edit" | "delete" | "download";
  onClick: () => void | Promise<void>;
  disabled?: boolean;
}) {
  const Icon = tone === "delete" ? DeleteIcon : tone === "download" ? DownloadIcon : EditIcon;
  return (
    <button
      className={joinClasses(
        "table-icon-button",
        tone === "delete" ? "table-icon-button-delete" : tone === "download" ? "table-icon-button-download" : "table-icon-button-edit"
      )}
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
    >
      <Icon />
    </button>
  );
}

export function EmptyState({
  title
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="rounded-[12px] border border-dashed border-slate-300/80 bg-white/60 px-6 py-10 text-center">
      <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
    </div>
  );
}

export function ModalDialog({
  open,
  onClose,
  className,
  children
}: {
  open: boolean;
  onClose: () => void;
  className?: string;
  children: ReactNode;
}) {
  if (!open) return null;
  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className={joinClasses("modal-shell", className)} onClick={(event) => event.stopPropagation()}>
        {children}
      </div>
    </div>,
    document.body
  );
}

export function TablePagination({
  pagination,
  itemLabel = "records",
  onExport,
  exportLabel = "Export CSV"
}: {
  pagination: PaginationResult<unknown>;
  itemLabel?: string;
  onExport?: () => void;
  exportLabel?: string;
}) {
  return (
    <div className="table-pagination">
      <p className="table-pagination-summary">
        Showing {pagination.startIndex}-{pagination.endIndex} of {pagination.totalItems} {itemLabel}
      </p>

      <div className="table-pagination-controls">
        <div className="table-pagination-tools">
          {onExport ? (
            <button
              className="secondary-button table-pagination-button"
              disabled={pagination.totalItems === 0}
              onClick={onExport}
              type="button"
            >
              {exportLabel}
            </button>
          ) : null}
          <label className="table-pagination-size">
            <span>Rows</span>
            <select
              className="field-input table-pagination-select"
              value={pagination.pageSize}
              onChange={(event) => pagination.setPageSize(Number(event.target.value))}
            >
              {TABLE_PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="table-pagination-buttons">
          <button
            className="secondary-button table-pagination-button"
            disabled={pagination.page <= 1}
            onClick={() => pagination.setPage(pagination.page - 1)}
            type="button"
          >
            Previous
          </button>
          <span className="table-pagination-page">Page {pagination.page} of {pagination.totalPages}</span>
          <button
            className="secondary-button table-pagination-button"
            disabled={pagination.page >= pagination.totalPages}
            onClick={() => pagination.setPage(pagination.page + 1)}
            type="button"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
