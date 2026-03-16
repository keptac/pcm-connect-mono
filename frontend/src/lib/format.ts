const COMPACT_THRESHOLD = 1_000_000;

function shouldUseCompactNotation(value?: number | null) {
  return Math.abs(Number(value ?? 0)) >= COMPACT_THRESHOLD;
}

export function formatCurrency(amount?: number | null, currency = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    notation: shouldUseCompactNotation(amount) ? "compact" : "standard",
    maximumFractionDigits: shouldUseCompactNotation(amount) ? 1 : 0
  }).format(amount ?? 0);
}

export function formatCompactCurrency(amount?: number | null, currency = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: 1
  }).format(amount ?? 0);
}

export function formatNumber(value?: number | null) {
  return new Intl.NumberFormat("en-US", {
    notation: shouldUseCompactNotation(value) ? "compact" : "standard",
    maximumFractionDigits: shouldUseCompactNotation(value) ? 1 : 0
  }).format(value ?? 0);
}

export function formatCompactNumber(value?: number | null) {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1
  }).format(value ?? 0);
}

export function formatDate(value?: string | null) {
  if (!value) return "No date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(date);
}

export function formatDateTime(value?: string | null) {
  if (!value) return "No time";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(date);
}
