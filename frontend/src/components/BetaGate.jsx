import { useState } from 'react';

const STORAGE_KEY = 'pe_beta_unlocked';

function check(password) {
  // Password is set via VITE_BETA_PASSWORD env var at build time.
  // Falls back to 'predictionedge' for local dev.
  const expected = import.meta.env.VITE_BETA_PASSWORD || 'predictionedge';
  return password.trim().toLowerCase() === expected.toLowerCase();
}

export function useBetaGate() {
  const [unlocked, setUnlocked] = useState(() => {
    try { return sessionStorage.getItem(STORAGE_KEY) === '1'; } catch { return false; }
  });

  const unlock = (password) => {
    if (check(password)) {
      try { sessionStorage.setItem(STORAGE_KEY, '1'); } catch {}
      setUnlocked(true);
      return true;
    }
    return false;
  };

  return { unlocked, unlock };
}

export default function BetaGate({ onUnlock }) {
  const [input, setInput]   = useState('');
  const [error, setError]   = useState(false);
  const [shake, setShake]   = useState(false);

  const submit = (e) => {
    e.preventDefault();
    if (check(input)) {
      onUnlock();
    } else {
      setError(true);
      setShake(true);
      setTimeout(() => setShake(false), 500);
    }
  };

  return (
    <div style={styles.overlay}>
      <div style={{ ...styles.card, animation: shake ? 'shake 0.4s ease' : 'none' }}>
        <div style={styles.logo}>PE</div>
        <div style={styles.title}>PredictionEdge</div>
        <div style={styles.sub}>Private Beta · Enter access code to continue</div>

        <form onSubmit={submit} style={styles.form}>
          <input
            style={{ ...styles.input, borderColor: error ? 'var(--accent-amber)' : 'var(--border)' }}
            type="password"
            placeholder="Access code"
            value={input}
            autoFocus
            onChange={(e) => { setInput(e.target.value); setError(false); }}
          />
          {error && <div style={styles.errorMsg}>Incorrect access code</div>}
          <button style={styles.btn} type="submit">Enter →</button>
        </form>

        <div style={styles.disclaimer}>
          Not financial advice · 18+ · Trade responsibly
        </div>
      </div>

      <style>{`
        @keyframes shake {
          0%,100% { transform: translateX(0); }
          20%,60%  { transform: translateX(-8px); }
          40%,80%  { transform: translateX(8px); }
        }
      `}</style>
    </div>
  );
}

const styles = {
  overlay: {
    position: 'fixed', inset: 0, background: 'var(--bg-primary)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 100, fontFamily: 'var(--font-sans)',
  },
  card: {
    background: 'var(--bg-card)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)', padding: '48px 40px',
    width: '360px', textAlign: 'center', boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
  },
  logo: {
    width: '52px', height: '52px', borderRadius: '14px', margin: '0 auto 16px',
    background: 'linear-gradient(135deg, var(--accent-green) 0%, var(--accent-cyan) 100%)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '18px', color: '#000',
  },
  title: { fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' },
  sub:   { fontSize: '13px', color: 'var(--text-muted)', marginBottom: '28px' },

  form:  { display: 'flex', flexDirection: 'column', gap: '10px' },
  input: {
    background: 'var(--bg-secondary)', border: '1px solid', borderRadius: '8px',
    padding: '12px 16px', fontSize: '14px', color: 'var(--text-primary)',
    fontFamily: 'var(--font-mono)', outline: 'none', textAlign: 'center',
    transition: 'border-color 0.15s',
  },
  errorMsg: { fontSize: '12px', color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)' },
  btn: {
    background: 'var(--accent-green)', color: '#000', border: 'none', borderRadius: '8px',
    padding: '12px', fontSize: '14px', fontWeight: 700, cursor: 'pointer',
    fontFamily: 'var(--font-sans)', marginTop: '4px', transition: 'opacity 0.15s',
  },

  disclaimer: { fontSize: '11px', color: 'var(--text-muted)', marginTop: '24px' },
};
