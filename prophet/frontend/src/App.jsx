import { useState, useEffect, useCallback } from "react";
import { Activity, Search, RefreshCw } from "lucide-react";
import "./App.css";

const SERIES_LABELS = {
  KXBTC: "Bitcoin",
  KXETH: "Ethereum",
  KXINX: "S&P 500",
  KXSP500: "S&P 500",
  KXFED: "Fed Rate",
  KXCPI: "CPI",
  KXGDP: "GDP",
  KXNBA: "NBA",
  KXNFL: "NFL",
  KXMLB: "MLB",
  KXTRUMP: "Trump",
};

const fmtPrice = (v) => {
  const n = parseFloat(v);
  if (!n) return "-";
  return `${(n * 100).toFixed(0)}\u00a2`;
};

const fmtVol = (v) => {
  const n = parseFloat(v);
  if (!n) return "-";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(0);
};

const fmtTime = (iso) => {
  if (!iso) return "-";
  const d = new Date(iso);
  const now = new Date();
  const diff = d - now;
  if (diff < 0) return "Closed";
  if (diff < 3600000) return `${Math.round(diff / 60000)}m`;
  if (diff < 86400000) return `${Math.round(diff / 3600000)}h`;
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
};

export default function App() {
  const [markets, setMarkets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("ALL");
  const [error, setError] = useState(null);

  const fetchFeed = useCallback(async () => {
    try {
      const res = await fetch("/api/feed");
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setMarkets(data.markets || []);
      setLastUpdate(new Date());
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFeed();
    const interval = setInterval(fetchFeed, 10000);
    return () => clearInterval(interval);
  }, [fetchFeed]);

  const seriesSet = [...new Set(markets.map((m) => m.series))];

  const filtered = markets.filter((m) => {
    if (filter !== "ALL" && m.series !== filter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        m.title.toLowerCase().includes(q) ||
        m.subtitle.toLowerCase().includes(q) ||
        m.ticker.toLowerCase().includes(q) ||
        m.event_title.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="app">
      <header>
        <div className="header-left">
          <Activity size={22} />
          <h1>Prophet</h1>
          <span className="tag">LIVE FEED</span>
        </div>
        <div className="header-right">
          {lastUpdate && (
            <span className="last-update">
              <RefreshCw size={12} className={loading ? "spin" : ""} />
              {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <span className="count">{filtered.length} contracts</span>
        </div>
      </header>

      {error && <div className="error-bar">API error: {error}</div>}

      <div className="controls">
        <div className="search-box">
          <Search size={16} />
          <input
            type="text"
            placeholder="Search contracts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="filters">
          <button
            className={filter === "ALL" ? "active" : ""}
            onClick={() => setFilter("ALL")}
          >
            All
          </button>
          {seriesSet.map((s) => (
            <button
              key={s}
              className={filter === s ? "active" : ""}
              onClick={() => setFilter(s)}
            >
              {SERIES_LABELS[s] || s}
            </button>
          ))}
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="th-cat">Cat</th>
              <th className="th-contract">Contract</th>
              <th className="th-price">Yes Bid</th>
              <th className="th-price">Yes Ask</th>
              <th className="th-price">No Bid</th>
              <th className="th-price">No Ask</th>
              <th className="th-price">Last</th>
              <th className="th-vol">Volume</th>
              <th className="th-time">Closes</th>
            </tr>
          </thead>
          <tbody>
            {loading && markets.length === 0 ? (
              <tr>
                <td colSpan={9} className="empty">Loading markets...</td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={9} className="empty">No contracts found</td>
              </tr>
            ) : (
              filtered.map((m) => (
                <tr key={m.ticker}>
                  <td className="cat">
                    <span className={`badge badge-${m.series}`}>
                      {SERIES_LABELS[m.series] || m.series}
                    </span>
                  </td>
                  <td className="contract">
                    <div className="contract-title">{m.subtitle || m.title}</div>
                    <div className="contract-event">{m.event_title}</div>
                  </td>
                  <td className="price green">{fmtPrice(m.yes_bid)}</td>
                  <td className="price green">{fmtPrice(m.yes_ask)}</td>
                  <td className="price red">{fmtPrice(m.no_bid)}</td>
                  <td className="price red">{fmtPrice(m.no_ask)}</td>
                  <td className="price last">{fmtPrice(m.last_price)}</td>
                  <td className="vol">{fmtVol(m.volume)}</td>
                  <td className="time">{fmtTime(m.close_time)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
