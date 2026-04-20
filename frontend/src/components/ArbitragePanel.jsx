import { PLATFORM_LABELS, toCents } from '../utils/formatters';

export default function ArbitragePanel({ opportunities = [] }) {
  const display = opportunities.length > 0 ? opportunities : DEMO_OPPS;
  const count   = opportunities.length;

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <span style={styles.title}>Arbitrage Alerts</span>
        <span style={styles.badge}>
          {count > 0 ? `${count} LIVE` : 'SCANNING'}
        </span>
      </div>

      {display.slice(0, 7).map((opp, i) => (
        <div key={i} style={styles.row}>
          <div>
            <div style={styles.name}>{opp.market_title}</div>
            <div style={styles.meta}>
              Buy {PLATFORM_LABELS[opp.buy_yes_platform] ?? opp.buy_yes_platform} {toCents(opp.buy_yes_price)}
              {' → '}
              Buy NO {PLATFORM_LABELS[opp.buy_no_platform] ?? opp.buy_no_platform} {toCents(opp.buy_no_price)}
            </div>
          </div>
          <div style={styles.edge}>{opp.edge_pct?.toFixed(1)}% edge</div>
        </div>
      ))}

      {display.length === 0 && (
        <div style={styles.empty}>No opportunities above 1.5% threshold</div>
      )}
    </div>
  );
}

const DEMO_OPPS = [
  { market_title: 'Celtics NBA Champs — YES',   buy_yes_platform: 'kalshi',     buy_yes_price: 0.28, buy_no_platform: 'polymarket', buy_no_price: 0.74, edge_pct: 2.8 },
  { market_title: 'Iran Ceasefire Jun — YES',   buy_yes_platform: 'kalshi',     buy_yes_price: 0.29, buy_no_platform: 'polymarket', buy_no_price: 0.67, edge_pct: 4.1 },
  { market_title: 'GTA VI Dec 2026 — YES',      buy_yes_platform: 'polymarket', buy_yes_price: 0.51, buy_no_platform: 'kalshi',     buy_no_price: 0.45, edge_pct: 3.6 },
  { market_title: 'BTC >$100K Jun — YES',       buy_yes_platform: 'kalshi',     buy_yes_price: 0.61, buy_no_platform: 'polymarket', buy_no_price: 0.36, edge_pct: 2.3 },
  { market_title: 'Fed Cut Jul — YES',           buy_yes_platform: 'kalshi',     buy_yes_price: 0.34, buy_no_platform: 'polymarket', buy_no_price: 0.63, edge_pct: 3.0 },
];

const styles = {
  card:  { background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px 20px' },
  header: { display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' },
  title: { fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' },
  badge: { fontFamily: 'var(--font-mono)', fontSize: '10px', background: 'var(--accent-amber-dim)', color: 'var(--accent-amber)', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 },
  row:   { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid rgba(30,41,59,0.4)' },
  name:  { fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', marginBottom: '2px' },
  meta:  { fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' },
  edge:  { fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 600, background: 'var(--accent-amber-dim)', color: 'var(--accent-amber)', padding: '2px 10px', borderRadius: '4px', whiteSpace: 'nowrap' },
  empty: { padding: '20px 0', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '12px' },
};
