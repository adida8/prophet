export default function CTABanner() {
  return (
    <div style={styles.banner}>
      <div>
        <h3 style={styles.heading}>Get real-time arbitrage alerts before anyone else</h3>
        <p style={styles.sub}>Free cross-platform odds comparison. Premium alerts for price gaps &gt;2%.</p>
      </div>
      <button style={styles.btn} onClick={() => alert('Coming soon — enter your email below!')}>
        Get Free Alerts →
      </button>
    </div>
  );
}

const styles = {
  banner: {
    background: 'linear-gradient(135deg, rgba(34,197,94,0.08), rgba(6,182,212,0.08))',
    border: '1px solid rgba(34,197,94,0.2)',
    borderRadius: 'var(--radius-xl)',
    padding: '24px 32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '20px',
  },
  heading: {
    fontSize: '16px',
    fontWeight: 700,
    color: 'var(--text-primary)',
    marginBottom: '4px',
    fontFamily: 'var(--font-sans)',
  },
  sub: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    fontFamily: 'var(--font-sans)',
  },
  btn: {
    background: 'var(--accent-green)',
    color: 'var(--bg-primary)',
    fontFamily: 'var(--font-sans)',
    fontSize: '13px',
    fontWeight: 700,
    padding: '10px 24px',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    cursor: 'pointer',
    letterSpacing: '-0.2px',
    whiteSpace: 'nowrap',
    transition: 'transform 0.15s, box-shadow 0.15s',
  },
};
