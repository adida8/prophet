import { useState } from 'react';
import './styles/theme.css';
import './index.css';

import { useMarketData } from './hooks/useMarketData';
import Navbar                from './components/Navbar';
import TickerBar             from './components/TickerBar';
import StatsRow              from './components/StatsRow';
import MatchedMarketsTable   from './components/MatchedMarketsTable';
import MarketDetailDrawer    from './components/MarketDetailDrawer';
import PlatformCards         from './components/PlatformCards';
import CTABanner             from './components/CTABanner';
import BetaGate, { useBetaGate } from './components/BetaGate';

export default function App() {
  const { stats, platforms, ticker, connected } = useMarketData();
  const [selectedSignal, setSelectedSignal] = useState(null);
  const { unlocked, unlock } = useBetaGate();

  if (!unlocked) return <BetaGate onUnlock={unlock} />;

  return (
    <div className="app">
      <Navbar connected={connected} />
      <TickerBar items={ticker} />

      <main className="main">
        <StatsRow stats={stats} />
        <MatchedMarketsTable onSelectMarket={setSelectedSignal} />
        <PlatformCards platforms={platforms} />
        <CTABanner />
      </main>

      <footer className="footer">
        <div>© 2026 PredictionEdge · Data from Kalshi API + Polymarket CLOB · Updated every 30s</div>
        <div>Not financial advice · 18+ · Trade responsibly</div>
      </footer>

      {selectedSignal && (
        <MarketDetailDrawer
          signal={selectedSignal}
          onClose={() => setSelectedSignal(null)}
        />
      )}
    </div>
  );
}
