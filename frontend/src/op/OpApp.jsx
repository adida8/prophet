// Odds Primer — root component for the editorial routes (/, /about, /learn, /learn/*, /world-cup).
//
// Path-based routing without a router lib (matches the LedgerApp + DeskApp
// pattern). Internal navigation uses pushState + popstate so the masthead
// links don't full-reload between editorial pages.

import { useCallback, useEffect, useState } from "react";

import "../ledger/op-tokens.css";
import "./op.css";

import NewsletterPopup from "./NewsletterPopup";
import About from "./pages/About";
import HomeV3 from "./pages/HomeV3";
import LearnIndex from "./pages/LearnIndex";
import WorldCup from "./pages/WorldCup";
import HowPricesAreSet from "./pages/articles/HowPricesAreSet";
import HowToStart from "./pages/articles/HowToStart";
import IsItLegal from "./pages/articles/IsItLegal";
import IsKalshiLegit from "./pages/articles/IsKalshiLegit";
import PredictionMarketFees from "./pages/articles/PredictionMarketFees";
import WhatIsAPredictionMarket from "./pages/articles/WhatIsAPredictionMarket";

const ARTICLE_BY_SLUG = {
  "what-is-a-prediction-market": WhatIsAPredictionMarket,
  "how-prices-are-set":          HowPricesAreSet,
  "is-it-legal":                 IsItLegal,
  "is-kalshi-legit":             IsKalshiLegit,
  "prediction-market-fees":      PredictionMarketFees,
  "how-to-start":                HowToStart,
};

// Per-route SEO metadata. Keyed by route name, or by `learn/<slug>` for
// articles. Client-side title/description is a partial SEO win on an SPA —
// see SEO_MATCH_PAGES_NOTE.md for the prerender/SSR gap that fully unlocks it.
const DEFAULT_TITLE = "Odds Primer — read the market, then read us";
const DEFAULT_DESC =
  "Odds Primer compares prediction-market and sportsbook odds as one probability, then publishes a Pick, Pass, or Avoid verdict on each — with the reasoning.";

const META = {
  home: { title: DEFAULT_TITLE, desc: DEFAULT_DESC },
  about: {
    title: "About Odds Primer — the verdict, explained",
    desc: "Who we are and how the verdict works: an independent model run against live prediction-market and sportsbook prices, published as Pick, Pass, or Avoid.",
  },
  "learn-index": {
    title: "Learn prediction markets — six short primers | Odds Primer",
    desc: "Six plain-English reads on prediction markets: what they are, how prices work, whether they're legal, if Kalshi is safe, the fees, and how to place your first trade.",
  },
  "world-cup": {
    title: "World Cup 2026 odds & prediction markets | Odds Primer",
    desc: "World Cup 2026 odds across Polymarket, Kalshi, and the sportsbooks — standardised to one probability, with a Pick / Pass / Avoid verdict on the winner market and every priced match.",
  },
  "learn/what-is-a-prediction-market": {
    title: "What is a prediction market? | Odds Primer",
    desc: "A prediction market is where you trade contracts that pay out on real-world events — and the price is the probability. How it differs from a sportsbook, in plain English.",
  },
  "learn/how-prices-are-set": {
    title: "How are prediction-market prices set? | Odds Primer",
    desc: "Order books, implied probability, and why two venues quote the same outcome at different prices — with a worked example and an American-odds conversion table.",
  },
  "learn/is-it-legal": {
    title: "Are prediction markets legal? Kalshi & Polymarket by state | Odds Primer",
    desc: "A state-by-state read on the legality of Kalshi, Polymarket, and sportsbook-run prediction products in the US — plus the age limits and where each is blocked.",
  },
  "learn/is-kalshi-legit": {
    title: "Is Kalshi legit and safe? | Odds Primer",
    desc: "Kalshi is a CFTC-regulated US exchange, not an offshore app. What 'regulated' actually buys you — segregated funds, filed markets — and where the real risk still sits.",
  },
  "learn/prediction-market-fees": {
    title: "Polymarket & Kalshi fees explained | Odds Primer",
    desc: "How prediction-market fees work — per-trade charges, maker/taker spreads, and why the fee changes your real break-even probability. What to check before you trade.",
  },
  "learn/how-to-start": {
    title: "How to start: your first prediction-market trade | Odds Primer",
    desc: "Five steps from never-traded to a placed trade you understand — picking a legal venue, verifying, funding small, reading the price, and placing your first contract.",
  },
};

function setMeta(route, articleSlug) {
  if (typeof document === "undefined") return;
  const key = route === "learn-article" ? `learn/${articleSlug}` : route;
  const m = META[key] || META.home;
  document.title = m.title;
  let tag = document.querySelector('meta[name="description"]');
  if (!tag) {
    tag = document.createElement("meta");
    tag.setAttribute("name", "description");
    document.head.appendChild(tag);
  }
  tag.setAttribute("content", m.desc);
}

function readPath() {
  if (typeof window === "undefined") return { route: "home", articleSlug: null };
  const raw = window.location.pathname.replace(/\/+$/, "") || "/";

  if (raw === "/" || raw === "")          return { route: "home", articleSlug: null };
  if (raw === "/about")                   return { route: "about", articleSlug: null };
  if (raw === "/world-cup")               return { route: "world-cup", articleSlug: null };
  if (raw === "/learn")                   return { route: "learn-index", articleSlug: null };
  if (raw.startsWith("/learn/")) {
    const slug = raw.slice("/learn/".length);
    if (ARTICLE_BY_SLUG[slug]) return { route: "learn-article", articleSlug: slug };
    return { route: "learn-index", articleSlug: null };
  }
  return { route: "home", articleSlug: null };
}

export default function OpApp() {
  const [state, setState] = useState(readPath);

  useEffect(() => {
    function onPop() { setState(readPath()); }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Keep <title> + meta description in sync with the current route.
  useEffect(() => {
    setMeta(state.route, state.articleSlug);
  }, [state.route, state.articleSlug]);

  // Internal SPA navigation — used by Masthead + Footer link clicks.
  const navigate = useCallback((to) => {
    if (typeof window === "undefined") return;
    if (window.location.pathname === to) {
      window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
      return;
    }
    window.history.pushState({}, "", to);
    setState(readPath());
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  }, []);

  const currentPath = typeof window !== "undefined" ? window.location.pathname : "/";

  let page;
  if (state.route === "about") {
    page = <About navigate={navigate} currentPath={currentPath} />;
  } else if (state.route === "world-cup") {
    page = <WorldCup navigate={navigate} currentPath={currentPath} />;
  } else if (state.route === "learn-index") {
    page = <LearnIndex navigate={navigate} currentPath={currentPath} />;
  } else if (state.route === "learn-article") {
    const Article = ARTICLE_BY_SLUG[state.articleSlug];
    page = <Article navigate={navigate} currentPath={currentPath} slug={state.articleSlug} />;
  } else {
    page = <HomeV3 navigate={navigate} currentPath={currentPath} />;
  }

  // NewsletterPopup mounts once at the app root so its trigger logic
  // (timer + scroll + suppression) lives outside any one page; the
  // component returns null until it decides to show itself.
  return (
    <>
      {page}
      <NewsletterPopup />
    </>
  );
}
