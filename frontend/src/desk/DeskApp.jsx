// Odds Primer · The Desk — entry component.
//
// Path-based routing without a router lib:
//   /desk             → list view (WC 2026 fixtures)
//   /desk/{match_id}  → single-match verdict page
//
// Wireframe + CTA decisions per the conversion design doc:
// Pick / Pass / Avoid all stay on the list (calibration story); Pick
// fixtures get the strongest card treatment. Match page puts the
// verdict + CTA above the fold, with the blurb below.

import { useCallback, useEffect, useState } from "react";

import "../ledger/op-tokens.css";
import "./desk.css";

import DeskList   from "./DeskList";
import DeskMatch  from "./DeskMatch";
import DeskHeader from "./DeskHeader";
import OpsApp     from "./ops/OpsApp";

// match_id pattern from desk/contract.schema.json
const MATCH_ID_RE = /^[a-z0-9]{2,8}-[a-z0-9]+(?:-[a-z0-9]+){2,}-\d{8}$/;

function isOpsPath() {
  const p = window.location.pathname.replace(/\/+$/, "");
  return p === "/desk/ops";
}

function readMatchIdFromPath() {
  // /desk/{match_id} → match_id  ;  /desk → null
  const parts = window.location.pathname.replace(/\/+$/, "").split("/");
  const tail = parts[parts.length - 1] || "";
  return MATCH_ID_RE.test(tail) ? tail : null;
}

export default function DeskApp() {
  // The ops dashboard owns its own surface — render it before the match
  // list/detail. Server.py gates the page route, so an unauthed user
  // never reaches this code path.
  if (typeof window !== "undefined" && isOpsPath()) {
    return <OpsApp />;
  }

  const [matchId, setMatchId] = useState(() => readMatchIdFromPath());

  useEffect(() => {
    function onPop() { setMatchId(readMatchIdFromPath()); }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((nextMatchId) => {
    const path = nextMatchId ? `/desk/${nextMatchId}` : "/desk";
    if (window.location.pathname !== path) {
      window.history.pushState({}, "", path);
    }
    setMatchId(nextMatchId);
    // Scroll to top on navigation — list and match page have very
    // different content shapes, leaving the user mid-scroll is jarring.
    window.scrollTo({ top: 0, behavior: "instant" });
  }, []);

  return (
    <div className="op-page op-desk">
      <DeskHeader inMatch={Boolean(matchId)} onBack={() => navigate(null)} />
      {matchId ? (
        <DeskMatch matchId={matchId} onBack={() => navigate(null)} />
      ) : (
        <DeskList onSelect={navigate} />
      )}
      <footer className="op-colophon">
        <span>Odds Primer · The Desk · World Cup 2026</span>
        <span>Pick / Pass / Avoid · live prices verified at the venue</span>
      </footer>
    </div>
  );
}
