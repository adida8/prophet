import { useState, useEffect, useRef, useCallback } from "react";

const WS_URL =
  (window.location.protocol === "https:" ? "wss://" : "ws://") +
  window.location.host +
  "/ws/dashboard";

function Toast({ message, type, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [onClose]);
  return (
    <div className={`toast ${type}`}>
      {message}
    </div>
  );
}

function SettingsPanel() {
  const [settings, setSettings] = useState(null);
  const [local, setLocal] = useState({});
  const [toast, setToast] = useState(null);
  const [saving, setSaving] = useState(false);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch("/api/settings");
      const data = await res.json();
      setSettings(data);
      setLocal(data);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    fetchSettings();
    const interval = setInterval(fetchSettings, 5000);
    return () => clearInterval(interval);
  }, [fetchSettings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(local),
      });
      if (!res.ok) throw new Error("Save failed");
      const data = await res.json();
      setSettings(data);
      setLocal(data);
      setToast({ message: "Settings saved", type: "success" });
    } catch {
      setToast({ message: "Failed to save settings", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  if (!settings) return <div className="panel">Loading settings...</div>;

  const sliders = [
    { key: "yes_ceiling", label: "YES Ceiling", min: 0.1, max: 1.0, step: 0.01 },
    { key: "no_floor", label: "NO Floor", min: 0.1, max: 1.0, step: 0.01 },
    { key: "min_edge", label: "Min Edge", min: 0.001, max: 0.2, step: 0.001 },
  ];

  const dirty = JSON.stringify(local) !== JSON.stringify(settings);

  return (
    <div className="panel settings-panel">
      <h2>Strategy Controls</h2>
      {sliders.map(({ key, label, min, max, step }) => (
        <div key={key} className="slider-group">
          <label>{label}</label>
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={local[key] ?? min}
            onChange={(e) => setLocal({ ...local, [key]: parseFloat(e.target.value) })}
          />
          <span className="slider-value">{(local[key] ?? 0).toFixed(key === "min_edge" ? 3 : 2)}</span>
        </div>
      ))}
      <button onClick={handleSave} disabled={saving || !dirty} className="btn-save">
        {saving ? "Saving..." : "Update"}
      </button>
      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  );
}

function TradeRow({ trade }) {
  return (
    <tr>
      <td>{trade.ticker}</td>
      <td className={trade.side === "BUY_YES" ? "green" : "red"}>{trade.side}</td>
      <td>{(trade.price * 100).toFixed(1)}\u00a2</td>
      <td>{trade.contracts}</td>
      <td>{trade.edge?.toFixed(4)}</td>
      <td>${trade.balance_after?.toFixed(2)}</td>
    </tr>
  );
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [trades, setTrades] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "init") {
          setSummary(msg.data.summary);
          setTrades(msg.data.trades);
        } else if (msg.type === "trade") {
          setTrades((prev) => [...prev, msg.data]);
        } else if (msg.type === "heartbeat") {
          setSummary(msg.data);
        }
      };

      ws.onclose = () => setTimeout(connect, 3000);
    }

    connect();
    return () => wsRef.current?.close();
  }, []);

  return (
    <div className="app">
      <header>
        <h1>Prophet Dashboard</h1>
        {summary && (
          <div className="stats">
            <div className="stat">
              <span className="stat-label">Balance</span>
              <span className="stat-value">${summary.current_balance?.toLocaleString()}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Trades</span>
              <span className="stat-value">{summary.total_trades ?? summary.trade_count ?? 0}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Return</span>
              <span className={`stat-value ${(summary.return_pct ?? 0) >= 0 ? "green" : "red"}`}>
                {summary.return_pct?.toFixed(2)}%
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Fees</span>
              <span className="stat-value">${summary.total_fees?.toFixed(4)}</span>
            </div>
          </div>
        )}
      </header>

      <main>
        <SettingsPanel />

        <div className="panel trades-panel">
          <h2>Trade History</h2>
          {trades.length === 0 ? (
            <p className="empty">No trades yet. Waiting for signals...</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Side</th>
                    <th>Price</th>
                    <th>Qty</th>
                    <th>Edge</th>
                    <th>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {[...trades].reverse().map((t, i) => (
                    <TradeRow key={i} trade={t} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
