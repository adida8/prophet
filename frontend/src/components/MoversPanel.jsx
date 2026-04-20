import { toCents, fmtChange, fmtPct } from '../utils/formatters';

export default function MoversPanel({ movers = [], window = '24H' }) {
  const display = movers.length > 0 ? movers : DEMO_MOVERS;

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <span style={styles.title}>Biggest Movers</span>
        <span style={styles.badge}>{window}</span>
      </div>

      {display.slice(0, 7).map((m, i) => {
        const up = (m.change_abs ?? 0) >= 0;
        return (
          <div key={i} style={styles.row}>
            <div style={styles.name}>{m.title || m.market_id}</div>
            <div style={styles.detail}>
              <span style={styles.price}>{toCents(m.current_price)}</span>
              <span style={{
                ...styles.change,
                color: up ? 'var(--accent-green)' : 'var(--accent-red)',
                background: up ? 'var(--accent-green-dim)' : 'var(--accent-red-dim)',
              }}>
                {up ? '▲' : '▼'} {fmtChange(m.change_abs)}
              </span>
            </div>
          </div>
        );
      })}

      {display.length === 0 && (
        <div style={styles.empty}>Accumulating price history…</div>
      )}
    </div>
  );
}

const DEMO_MOVERS = [
  { title: 'Iran Ceasefire by June 30',    current_price: 0.31, change_abs:  0.08 },
  { title: 'CA Governor — Newsom Recall',  current_price: 0.22, change_abs:  0.06 },
  { title: 'GTA VI Delayed Past 2026',     current_price: 0.47, change_abs: -0.05 },
  { title: 'BTC Above $120K Dec 2026',     current_price: 0.38, change_abs:  0.04 },
  { title: 'US Recession by Q4 2026',      current_price: 0.29, change_abs: -0.04 },
];

const styles = {
  card:  { background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px 20px' },
  header: { display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' },
  title: { fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' },
  badge: { fontFamily: 'var(--font-mono)', fontSize: '10px', background: 'var(--accent-blue-dim)', color: 'var(--accent-blue)', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 },
  row:   { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid rgba(30,41,59,0.4)' },
  name:  { fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  detail: { display: 'flex', alignItems: 'center', gap: '12px', fontFamily: 'var(--font-mono)', fontSize: '12px' },
  price: { color: 'var(--text-secondary)' },
  change: { padding: '2px 8px', borderRadius: '4px', fontWeight: 600 },
  empty: { padding: '20px 0', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '12px' },
};
