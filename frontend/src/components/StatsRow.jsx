import { fmtVolume } from '../utils/formatters';

export default function StatsRow({ stats = {} }) {
  const volume  = stats.total_volume_24h ?? 0;
  const markets = stats.total_markets   ?? 0;

  return (
    <div style={styles.row}>
      <StatCard
        label="24h Volume (All Platforms)"
        value={volume > 0 ? fmtVolume(volume) : '—'}
        sub="Kalshi + Polymarket aggregated"
      />
      <StatCard
        label="Active Markets Tracked"
        value={markets > 0 ? markets.toLocaleString() : '—'}
        sub="Kalshi + Polymarket"
      />
    </div>
  );
}

function StatCard({ label, value, sub }) {
  return (
    <div style={styles.card}>
      <div style={styles.label}>{label}</div>
      <div style={styles.value}>{value}</div>
      <div style={styles.sub}>{sub}</div>
    </div>
  );
}

const styles = {
  row: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '12px',
    marginBottom: '20px',
  },
  card: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '16px 20px',
  },
  label: {
    fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '0.5px', marginBottom: '6px', fontFamily: 'var(--font-sans)',
  },
  value: {
    fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '24px',
    letterSpacing: '-1px', lineHeight: 1.1, color: 'var(--text-primary)',
  },
  sub: {
    fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px',
  },
};
