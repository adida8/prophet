// Header strip — total value, realized, unrealized, win rate, position count.
// Editorial card grid. Numbers are tabular; P&L uses chart green/red at low
// saturation per design system rules.

import { fmtUsd, fmtUsdSigned, fmtPct, pnlClass } from "./format";

export default function StatStrip({ totals, walletAddress }) {
  if (!totals) return null;
  return (
    <section className="op-stats" aria-label="portfolio summary">
      <Stat
        eyebrow="Total value"
        value={fmtUsd(totals.total_value_usd, 0)}
        meta={walletAddress}
      />
      <Stat
        eyebrow="Unrealized P&amp;L"
        value={fmtUsdSigned(totals.unrealized_pnl_usd)}
        valueClass={pnlClass(totals.unrealized_pnl_usd)}
        meta="open positions"
      />
      <Stat
        eyebrow="Realized P&amp;L"
        value={fmtUsdSigned(totals.realized_pnl_usd)}
        valueClass={pnlClass(totals.realized_pnl_usd)}
        meta="closed positions"
      />
      <Stat
        eyebrow="Win rate"
        value={totals.win_rate === null ? "—" : fmtPct(totals.win_rate)}
        meta={
          totals.closed_position_count
            ? `${totals.closed_position_count} closed`
            : "no closed positions yet"
        }
      />
      <Stat
        eyebrow="Positions"
        value={String(totals.open_position_count)}
        meta={
          totals.closed_position_count
            ? `${totals.closed_position_count} closed`
            : "all open"
        }
      />
    </section>
  );
}

function Stat({ eyebrow, value, valueClass = "", meta }) {
  return (
    <div className="op-stat">
      <p className="op-eyebrow">{eyebrow}</p>
      <p className={`op-num op-stat__value ${valueClass}`}>{value}</p>
      {meta ? <p className="op-stat__meta">{meta}</p> : null}
    </div>
  );
}
