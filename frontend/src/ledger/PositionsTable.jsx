// Open / closed positions table. Hairline rules, tabular numbers,
// flame underline reserved for "biggest disagreement"-class accents.
// Closed table is collapsed by default per the brief.

import { useState } from "react";

import {
  fmtPrice,
  fmtShares,
  fmtUsd,
  fmtUsdSigned,
  pnlClass,
} from "./format";

const POLYMARKET_EVENT_BASE = "https://polymarket.com/event/";

export default function PositionsTable({ title, eyebrow, positions, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  const empty = !positions || positions.length === 0;
  return (
    <section className="op-table-block">
      <header className="op-table-block__head">
        <div>
          <p className="op-eyebrow">{eyebrow}</p>
          <h2 className="op-h2 op-table-block__title">{title}</h2>
        </div>
        <button
          type="button"
          className="op-toggle"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          {open ? "Collapse" : `Expand · ${positions?.length ?? 0}`}
        </button>
      </header>

      {open ? (
        empty ? (
          <p className="op-empty-row">— no positions in this section.</p>
        ) : (
          <div className="op-table-wrap">
            <table className="op-table">
              <thead>
                <tr>
                  <th className="op-th op-th--market">Market</th>
                  <th className="op-th op-th--num">Shares</th>
                  <th className="op-th op-th--num">Avg entry</th>
                  <th className="op-th op-th--num">Current</th>
                  <th className="op-th op-th--num">Value</th>
                  <th className="op-th op-th--num">P&amp;L</th>
                  <th className="op-th op-th--source">Source</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <Row key={p.asset || p.condition_id} p={p} />
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : null}
    </section>
  );
}

function Row({ p }) {
  const closed = !!p.closed_at;
  const pnl = closed ? p.realized_pnl_usd : p.unrealized_pnl_usd;
  const sourceUrl = p.event_slug ? `${POLYMARKET_EVENT_BASE}${p.event_slug}` : null;
  return (
    <tr className="op-tr">
      <td className="op-td op-td--market">
        <div className="op-market">
          <span className="op-venue-dot" aria-hidden="true" />
          <div>
            <p className="op-market__q">{p.market_question || "—"}</p>
            <p className="op-market__meta">
              {p.outcome ? <span className="op-tag">{p.outcome}</span> : null}
              {p.end_date ? <span className="op-meta">Ends {p.end_date}</span> : null}
            </p>
          </div>
        </div>
      </td>
      <td className="op-td op-num">{fmtShares(p.shares)}</td>
      <td className="op-td op-num">{fmtPrice(p.avg_entry_price)}</td>
      <td className="op-td op-num">{fmtPrice(p.current_price)}</td>
      <td className="op-td op-num">{fmtUsd(p.value_usd)}</td>
      <td className={`op-td op-num ${pnlClass(pnl)}`}>{fmtUsdSigned(pnl)}</td>
      <td className="op-td op-td--source">
        {sourceUrl ? (
          <a href={sourceUrl} target="_blank" rel="noreferrer" className="op-source">
            View source on Polymarket ↗
          </a>
        ) : (
          <span className="op-meta">—</span>
        )}
      </td>
    </tr>
  );
}
