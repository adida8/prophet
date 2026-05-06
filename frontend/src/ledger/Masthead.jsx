// Page masthead — Odds Primer wordmark + sub-product label "Ledger".
// Treats "Ledger" the way wc-edition-brief.md treats the issue: a quiet
// edition strip beside the wordmark, not a sub-brand.

import { Wordmark } from "./Wordmark";

export default function Masthead({ refreshedAt, onRefresh, refreshing }) {
  return (
    <header className="op-masthead">
      <div className="op-masthead__row">
        <div className="op-masthead__left">
          <Wordmark glyphHeight={42} fontSize={18} fontWeight={700} />
          <span className="op-masthead__divider" aria-hidden="true" />
          <span className="op-masthead__edition">Ledger · Vol. 1 · Polymarket</span>
        </div>
        <div className="op-masthead__right">
          {refreshedAt ? (
            <button
              type="button"
              className="op-masthead__refresh"
              onClick={onRefresh}
              disabled={refreshing}
            >
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
          ) : null}
          {refreshedAt ? (
            <span className="op-masthead__live">
              Last refreshed · <RelTime iso={refreshedAt} />
            </span>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function RelTime({ iso }) {
  if (!iso) return "—";
  const t = new Date(iso);
  const diff = (Date.now() - t.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return t.toISOString().slice(0, 10);
}
