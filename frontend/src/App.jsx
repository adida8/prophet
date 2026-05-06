import './styles/theme.css';
import './index.css';

import { useMarketData } from './hooks/useMarketData';
import Navbar          from './components/Navbar';
import TickerBar       from './components/TickerBar';
import StatsRow        from './components/StatsRow';
import OddsTable       from './components/OddsTable';
import MoversPanel     from './components/MoversPanel';
import ArbitragePanel  from './components/ArbitragePanel';
import PlatformCards   from './components/PlatformCards';
import CTABanner       from './components/CTABanner';
import LedgerApp       from './ledger/LedgerApp';

export default function App() {
  // Path-based routing — Ledger lives at /ledger and /ledger/0x…
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/ledger')) {
    return <LedgerApp />;
  }

  const { compared, arbitrage, movers, stats, platforms, ticker, loading, connected } = useMarketData();

  return (
    <div className="app">
      <Navbar connected={connected} />
      <TickerBar items={ticker} />

      <main className="main">
        <StatsRow stats={stats} loading={loading} />

        <OddsTable compared={compared} loading={loading} />

        <div className="two-col">
          <MoversPanel movers={movers?.h24 ?? []} window="24H" />
          <ArbitragePanel opportunities={arbitrage} />
        </div>

        <PlatformCards platforms={platforms} />
        <CTABanner />
      </main>

      <footer className="footer">
        <div>© 2026 PredictionEdge · Data sourced from Kalshi API, Polymarket CLOB · Updated every 30 seconds</div>
        <div>Not financial advice · 18+ · Trade responsibly</div>
      </footer>
    </div>
  );
}
