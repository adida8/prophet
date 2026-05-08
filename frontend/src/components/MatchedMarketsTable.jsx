import { useState, useEffect, useRef } from 'react';
import { toCents, fmtVolume, fmtDate, affiliateUrl } from '../utils/formatters';

const SOURCE_LABEL = { explicit: 'VERIFIED', fuzzy: 'FUZZY', single: 'SINGLE' };
const SOURCE_COLOR = {
  explicit: { bg: 'var(--accent-green-dim)', fg: 'var(--accent-green)' },
  fuzzy:    { bg: 'var(--accent-amber-dim)', fg: 'var(--accent-amber)' },
  single:   { bg: 'rgba(255,255,255,0.06)', fg: 'var(--text-muted)' },
};

export default function MatchedMarketsTable({ onSelectMarket }) {
  const [signals, setSignals]     = useState([]);
  const [loading, setLoading]     = useState(true);
  const [lastFetch, setLastFetch] = useState(null);
  const intervalRef = useRef(null);

  const fetchSignals = () => {
    fetch('/api/signal')
      .then((r) => r.json())
      .then((data) => {
        setSignals(Array.isArray(data) ? data : []);
        setLastFetch(new Date());
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchSignals();
    intervalRef.current = setInterval(fetchSignals, 30_000);
    return () => clearInterval(intervalRef.current);
  }, []);

  return (
    <div>
      <div style={styles.header}>
        <div style={styles.title}>
          Prophet Signals
          <span style={styles.liveBadge}>LIVE</span>
        </div>
        <div style={styles.meta}>
          {lastFetch ? `Updated ${lastFetch.toLocaleTimeString()}` : 'Loading…'}
        </div>
      </div>

      <div style={styles.tableWrap}>
        {loading ? (
          <div style={styles.empty}>Fetching signals…</div>
        ) : signals.length === 0 ? (
          <div style={styles.empty}>
            No signals right now — market prices don't show enough edge. Check back soon.
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={{ ...styles.th, textAlign: 'left', width: '35%' }}>Market</th>
                <th style={styles.th}>Kalshi</th>
                <th style={styles.th}>Polymarket</th>
                <th style={styles.th}>Signal</th>
                <th style={styles.th}>Confidence</th>
                <th style={styles.th}>Kelly %</th>
                <th style={styles.th}>Resolves</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((sig) => (
                <SignalRow key={sig.market_id} signal={sig} onSelect={onSelectMarket} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function SignalRow({ signal, onSelect }) {
  const kp  = signal.platforms?.kalshi;
  const pp  = signal.platforms?.polymarket;
  const src = signal.source || 'fuzzy';
  const srcStyle = SOURCE_COLOR[src] || SOURCE_COLOR.fuzzy;

  return (
    <tr
      style={styles.row}
      className="odds-row"
      onClick={() => onSelect?.(signal)}
    >
      {/* Market title + source badge */}
      <td style={styles.tdName}>
        <div style={styles.marketName}>{signal.title}</div>
        <div style={styles.marketMeta}>
          <span style={{ ...styles.srcBadge, background: srcStyle.bg, color: srcStyle.fg }}>
            {SOURCE_LABEL[src] || src.toUpperCase()}
          </span>
          {signal.resolution_date ? ` · ${fmtDate(signal.resolution_date)}` : ''}
        </div>
      </td>

      {/* Kalshi price */}
      <td style={styles.tdCenter}>
        {kp ? (
          <a href={affiliateUrl(kp.url, 'kalshi')} target="_blank" rel="noopener noreferrer"
             style={{ textDecoration: 'none' }} onClick={(e) => e.stopPropagation()}>
            <span style={signal.best_yes_platform === 'kalshi' ? styles.priceBest : styles.priceNormal}>
              {toCents(kp.yes_price)}
            </span>
          </a>
        ) : <span style={styles.priceEmpty}>—</span>}
      </td>

      {/* Polymarket price */}
      <td style={styles.tdCenter}>
        {pp ? (
          <a href={affiliateUrl(pp.url, 'polymarket')} target="_blank" rel="noopener noreferrer"
             style={{ textDecoration: 'none' }} onClick={(e) => e.stopPropagation()}>
            <span style={signal.best_yes_platform === 'polymarket' ? styles.priceBest : styles.priceNormal}>
              {toCents(pp.yes_price)}
            </span>
          </a>
        ) : <span style={styles.priceEmpty}>—</span>}
      </td>

      {/* Signal badge */}
      <td style={styles.tdCenter}>
        <span style={signal.side === 'BUY_YES' ? styles.signalBuy : styles.signalPass}>
          {signal.side === 'BUY_YES' ? 'BUY YES' : signal.side === 'BUY_NO' ? 'BUY NO' : 'PASS'}
        </span>
      </td>

      {/* Confidence */}
      <td style={styles.tdCenter}>
        <ConfidenceBar value={signal.confidence} />
      </td>

      {/* Kelly % */}
      <td style={styles.tdCenter}>
        <span style={styles.kelly}>{signal.kelly_pct?.toFixed(1) ?? '—'}%</span>
      </td>

      {/* Resolution date */}
      <td style={styles.tdCenter}>
        <span style={styles.resolveDate}>{fmtDate(signal.resolution_date) || '—'}</span>
      </td>
    </tr>
  );
}

function ConfidenceBar({ value }) {
  const pct = Math.round((value ?? 0) * 100);
  const color = pct >= 80 ? 'var(--accent-green)' : pct >= 60 ? 'var(--accent-amber)' : 'var(--text-muted)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center' }}>
      <div style={{ width: '48px', height: '4px', background: 'rgba(255,255,255,0.06)', borderRadius: '2px', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: '2px', background: color }} />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color }}>{pct}%</span>
    </div>
  );
}

const styles = {
  header:    { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' },
  title:     { fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-sans)', display: 'flex', alignItems: 'center', gap: '8px' },
  liveBadge: { fontFamily: 'var(--font-mono)', fontSize: '10px', background: 'var(--accent-blue-dim)', color: 'var(--accent-blue)', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 },
  meta:      { fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' },

  tableWrap: { background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', marginBottom: '20px' },
  empty:     { padding: '48px 40px', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '13px', lineHeight: 1.6 },
  table:     { width: '100%', borderCollapse: 'collapse' },

  th: {
    fontSize: '10px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '0.8px', padding: '12px 16px', textAlign: 'center',
    borderBottom: '1px solid var(--border)', background: 'rgba(0,0,0,0.2)',
    fontFamily: 'var(--font-sans)',
  },
  row:       { borderBottom: '1px solid rgba(30,41,59,0.5)', transition: 'background 0.15s', cursor: 'pointer' },
  tdName:    { padding: '14px 16px' },
  tdCenter:  { padding: '14px 16px', textAlign: 'center' },

  marketName: { fontWeight: 600, color: 'var(--text-primary)', fontSize: '13px', marginBottom: '4px', fontFamily: 'var(--font-sans)' },
  marketMeta: { fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' },

  srcBadge:   { fontSize: '9px', fontWeight: 700, padding: '1px 5px', borderRadius: '3px', letterSpacing: '0.5px', fontFamily: 'var(--font-mono)' },

  priceBest:  { fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '14px', padding: '3px 8px', borderRadius: '4px', display: 'inline-block', minWidth: '48px', background: 'var(--accent-green-dim)', color: 'var(--accent-green)', border: '1px solid rgba(34,197,94,0.25)' },
  priceNormal:{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '14px', padding: '3px 8px', borderRadius: '4px', display: 'inline-block', minWidth: '48px', background: 'rgba(255,255,255,0.04)', color: 'var(--text-secondary)', border: '1px solid transparent' },
  priceEmpty: { fontFamily: 'var(--font-mono)', fontSize: '14px', color: 'var(--text-muted)' },

  signalBuy:  { fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 700, background: 'var(--accent-green-dim)', color: 'var(--accent-green)', padding: '3px 8px', borderRadius: '4px', letterSpacing: '0.5px' },
  signalPass: { fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 600, background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)', padding: '3px 8px', borderRadius: '4px' },

  kelly:       { fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 600, color: 'var(--accent-cyan)' },
  resolveDate: { fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' },
};
