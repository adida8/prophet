export default function Navbar({ connected }) {
  return (
    <nav style={styles.nav}>
      <div style={styles.logo}>
        <div style={styles.logoIcon}>PE</div>
        PredictionEdge
      </div>

      <div style={styles.links}>
        {['Odds Compare', 'Markets', 'Arbitrage', 'Platforms', 'Movers', 'Alerts'].map((label) => (
          <a key={label} href="#" style={styles.link}>{label}</a>
        ))}
      </div>

      <div style={styles.right}>
        <div style={{ ...styles.dot, background: connected ? 'var(--accent-green)' : 'var(--accent-amber)' }} />
        <span style={styles.liveLabel}>{connected ? 'Live' : 'Connecting'}</span>
      </div>
    </nav>
  );
}

const styles = {
  nav: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 32px',
    height: '56px',
    background: 'rgba(10, 14, 23, 0.92)',
    backdropFilter: 'blur(12px)',
    borderBottom: '1px solid var(--border)',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    fontSize: '16px',
    letterSpacing: '-0.5px',
    color: 'var(--text-primary)',
    textDecoration: 'none',
  },
  logoIcon: {
    width: '28px',
    height: '28px',
    background: 'linear-gradient(135deg, var(--accent-green), var(--accent-cyan))',
    borderRadius: '6px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '13px',
    fontWeight: 700,
    color: 'var(--bg-primary)',
    fontFamily: 'var(--font-mono)',
  },
  links: {
    display: 'flex',
    gap: '4px',
  },
  link: {
    color: 'var(--text-secondary)',
    textDecoration: 'none',
    fontSize: '13px',
    fontWeight: 500,
    padding: '6px 14px',
    borderRadius: '6px',
    transition: 'color 0.15s',
    fontFamily: 'var(--font-sans)',
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  dot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    boxShadow: '0 0 8px var(--accent-green)',
    animation: 'pulse 2s infinite',
  },
  liveLabel: {
    fontFamily: 'var(--font-mono)',
    fontSize: '11px',
    color: 'var(--accent-green)',
    textTransform: 'uppercase',
    letterSpacing: '1px',
  },
};
