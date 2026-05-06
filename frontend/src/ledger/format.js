// Number/string formatters for Ledger tables and stat strip.

const USD0 = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumFractionDigits: 0,
});
const USD2 = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumFractionDigits: 2,
});
const NUM2 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const NUM4 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 });
const PCT  = new Intl.NumberFormat("en-US", {
  style: "percent", maximumFractionDigits: 1,
});

export function fmtUsd(n, decimals = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return decimals === 0 ? USD0.format(n) : USD2.format(n);
}

export function fmtUsdSigned(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return `${sign}${USD2.format(Math.abs(n))}`;
}

export function fmtPrice(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(0)}¢`;
}

export function fmtShares(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (Math.abs(n) >= 1000) return NUM2.format(n);
  return NUM4.format(n);
}

export function fmtPct(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return PCT.format(n);
}

export function fmtAddrShort(addr) {
  if (!addr) return "";
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

export function pnlClass(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "";
  if (n > 0) return "op-num--up";
  if (n < 0) return "op-num--down";
  return "";
}
