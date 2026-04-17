import { useState, useEffect, useRef, useCallback } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar,
} from "recharts";
import {
  Activity, DollarSign, TrendingUp, TrendingDown,
  Wifi, WifiOff, BarChart3, Clock,
} from "lucide-react";
import "./App.css";

const WS_URL =
  (window.location.protocol === "https:" ? "wss://" : "ws://") +
  window.location.host +
  "/ws/dashboard";

// ── Helpers ──────────────────────────────────────────────────────────
const fmt = (n, d = 2) => Number(n).toFixed(d);
const fmtUsd = (n) => `$${fmt(n)}`;
const fmtPct = (n) => `${fmt(n)}%`;
const fmtTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

// ── App ──────────────────────────────────────────────────────────────
export default function App() {
  const [connected, setConnected] = useState(false);
  const [summary, setSummary] = useState({
    total_trades: 0, total_fees: 0, total_invested: 0,
    current_balance: 10000, return_pct: 0,
  });
  const [trades, setTrades] = useState([]);
  const [balanceHistory, setBalanceHistory] = useState([
    { time: fmtTime(new Date().toISOString()), balance: 10000 },
  ]);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };

    ws.onclose = () => {
      setConnected(false);
      reconnectRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);

      if (msg.type === "init") {
        setSummary(msg.data.summary);
        setTrades(msg.data.trades);
        const hist = msg.data.trades.map((t) => ({
          time: fmtTime(t.timestamp),
          balance: t.balance_after,
        }));
        if (hist.length) setBalanceHistory(hist);
      }

      if (msg.type === "trade") {
        const t = msg.data;
        setTrades((prev) => [...prev, t]);
        setBalanceHistory((prev) => [
          ...prev,
          { time: fmtTime(t.timestamp), balance: t.balance_after },
        ]);
      }

      if (msg.type === "heartbeat") {
        setSummary(msg.data);
      }
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const returnPositive = summary.return_pct >= 0;

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <Activity size={24} />
          <h1>Prophet MVP</h1>
          <span className="tag">PAPER TRADING</span>
        </div>
        <div className={`status ${connected ? "online" : "offline"}`}>
          {connected ? <Wifi size={14} /> : <WifiOff size={14} />}
          {connected ? "Live" : "Reconnecting..."}
        </div>
      </header>

      {/* Stats Cards */}
      <div className="cards">
        <StatCard
          icon={<DollarSign size={20} />}
          label="Balance"
          value={fmtUsd(summary.current_balance)}
          accent="blue"
        />
        <StatCard
          icon={returnPositive ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
          label="Return"
          value={fmtPct(summary.return_pct)}
          accent={returnPositive ? "green" : "red"}
        />
        <StatCard
          icon={<BarChart3 size={20} />}
          label="Trades"
          value={summary.total_trades}
          accent="purple"
        />
        <StatCard
          icon={<Clock size={20} />}
          label="Fees Paid"
          value={fmtUsd(summary.total_fees)}
          accent="orange"
        />
      </div>

      {/* Strategy Controls */}
      <SettingsPanel />

      {/* Charts Row */}
      <div className="charts-row">
        <div className="chart-card">
          <h2>Balance Over Time</h2>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={balanceHistory}>
              <defs>
                <linearGradient id="balGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} domain={["dataMin - 100", "dataMax + 100"]} />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                labelStyle={{ color: "#94a3b8" }}
              />
              <Area type="monotone" dataKey="balance" stroke="#6366f1" fill="url(#balGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h2>Trade Sizes</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={trades.slice(-30)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="ticker" tick={{ fill: "#94a3b8", fontSize: 10 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                labelStyle={{ color: "#94a3b8" }}
              />
              <Bar dataKey="contracts" fill="#22d3ee" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Trade Log */}
      <div className="trade-log">
        <h2>Trade Log</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Ticker</th>
                <th>Side</th>
                <th>Price</th>
                <th>Qty</th>
                <th>Fee</th>
                <th>Cost</th>
                <th>Balance</th>
              </tr>
            </thead>
            <tbody>
              {trades.length === 0 ? (
                <tr>
                  <td colSpan={8} className="empty">
                    Waiting for signals...
                  </td>
                </tr>
              ) : (
                [...trades].reverse().slice(0, 100).map((t, i) => (
                  <tr key={i}>
                    <td className="mono">{fmtTime(t.timestamp)}</td>
                    <td className="ticker">{t.ticker}</td>
                    <td className={t.side === "BUY_YES" ? "buy" : "sell"}>{t.side}</td>
                    <td className="mono">{fmt(t.entry_price * 100, 1)}c</td>
                    <td className="mono">{t.contracts}</td>
                    <td className="mono">{fmtUsd(t.fee)}</td>
                    <td className="mono">{fmtUsd(t.net_cost)}</td>
                    <td className="mono">{fmtUsd(t.balance_after)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
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
      // Only update local if user hasn't made unsaved changes
      setLocal((prev) => {
        if (!settings) return data; // first load
        return prev;
      });
    } catch { /* ignore */ }
  }, [settings]);

  useEffect(() => {
    fetchSettings();
    const interval = setInterval(fetchSettings, 5000);
    return () => clearInterval(interval);
  }, []);

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

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  if (!settings) return null;

  const sliders = [
    { key: "yes_ceiling", label: "YES Ceiling", min: 0.1, max: 1.0, step: 0.01 },
    { key: "no_floor", label: "NO Floor", min: 0.1, max: 1.0, step: 0.01 },
    { key: "min_edge", label: "Min Edge", min: 0.001, max: 0.2, step: 0.001 },
  ];

  const dirty = JSON.stringify(local) !== JSON.stringify(settings);

  return (
    <div className="settings-panel">
      <h2>Strategy Controls</h2>
      <div className="settings-sliders">
        {sliders.map(({ key, label, min, max, step }) => (
          <div key={key} className="slider-group">
            <div className="slider-header">
              <label>{label}</label>
              <span className="slider-value">
                {(local[key] ?? 0).toFixed(key === "min_edge" ? 3 : 2)}
              </span>
            </div>
            <input
              type="range"
              min={min}
              max={max}
              step={step}
              value={local[key] ?? min}
              onChange={(e) => setLocal({ ...local, [key]: parseFloat(e.target.value) })}
            />
          </div>
        ))}
        <button onClick={handleSave} disabled={saving || !dirty} className="btn-save">
          {saving ? "Saving..." : "Update Thresholds"}
        </button>
      </div>
      {toast && (
        <div className={`toast toast-${toast.type}`}>{toast.message}</div>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, accent }) {
  return (
    <div className={`stat-card accent-${accent}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-body">
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}</span>
      </div>
    </div>
  );
}
