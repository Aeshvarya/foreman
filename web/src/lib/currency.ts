// Display currency for every money figure in the product.
//
// The engine computes in INR — that is the currency the project contracts are
// written in. What a *reader* wants is a different question, and the answer
// depends who is looking at the screen. So currency is a presentation choice,
// stored on the client, sent to the API as a header, and applied by the
// formatting layer alone. No number is ever recomputed.
//
// Default is USD. Rate mirrors USD_INR in src/money.py — change both together.

export type Currency = "USD" | "INR";

export const USD_INR = 95.75;
export const RATE_DATE = "21 Aug 2026";
export const RATE_NOTE = `Converted at ₹${USD_INR} = $1, fixed ${RATE_DATE}.`;

const KEY = "foreman.currency";

export function currency(): Currency {
  try {
    return localStorage.getItem(KEY) === "INR" ? "INR" : "USD";
  } catch {
    return "USD";                       // private mode / storage blocked
  }
}

/** Switch currency and re-render everything.
 *
 * A full reload rather than a refetch, deliberately: money labels are built
 * server-side and arrive inside a dozen different payloads. Refetching some of
 * them would leave one panel in dollars and its neighbour in rupees, which on
 * a projector reads as a bug. A reload cannot produce a mixed screen. */
export function setCurrency(next: Currency): void {
  try { localStorage.setItem(KEY, next); } catch { /* nothing we can do */ }
  window.location.reload();
}

/** Format an INR amount for display. Mirrors fmt_money() in src/money.py, for
 *  the few values the API hands over as raw numbers instead of labels. */
export function fmtShort(inr: number): string {
  return currency() === "USD" ? fmtUsd(inr) : fmtInr(inr);
}

function fmtUsd(inr: number): string {
  const d = inr / USD_INR;
  const sign = d < 0 ? "-" : "", a = Math.abs(d);
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(2).replace(/\.00$/, "")}M`;
  if (a >= 1e4) return `${sign}$${(a / 1e3).toFixed(1).replace(/\.0$/, "")}K`;
  return `${sign}$${Math.round(a).toLocaleString("en-US")}`;
}

function fmtInr(n: number): string {
  const a = Math.abs(n), sign = n < 0 ? "-" : "";
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(2).replace(/\.00$/, "")} crore`;
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(2).replace(/\.00$/, "")} lakh`;
  return `${sign}₹${Math.round(a).toLocaleString("en-IN")}`;
}

/** The symbol to prefix a money INPUT with. Inputs are always in the currency
 *  on screen; the API stores INR, so the caller converts on save. */
export function symbol(): string {
  return currency() === "USD" ? "$" : "₹";
}

/** UI value -> INR for the API. */
export function toInr(shown: number): number {
  return currency() === "USD" ? Math.round(shown * USD_INR) : shown;
}

/** INR from the API -> UI value. */
export function fromInr(inr: number): number {
  return currency() === "USD" ? Math.round(inr / USD_INR) : inr;
}
