/**
 * Display formatting. Indian conventions throughout: lakh/crore, ₹, en-IN grouping.
 * Pure functions, no I/O.
 */

const INR = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});
const COMPACT = new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 });
const PLAIN = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

const MINUS = "−";

/** ₹3,00,000 */
export function formatINR(value: number): string {
  return INR.format(value);
}

/** ₹17.2L · ₹1.2Cr · ₹85K — for axes, tiles and tables with limited room. */
export function formatCompactINR(value: number): string {
  return `${value < 0 ? MINUS : ""}₹${COMPACT.format(Math.abs(value))}`;
}

/** +₹1.2L · −₹3.4L. Zero is shown without a sign. */
export function formatSignedCompactINR(value: number): string {
  if (Math.round(value) === 0) return "₹0";
  return `${value > 0 ? "+" : MINUS}₹${COMPACT.format(Math.abs(value))}`;
}

/** Fraction to percent: 0.315 -> "32%". */
export function formatPct(fraction: number, digits = 0): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

export function formatSignedPct(fraction: number, digits = 0): string {
  const text = `${Math.abs(fraction * 100).toFixed(digits)}%`;
  if (Number(text.slice(0, -1)) === 0) return text;
  return `${fraction > 0 ? "+" : MINUS}${text}`;
}

export function formatNumber(value: number): string {
  return PLAIN.format(value);
}

/** 60 -> "5 yr", 18 -> "1 yr 6 mo", 6 -> "6 mo". */
export function formatMonths(months: number): string {
  const years = Math.floor(months / 12);
  const rest = months % 12;
  if (years === 0) return `${rest} mo`;
  return rest === 0 ? `${years} yr` : `${years} yr ${rest} mo`;
}

/** "real_estate" -> "Real estate". */
export function humanize(key: string): string {
  const text = key.replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** 1.4 s for a latency in milliseconds. */
export function formatLatency(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}
