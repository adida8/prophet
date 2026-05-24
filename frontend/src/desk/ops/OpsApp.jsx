// The Desk · Ops shell — left-sidebar nav + sub-view router.
//
// Two views live here:
//   /desk/ops        → OpsMain  ("The Desk" — read-only run history)
//   /desk/ops/admin  → OpsAdmin ("Desk admin" — schedule + enable/disable)
//
// Both are gated by the same HTTP Basic auth (server.py wraps the SPA
// catch-all under /desk/ops with the gate dependency).

import { useCallback, useEffect, useState } from "react";

import "../../ledger/op-tokens.css";
import "./ops.css";

import OpsMain  from "./OpsMain";
import OpsAdmin from "./OpsAdmin";

const NAV_ITEMS = [
  { id: "main",  label: "The Desk",   path: "/desk/ops" },
  { id: "admin", label: "Desk admin", path: "/desk/ops/admin" },
];

function readView() {
  const p = (typeof window !== "undefined" ? window.location.pathname : "/desk/ops")
    .replace(/\/+$/, "");
  return p === "/desk/ops/admin" ? "admin" : "main";
}

export default function OpsApp() {
  const [view, setView] = useState(readView);

  useEffect(() => {
    function onPop() { setView(readView()); }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((nextId) => {
    const item = NAV_ITEMS.find((n) => n.id === nextId);
    if (!item) return;
    if (window.location.pathname !== item.path) {
      window.history.pushState({}, "", item.path);
    }
    setView(nextId);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, []);

  return (
    <div className="op-page ops ops--shell">
      <aside className="ops__nav">
        <div className="ops__nav-brand">Desk · Ops</div>
        <nav>
          {NAV_ITEMS.map((n) => (
            <button
              key={n.id}
              className={`ops__nav-item ${view === n.id ? "is-active" : ""}`}
              onClick={() => navigate(n.id)}
            >
              {n.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="ops__main">
        {view === "admin" ? <OpsAdmin /> : <OpsMain />}
      </main>
    </div>
  );
}
