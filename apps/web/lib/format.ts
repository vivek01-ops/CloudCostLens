/** Formatting helpers for money, percentages, dates, and numbers. */

const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

export function formatMoney(value: number | string, currency = "USD"): string {
  const numeric = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric);
}

export function formatCompactMoney(value: number | string, currency = "USD"): string {
  const numeric = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(numeric);
}

export function formatNumber(value: number | string): string {
  return numberFormatter.format(typeof value === "string" ? Number(value) : value);
}

export function formatPercent(value: number | string | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  const numeric = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(numeric)) return "—";
  return `${numeric.toFixed(digits)}%`;
}

export function formatDate(value: string | Date, opts?: Intl.DateTimeFormatOptions): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...opts,
  }).format(date);
}

export function formatDateTime(value: string | Date): string {
  return formatDate(value, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZoneName: "short",
  });
}

export function isoDate(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.toISOString().slice(0, 10);
}

export function daysAgoText(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  const diffMs = Date.now() - date.getTime();
  const hours = Math.floor(diffMs / 3_600_000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Distinguish "blocked/na" values from real zeros. */
export function valueOrEmDash(value: number | string | null | undefined): string | number {
  return value === null || value === undefined || Number.isNaN(Number(value))
    ? "—"
    : value;
}