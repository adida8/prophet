// The Desk · Ops shell — left-sidebar nav + sub-view router.
//
// Four views live here:
//   /desk/ops            → OpsMain      ("The Desk" — read-only run history)
//   /desk/ops/social     → OpsSocial    (social-queue approval)
//   /desk/ops/schedules  → OpsSchedules (unified loop on/off)
//   /desk/ops/admin      → OpsAdmin     ("Desk admin" — schedule + enable/disable)
//
// All gated by the same HTTP Basic auth (server.py wraps the SPA
// catch-all under /desk/ops with the gate dependency).

import { useCallback, useEffect, useState } from "react";

import "../../ledger/op-tokens.css";
import "./ops.css";

import OpsMain      from "./OpsMain";
import OpsAdmin     from "./OpsAdmin";
import OpsSocial    from "./OpsSocial";
import OpsSchedules from "./OpsSchedules";

const NAV_ITEMS = [
  { id: "main",      label: "The Desk",   path: "/desk/ops"           },
  { id: "schedules", label: "Schedules",  path: "/desk/ops/schedules" },
  { id: "social",    label: "Social",     path: "/desk/ops/social"    },
  { id: "admin",     label: "Desk admin", path: "/desk/ops/admin"     },
];

function readView() {
  const p = (typeof window !== "undefined" ? window.location.pathname : "/desk/ops")
    .replace(/\/+$/, "");
  if (p === "/desk/ops/admin")     return "admin";
  if (p === "/desk/ops/social")    return "social";
  if (p === "/desk/ops/schedules") return "schedules";
  return "main";
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
        {view === "admin"     && <OpsAdmin />}
        {view === "social"    && <OpsSocial />}
        {view === "schedules" && <OpsSchedules />}
        {view === "main"      && <OpsMain />}
      </main>
    </div>
  );
}
