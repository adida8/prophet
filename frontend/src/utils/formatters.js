/** Convert decimal price (0-1) to display cents string: 0.61 → "61¢" */
export function toCents(price) {
  if (price == null || isNaN(price)) return '—';
  return `${Math.round(price * 100)}¢`;
}

/** Format USD volume: 1234567 → "$1.2M" */
export function fmtVolume(usd) {
  if (!usd || isNaN(usd)) return '$0';
  if (usd >= 1e9) return `$${(usd / 1e9).toFixed(1)}B`;
  if (usd >= 1e6) return `$${(usd / 1e6).toFixed(1)}M`;
  if (usd >= 1e3) return `$${(usd / 1e3).toFixed(0)}K`;
  return `$${Math.round(usd)}`;
}

/** Signed cents change: 0.04 → "+4¢", -0.05 → "−5¢" */
export function fmtChange(delta) {
  if (delta == null || isNaN(delta)) return '';
  const c = Math.round(delta * 100);
  return c >= 0 ? `+${c}¢` : `−${Math.abs(c)}¢`;
}

/** Pct change: 12.5 → "+12.5%", -3.2 → "−3.2%" */
export function fmtPct(pct) {
  if (pct == null || isNaN(pct)) return '';
  return pct >= 0 ? `+${pct.toFixed(1)}%` : `−${Math.abs(pct).toFixed(1)}%`;
}

/** Short date: "2026-06-30T00:00:00Z" → "Jun 30" */
export function fmtDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

/** Platform display name */
export const PLATFORM_LABELS = {
  kalshi:     'Kalshi',
  polymarket: 'Polymarket',
  draftkings: 'DraftKings',
  fanduel:    'FanDuel',
};

export function platformLabel(key) {
  return PLATFORM_LABELS[key] ?? key;
}

/** Build affiliate URL from platform URL */
export function affiliateUrl(url, platform) {
  if (!url) return '#';
  const utm = '?utm_source=predictionedge&utm_medium=referral&utm_campaign=odds';
  return url.includes('?') ? url + '&utm_source=predictionedge' : url + utm;
}

const MAX_VOL_FOR_BAR = 10_000_000;
export function volBarWidth(volume) {
  return Math.min(100, (volume / MAX_VOL_FOR_BAR) * 100);
}
