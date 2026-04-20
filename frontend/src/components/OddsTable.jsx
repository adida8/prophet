import { useState } from 'react';
import { toCents, fmtVolume, fmtDate, affiliateUrl, volBarWidth } from '../utils/formatters';

const CATEGORIES = ['All', 'Sports', 'Politics', 'Crypto', 'Economy', 'Culture'];
const PLATFORMS  = ['kalshi', 'polymarket', 'draftkings', 'fanduel'];
const PLAT_LABELS = { kalshi: 'Kalshi', polymarket: 'Polymarket', draftkings: 'DraftKings', fanduel: 'FanDuel' };

export default function OddsTable({ compared = [], loading }) {
  const [activeTab, setActiveTab] = useState('All');

  const filtered = activeTab === 'All'
    ? compared
    : compared.filter((c) => c.category?.toLowerCase() === activeTab.toLowerCase());

  return (
    <div>
      {/* Section header */}
      <div style={styles.sectionHeader}>
        <div style={styles.sectionTitle}>
          Cross-Platform Odds Comparison
          <span style={styles.badge}>LIVE</span>
        </div>
        <div style={styles.tabs}>
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              style={{ ...styles.tab, ...(activeTab === cat ? styles.tabActive : {}) }}
              onClick={() => setActiveTab(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div style={styles.tableWrap}>
        {loading ? (
          <div style={styles.empty}>Fetching live market data…</div>
        ) : filtered.length === 0 ? (
          <div style={styles.empty}>No markets for this category yet.</div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={{ ...styles.th, width: '30%', textAlign: 'left' }}>Market</th>
                {PLATFORMS.map((p) => <th key={p} style={styles.th}>{PLAT_LABELS[p]}</th>)}
                <th style={styles.th}>Edge</th>
                <th style={styles.th}>24h Vol</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 50).map((cm) => (
                <OddsRow key={cm.id} market={cm} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function OddsRow({ market }) {
  const { platforms, best_yes_platform, title, category, resolution_date, price_gap, arb_edge_pct, total_volume_24h } = market;

  return (
    <tr style={styles.row} className="odds-row">
      <td style={styles.tdName}>
        <div style={styles.marketName}>{title}</div>
        <div style={styles.marketMeta}>
          {resolution_date ? `Resolves: ${fmtDate(resolution_date)}` : ''}
          {category ? ` · ${cap(category)}` : ''}
        </div>
      </td>

      {PLATFORMS.map((p) => {
        const pp = platforms?.[p];
        const isBest = p === best_yes_platform && pp;
        return (
          <td key={p} style={styles.tdCenter}>
            {pp ? (
              <a
                href={affiliateUrl(pp.url, p)}
                target="_blank"
                rel="noopener noreferrer"
                style={{ textDecoration: 'none' }}
              >
                <span style={isBest ? styles.oddsBest : styles.oddsNormal}>
                  {toCents(pp.yes_price)}
                </span>
              </a>
            ) : (
              <span style={styles.oddsEmpty}>—</span>
            )}
          </td>
        );
      })}

      <td style={styles.tdCenter}>
        {price_gap > 0.005 ? (
          <span style={arb_edge_pct > 0 ? styles.arbBadgeGreen : styles.arbBadge}>
            {Math.round(price_gap * 100)}¢ GAP
          </span>
        ) : null}
      </td>

      <td style={styles.tdCenter}>
        <div style={styles.volWrap}>
          <div style={styles.volBg}>
            <div style={{ ...styles.volFill, width: `${volBarWidth(total_volume_24h)}%` }} />
          </div>
          <span style={styles.volText}>{fmtVolume(total_volume_24h)}</span>
        </div>
      </td>
    </tr>
  );
}

function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''; }

const styles = {
  sectionHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' },
  sectionTitle:  { fontSize: '14px', fontWeight: 700, letterSpacing: '-0.3px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' },
  badge:         { fontFamily: 'var(--font-mono)', fontSize: '10px', background: 'var(--accent-blue-dim)', color: 'var(--accent-blue)', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 },
  tabs:          { display: 'flex', gap: '2px' },
  tab:           { background: 'none', border: '1px solid transparent', color: 'var(--text-muted)', fontFamily: 'var(--font-sans)', fontSize: '12px', padding: '4px 12px', borderRadius: '5px', cursor: 'pointer', transition: 'all 0.15s' },
  tabActive:     { background: 'var(--bg-card)', color: 'var(--text-primary)', borderColor: 'var(--border)' },

  tableWrap: { background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', marginBottom: '20px' },
  empty:     { padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '13px' },
  table:     { width: '100%', borderCollapse: 'collapse' },

  th: {
    fontSize: '10px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '0.8px', padding: '12px 16px', textAlign: 'center',
    borderBottom: '1px solid var(--border)', background: 'rgba(0,0,0,0.2)',
    fontFamily: 'var(--font-sans)',
  },
  row:     { borderBottom: '1px solid rgba(30,41,59,0.5)', transition: 'background 0.15s', cursor: 'default' },
  tdName:  { padding: '12px 16px' },
  tdCenter: { padding: '12px 16px', textAlign: 'center' },

  marketName: { fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px', fontSize: '13px', fontFamily: 'var(--font-sans)' },
  marketMeta: { fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' },

  oddsBest: {
    fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '14px',
    padding: '4px 10px', borderRadius: '5px', display: 'inline-block', minWidth: '52px',
    background: 'var(--accent-green-dim)', color: 'var(--accent-green)',
    border: '1px solid rgba(34,197,94,0.3)',
  },
  oddsNormal: {
    fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '14px',
    padding: '4px 10px', borderRadius: '5px', display: 'inline-block', minWidth: '52px',
    background: 'rgba(255,255,255,0.04)', color: 'var(--text-secondary)',
    border: '1px solid transparent',
  },
  oddsEmpty: {
    fontFamily: 'var(--font-mono)', fontSize: '14px', color: 'var(--text-muted)', padding: '4px 10px',
  },

  arbBadge: {
    fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700,
    background: 'var(--accent-amber-dim)', color: 'var(--accent-amber)',
    padding: '2px 6px', borderRadius: '3px', letterSpacing: '0.5px',
  },
  arbBadgeGreen: {
    fontFamily: 'var(--font-mono)', fontSize: '10px', fontWeight: 700,
    background: 'var(--accent-green-dim)', color: 'var(--accent-green)',
    padding: '2px 6px', borderRadius: '3px', letterSpacing: '0.5px',
  },

  volWrap: { display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center' },
  volBg:   { width: '60px', height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', overflow: 'hidden' },
  volFill: { height: '100%', borderRadius: '2px', background: 'var(--accent-cyan)' },
  volText: { fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' },
};
