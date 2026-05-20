// Odds Primer — root component for the editorial routes (/, /about, /learn, /learn/*).
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
import HowPricesAreSet from "./pages/articles/HowPricesAreSet";
import IsItLegal from "./pages/articles/IsItLegal";
import WhatIsAPredictionMarket from "./pages/articles/WhatIsAPredictionMarket";

const ARTICLE_BY_SLUG = {
  "what-is-a-prediction-market": WhatIsAPredictionMarket,
  "how-prices-are-set":          HowPricesAreSet,
  "is-it-legal":                 IsItLegal,
};

function readPath() {
  if (typeof window === "undefined") return { route: "home", articleSlug: null };
  const raw = window.location.pathname.replace(/\/+$/, "") || "/";

  if (raw === "/" || raw === "")          return { route: "home", articleSlug: null };
  if (raw === "/about")                   return { route: "about", articleSlug: null };
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
