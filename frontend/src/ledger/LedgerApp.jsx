// Oddsprimer Ledger — Phase 0 entry component.
// Path-based routing without a router lib:
//   /ledger          → empty paste-a-wallet state
//   /ledger/0x…      → wallet view

import { useCallback, useEffect, useState } from "react";

import "./op-tokens.css";
import "./ledger.css";

import Filters from "./Filters";
import Masthead from "./Masthead";
import PnLChart from "./PnLChart";
import PositionsTable from "./PositionsTable";
import StatStrip from "./StatStrip";
import WalletInput from "./WalletInput";

const ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;

function readAddressFromPath() {
  // /ledger/0x… → 0x…  ;  /ledger → null
  const parts = window.location.pathname.replace(/\/+$/, "").split("/");
  const tail = parts[parts.length - 1] || "";
  return ADDRESS_RE.test(tail) ? tail.toLowerCase() : null;
}

export default function LedgerApp() {
  const [address, setAddress] = useState(() => readAddressFromPath());

  useEffect(() => {
    function onPop() { setAddress(readAddressFromPath()); }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((nextAddress) => {
    const path = nextAddress ? `/ledger/${nextAddress}` : "/ledger";
    if (window.location.pathname !== path) {
      window.history.pushState({}, "", path);
    }
    setAddress(nextAddress);
  }, []);

  return (
    <div className="op-page">
      {address ? (
        <WalletPage address={address} onReset={() => navigate(null)} />
      ) : (
        <EmptyPage onSubmit={(addr) => navigate(addr)} />
      )}
      <footer className="op-colophon">
        <span>Oddsprimer Ledger · Phase 0 · Polymarket</span>
        <span>Wallets are public · read-only · no orders are placed</span>
      </footer>
    </div>
  );
}

function EmptyPage({ onSubmit }) {
  return (
    <>
      <Masthead />
      <main className="op-main">
        <WalletInput onSubmit={onSubmit} />
      </main>
    </>
  );
}

function WalletPage({ address, onReset }) {
  const [view, setView] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async (signal) => {
    setLoading(true);
    setError(null);
    try {
      const [vRes, hRes] = await Promise.all([
        fetch(`/api/ledger/wallet/${address}`, { signal }),
        fetch(`/api/ledger/wallet/${address}/history`, { signal }),
      ]);
      if (!vRes.ok) throw new Error(`view ${vRes.status}`);
      if (!hRes.ok) throw new Error(`history ${hRes.status}`);
      setView(await vRes.json());
      setHistory(await hRes.json());
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [address]);

  useEffect(() => {
    const ac = new AbortController();
    load(ac.signal);
    return () => ac.abort();
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const r = await fetch("/api/ledger/wallet/refresh", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ address }),
      });
      if (!r.ok) throw new Error(`refresh ${r.status}`);
      const v = await r.json();
      setView(v);
      const hRes = await fetch(`/api/ledger/wallet/${address}/history`);
      if (hRes.ok) setHistory(await hRes.json());
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setRefreshing(false);
    }
  }, [address]);

  return (
    <>
      <Masthead
        refreshedAt={view?.last_refreshed_at}
        onRefresh={onRefresh}
        refreshing={refreshing}
      />
      <main className="op-main">
        <div className="op-walletbar">
          <p className="op-eyebrow">Wallet</p>
          <p className="op-walletbar__addr op-num">{address}</p>
          <button type="button" className="op-link" onClick={onReset}>
            ← Look up another wallet
          </button>
        </div>

        {loading && !view ? (
          <p className="op-loading">— loading wallet…</p>
        ) : error && !view ? (
          <ErrorBlock error={error} onRetry={() => load()} />
        ) : (
          <>
            <StatStrip totals={view?.totals} walletAddress={shortAddr(address)} />
            <Filters />
            <PnLChart history={history} />
            <PositionsTable
              eyebrow="Open · holding now"
              title="Open positions"
              positions={view?.open_positions || []}
              defaultOpen={true}
            />
            <PositionsTable
              eyebrow="Closed · resolved or sold"
              title="Closed positions"
              positions={view?.closed_positions || []}
              defaultOpen={false}
            />
            {error ? <p className="op-footnote">‡ {error}</p> : null}
          </>
        )}
      </main>
    </>
  );
}

function shortAddr(a) {
  return a ? `${a.slice(0, 6)}…${a.slice(-4)}` : "";
}

function ErrorBlock({ error, onRetry }) {
  return (
    <div className="op-error">
      <p className="op-eyebrow">Couldn't load this wallet</p>
      <p className="op-error__msg">{error}</p>
      <button type="button" className="op-btn op-btn--secondary" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}
