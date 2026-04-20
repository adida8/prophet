import { fmtVolume, affiliateUrl } from '../utils/formatters';

const PLATFORM_ORDER = ['kalshi', 'polymarket', 'draftkings'];

export default function PlatformCards({ platforms = {} }) {
  return (
    <div>
      <div style={styles.header}>
        <span style={styles.title}>Platform Comparison</span>
      </div>
      <div style={styles.grid}>
        {PLATFORM_ORDER.map((key) => {
          const p = platforms[key];
          if (!p) return null;
          return <PlatformCard key={key} platform={key} data={p} />;
        })}
      </div>
    </div>
  );
}

function PlatformCard({ platform, data }) {
  const liveVol = data.live_volume_24h > 0
    ? fmtVolume(data.live_volume_24h)
    : data.weekly_vol ?? '—';

  const url = affiliateUrl(data.url ?? '#', platform);

  return (
    <a href={url} target="_blank" rel="noopener noreferrer" style={styles.card}>
      <div style={styles.name}>{data.name ?? platform}</div>
      <div style={styles.type}>{data.type ?? ''}</div>
      <div style={styles.statsGrid}>
        <div>
          <div style={styles.psLabel}>24h Vol</div>
          <div style={styles.psValue}>{liveVol}</div>
        </div>
        <div>
          <div style={styles.psLabel}>Markets</div>
          <div style={styles.psValue}>
            {data.live_markets > 0 ? `${data.live_markets.toLocaleString()}` : data.market_count ?? '—'}
          </div>
        </div>
        <div>
          <div style={styles.psLabel}>Fees</div>
          <div style={{ ...styles.psValue, color: data.fee === '0%' ? 'var(--accent-green)' : 'var(--text-primary)' }}>
            {data.fee ?? '—'}
          </div>
        </div>
        <div>
          <div style={styles.psLabel}>Avg Spread</div>
          <div style={styles.psValue}>{data.avg_spread ?? '—'}</div>
        </div>
      </div>
      <div style={styles.cta}>Compare →</div>
    </a>
  );
}

const styles = {
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' },
  title:  { fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)' },
  grid:   { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '20px' },
  card:   {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '20px',
    textDecoration: 'none',
    display: 'block',
    position: 'relative',
    transition: 'all 0.2s',
    cursor: 'pointer',
  },
  name:   { fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px', fontFamily: 'var(--font-sans)' },
  type:   { fontSize: '11px', color: 'var(--text-muted)', marginBottom: '12px', fontFamily: 'var(--font-sans)' },
  statsGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' },
  psLabel: { fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', fontFamily: 'var(--font-sans)' },
  psValue: { fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' },
  cta: { fontSize: '11px', color: 'var(--accent-green)', fontWeight: 600, marginTop: '12px', fontFamily: 'var(--font-sans)' },
};
