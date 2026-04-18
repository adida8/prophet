import { useState, useEffect, useRef, useCallback } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar,
} from "recharts";
import {
  Activity, DollarSign, TrendingUp, TrendingDown,
  Wifi, WifiOff, BarChart3, Clock, AlertTriangle, ShieldOff,
} from "lucide-react";
import "./App.css";

const WS_URL = `ws://${window.location.hostname}:8000/ws/dashboard`;
const API = "";

// ── Helpers ──────────────────────────────────────────────────────────
const fmt = (n, d = 2) => Number(n).toFixed(d);
const fmtUsd = (n) => `$${fmt(n)}`;
const fmtPct = (n) => `${fmt(n)}%`;
const fmtTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

const STATUS_CLASS = {
  pending: "pending",
  resting: "resting",
  filled: "filled",
  cancelled: "cancelled",
  failed: "failed",
};

// ── App ──────────────────────────────────────────────────────────────
export default function App() {
  const [connected, setConnected] = useState(false);
  const [mode, setMode] = useState("paper");
  const [limits, setLimits] = useState({
    max_trade_dollars: 50, daily_loss_limit: 200, max_trades_per_day: 20,
  });
  const [summary, setSummary] = useState({
    total_trades: 0, total_fees: 0, total_invested: 0,
    current_balance: 10000, return_pct: 0,
  });
  const [trades, setTrades] = useState([]);
  const [orders, setOrders] = useState([]);
  const [positions, setPositions] = useState([]);
  const [liveBalance, setLiveBalance] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [confirmLive, setConfirmLive] = useState(false);
  const [balanceHistory, setBalanceHistory] = useState([
    { time: fmtTime(new Date().toISOString()), balance: 10000 },
  ]);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  // ── WebSocket lifecycle ────────────────────────────────────────────
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
        setTrades(msg.data.trades || []);
        setMode(msg.data.mode || "paper");
        setOrders(msg.data.orders || []);
        setPositions(msg.data.positions || []);
        if (msg.data.limits) setLimits(msg.data.limits);
        const hist = (msg.data.trades || []).map((t) => ({
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
        if (msg.data.mode) setMode(msg.data.mode);
      }

      if (msg.type === "mode_change") {
        setMode(msg.data.mode);
      }

      if (msg.type === "order_update") {
        const o = msg.data;
        setOrders((prev) => {
          const idx = prev.findIndex((x) => x.id === o.id);
          if (idx === -1) return [...prev, o];
          const next = prev.slice();
          next[idx] = o;
          return next;
        });
      }

      if (msg.type === "safety_alert") {
        setAlerts((prev) => [msg.data, ...prev].slice(0, 5));
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

  // Refresh live balance whenever mode flips to live
  useEffect(() => {
    if (mode !== "live") { setLiveBalance(null); return; }
    let cancelled = false;
    const fetchLive = async () => {
      try {
        const r = await fetch(`${API}/api/balance/live`);
        if (!r.ok) return;
        const data = await r.json();
        if (!cancelled) setLiveBalance(data);
      } catch {/* ignore */}
    };
    fetchLive();
    const id = setInterval(fetchLive, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, [mode]);

  // ── Actions ───────────────────────────────────────────────────────
  const requestLive = () => setConfirmLive(true);
  const cancelConfirm = () => setConfirmLive(false);

  const toggleMode = async (next) => {
    const r = await fetch(`${API}/api/mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: next, confirm: next === "live" }),
    });
    if (r.ok) {
      const data = await r.json();
      setMode(data.mode);
    }
    setConfirmLive(false);
  };

  const pressKill = async () => {
    if (!window.confirm("Kill switch: cancel all resting orders and revert to PAPER mode?")) return;
    const r = await fetch(`${API}/api/kill`, { method: "POST" });
    if (r.ok) {
      const data = await r.json();
      setMode(data.mode);
    }
  };

  const returnPositive = summary.return_pct >= 0;
  const isLive = mode === "live";

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <Activity size={24} />
          <h1>Prophet MVP</h1>
          <span className={`tag mode-tag ${isLive ? "live" : "paper"}`}>
            {isLive ? "LIVE TRADING" : "PAPER TRADING"}
          </span>
        </div>
        <div className="header-right">
          {isLive && (
            <button className="kill-btn" onClick={pressKill} title="Emergency stop">
              <ShieldOff size={14} /> KILL
            </button>
          )}
          <button
            className={`mode-toggle ${isLive ? "to-paper" : "to-live"}`}
            onClick={() => (isLive ? toggleMode("paper") : requestLive())}
          >
            {isLive ? "Switch to paper" : "Go live"}
          </button>
          <div className={`status ${connected ? "online" : "offline"}`}>
            {connected ? <Wifi size={14} /> : <WifiOff size={14} />}
            {connected ? "Live" : "Reconnecting..."}
          </div>
        </div>
      </header>

      {/* Safety alerts */}
      {alerts.length > 0 && (
        <div className="alerts">
          {alerts.map((a, i) => (
            <div key={i} className="alert">
              <AlertTriangle size={14} />
              <div>
                <strong>{a.rule}</strong> — {a.message}
              </div>
              <span className="alert-time">{fmtTime(a.timestamp)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Stats Cards */}
      <div className="cards">
        <StatCard
          icon={<DollarSign size={20} />}
          label={isLive ? "Paper balance" : "Balance"}
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
        {isLive && liveBalance && (
          <StatCard
            icon={<DollarSign size={20} />}
            label="Live balance (Kalshi)"
            value={fmtUsd((liveBalance.balance ?? 0) / 100)}
            accent="green"
          />
        )}
      </div>

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

      {/* Order panel — live mode only */}
      {isLive && (
        <div className="trade-log order-panel">
          <h2>Live Orders</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Ticker</th>
                  <th>Side</th>
                  <th>Qty</th>
                  <th>Price</th>
                  <th>Fill</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {orders.length === 0 ? (
                  <tr><td colSpan={7} className="empty">No live orders yet</td></tr>
                ) : (
                  [...orders].reverse().slice(0, 50).map((o) => (
                    <tr key={o.id}>
                      <td className="mono">{fmtTime(o.created_at)}</td>
                      <td className="ticker">{o.ticker}</td>
                      <td className={o.side === "yes" ? "buy" : "sell"}>{o.side.toUpperCase()}</td>
                      <td className="mono">{o.contracts}</td>
                      <td className="mono">{o.price}¢</td>
                      <td className="mono">{o.fill_price != null ? `${o.fill_price}¢` : "—"}</td>
                      <td>
                        <span className={`pill ${STATUS_CLASS[o.status] || ""}`}>
                          {o.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

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

      {/* Go-live confirmation modal */}
      {confirmLive && (
        <div className="modal-backdrop" onClick={cancelConfirm}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Enable live trading?</h3>
            <p>
              You are about to enable live trading on Kalshi Demo. Orders will be placed
              against your real demo account.
            </p>
            <ul>
              <li>Max <strong>{fmtUsd(limits.max_trade_dollars)}</strong> per trade</li>
              <li>Daily loss limit: <strong>{fmtUsd(limits.daily_loss_limit)}</strong></li>
              <li>Max <strong>{limits.max_trades_per_day}</strong> trades per day</li>
            </ul>
            <p>You can switch back to paper mode any time.</p>
            <div className="modal-actions">
              <button onClick={cancelConfirm}>Cancel</button>
              <button className="primary" onClick={() => toggleMode("live")}>
                Enable live trading
              </button>
            </div>
          </div>
        </div>
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
