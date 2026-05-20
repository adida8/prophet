// /  — the editorial home. Composes the six home blocks under the
// canonical masthead, with the sticky mobile bar pinned to the bottom.

import FeaturedColumns from "../home/FeaturedColumns";
import Hero from "../home/Hero";
import HowWeWork from "../home/HowWeWork";
import NewsletterCapture from "../home/NewsletterCapture";
import OutrightWinners from "../home/OutrightWinners";
import TodaysBoard from "../home/TodaysBoard";
import { TODAYS_SUMMARY } from "../home/data";

import Footer from "../Footer";
import Masthead from "../Masthead";
import StickyMobileBar from "../StickyMobileBar";

export default function HomeV3({ navigate, currentPath }) {
  return (
    <div className="op-site has-sticky-bar">
      <Masthead
        variant="canonical"
        sticky
        currentPath={currentPath}
        navigate={navigate}
        navMeta="Updated 14:08 ET"
        editionLeft="Vol. 1 · World Cup 2026 · Matchday 2"
        editionRight="Markets live"
      />

      <main className="page">
        <Hero navigate={navigate} />
        <OutrightWinners />
        <TodaysBoard />
        <HowWeWork navigate={navigate} />
        <FeaturedColumns />
      </main>

      <NewsletterCapture />

      <Footer navigate={navigate} currentPath={currentPath} />

      <StickyMobileBar navigate={navigate} summary={TODAYS_SUMMARY} />
    </div>
  );
}
