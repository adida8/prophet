import { toCents, fmtChange } from '../utils/formatters';

export default function TickerBar({ items = [] }) {
  // Duplicate items so the scroll loop is seamless
  const display = items.length > 0 ? [...items, ...items] : DEMO_ITEMS;

  return (
    <div style={styles.bar}>
      <div style={styles.track} className="ticker-track">
        {display.map((item, i) => (
          <TickerItem key={i} item={item} />
        ))}
      </div>
    </div>
  );
}

function TickerItem({ item }) {
  const up = item.gap >= 0;
  return (
    <>
      <span style={styles.sep}>|</span>
      <div style={styles.item}>
        <span style={styles.name}>{item.title}</span>
        <span style={styles.price}>{toCents(item.price)}</span>
        {item.gap > 0.005 && (
          <span style={{ ...styles.change, color: up ? 'var(--accent-green)' : 'var(--accent-red)' }}>
            {fmtChange(item.gap)}
          </span>
        )}
      </div>
    </>
  );
}

const DEMO_ITEMS = [
  { title: 'BTC >$95K May',       price: 0.67, gap: 0.04 },
  { title: 'Fed Hold June',        price: 0.82, gap: -0.02 },
  { title: 'Lakers Win Finals',    price: 0.14, gap: 0.03 },
  { title: 'Iran Ceasefire Jul',   price: 0.31, gap: 0.08 },
  { title: 'GTA VI Nov 2026',      price: 0.53, gap: -0.05 },
  { title: 'CPI >3.0% Apr',        price: 0.44, gap: 0.01 },
  { title: 'S&P >6000 EOY',        price: 0.71, gap: -0.03 },
  { title: 'Vance 2028 Nom',       price: 0.39, gap: 0.02 },
];

const styles = {
  bar: {
    background: 'var(--bg-secondary)',
    borderBottom: '1px solid var(--border)',
    overflow: 'hidden',
    height: '36px',
    display: 'flex',
    alignItems: 'center',
  },
  track: {
    display: 'flex',
    alignItems: 'center',
    gap: '24px',
    whiteSpace: 'nowrap',
    animation: 'tickerScroll 40s linear infinite',
    fontFamily: 'var(--font-mono)',
    fontSize: '12px',
    paddingLeft: '24px',
  },
  sep: {
    color: 'var(--border-accent)',
    flexShrink: 0,
  },
  item: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    flexShrink: 0,
  },
  name: {
    color: 'var(--text-muted)',
  },
  price: {
    color: 'var(--text-primary)',
    fontWeight: 600,
  },
  change: {
    fontWeight: 500,
  },
};
