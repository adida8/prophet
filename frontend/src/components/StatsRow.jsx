import { fmtVolume, toCents, fmtPct } from '../utils/formatters';

export default function StatsRow({ stats = {}, loading }) {
  const volume   = stats.total_volume_24h ?? 0;
  const markets  = stats.total_markets   ?? 0;
  const arbCount = stats.arb_count       ?? 0;
  const avgEdge  = stats.avg_arb_edge_pct ?? 0;
  const bm       = stats.biggest_mover   ?? {};

  return (
    <div style={styles.row}>
      <StatCard
        label="24h Volume (All Platforms)"
        value={loading ? '—' : fmtVolume(volume)}
        sub={loading ? '' : '▲ aggregated across platforms'}
        subColor="var(--accent-green)"
      />
      <StatCard
        label="Active Markets Tracked"
        value={loading ? '—' : markets.toLocaleString()}
        sub="Kalshi + Polymarket"
        subColor="var(--text-muted)"
      />
      <StatCard
        label="Live Arbitrage Opportunities"
        value={loading ? '—' : arbCount}
        valueColor="var(--accent-amber)"
        sub={arbCount > 0 ? `Avg edge: ${avgEdge.toFixed(1)}%` : 'None above 1.5% threshold'}
        subColor="var(--accent-amber)"
      />
      <StatCard
        label="Biggest Mover (24h)"
        value={loading ? '—' : (bm.title ? bm.title.slice(0, 28) : '—')}
        valueSize="15px"
        valueColor="var(--accent-green)"
        sub={bm.current ? `${toCents(bm.current)} · ${fmtPct(bm.change_pct)}` : ''}
        subColor="var(--accent-green)"
      />
    </div>
  );
}

function StatCard({ label, value, sub, subColor, valueColor, valueSize }) {
  return (
    <div style={styles.card}>
      <div style={styles.label}>{label}</div>
      <div style={{ ...styles.value, color: valueColor ?? 'var(--text-primary)', fontSize: valueSize ?? '24px' }}>
        {value}
      </div>
      {sub && <div style={{ ...styles.sub, color: subColor ?? 'var(--text-muted)' }}>{sub}</div>}
    </div>
  );
}

const styles = {
  row: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
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
    fontSize: '11px',
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '6px',
    fontFamily: 'var(--font-sans)',
  },
  value: {
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    letterSpacing: '-1px',
    lineHeight: 1.1,
  },
  sub: {
    fontFamily: 'var(--font-mono)',
    fontSize: '11px',
    marginTop: '4px',
  },
};
