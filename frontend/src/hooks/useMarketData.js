import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from './useWebSocket';

const EMPTY = {
  markets:     [],
  compared:    [],
  arbitrage:   [],
  movers:      { h24: [], h1: [] },
  stats:       {},
  platforms:   {},
  ticker:      [],
  lastUpdated: null,
  loading:     true,
  connected:   false,
};

const WS_URL =
  (window.location.protocol === 'https:' ? 'wss://' : 'ws://') +
  window.location.host +
  '/ws/live';

export function useMarketData() {
  const [data, setData] = useState(EMPTY);

  const handleMessage = useCallback((msg) => {
    if (msg.type === 'init' || msg.type === 'update') {
      const d = msg.data || {};
      setData({
        markets:     d.markets      ?? [],
        compared:    d.compared     ?? [],
        arbitrage:   d.arbitrage    ?? [],
        movers:      d.movers       ?? { h24: [], h1: [] },
        stats:       d.stats        ?? {},
        platforms:   d.platforms    ?? {},
        ticker:      d.ticker       ?? [],
        lastUpdated: d.last_updated ?? null,
        loading:     false,
        connected:   true,
      });
    }
  }, []);

  useWebSocket(WS_URL, handleMessage);

  // Also fetch via REST on mount — gives us data even before first WS push
  useEffect(() => {
    fetch('/api/snapshot')
      .then((r) => r.json())
      .then((snap) => {
        const d = snap?.data ?? {};
        if (Object.keys(d).length === 0) return;
        setData({
          markets:     d.markets      ?? [],
          compared:    d.compared     ?? [],
          arbitrage:   d.arbitrage    ?? [],
          movers:      d.movers       ?? { h24: [], h1: [] },
          stats:       d.stats        ?? {},
          platforms:   d.platforms    ?? {},
          ticker:      d.ticker       ?? [],
          lastUpdated: d.last_updated ?? null,
          loading:     false,
          connected:   false,
        });
      })
      .catch(() => {});
  }, []);

  return data;
}
