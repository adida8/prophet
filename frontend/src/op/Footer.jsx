// Footer — shared across every editorial page. Carries the canonical
// tagline on every page (per brief: "Footer carries it on small screens"
// and consistently on desktop too).

import { BarsGlyph } from "./BrandLock";

const FOOT_LINKS = {
  editorial: [
    { label: "Today's board",     href: "/#today",      kind: "hash" },
    { label: "Outright winners",  href: "/#outrights",  kind: "hash" },
    { label: "Columns",           href: "/columns",     kind: "external" },
    { label: "Learn the basics",  href: "/learn",       kind: "internal" },
  ],
  company: [
    { label: "About",       href: "/about",                  kind: "internal" },
    { label: "Methodology", href: "/methodology",            kind: "external" },
    { label: "Corrections", href: "/corrections",            kind: "external" },
    { label: "Contact",     href: "mailto:hello@oddsprimer.com", kind: "external" },
  ],
  legal: [
    { label: "Privacy",              href: "/privacy",              kind: "external" },
    { label: "Terms of use",         href: "/terms",                kind: "external" },
    { label: "Affiliate disclosure", href: "/affiliate-disclosure", kind: "external" },
    { label: "Responsible use",      href: "/responsible-use",      kind: "external" },
    { label: "Cookies",              href: "/cookies",              kind: "external" },
    { label: "Accessibility",        href: "/accessibility",        kind: "external" },
  ],
};

export default function Footer({ navigate, currentPath = "/" }) {
  const handle = (link) => (e) => {
    if (link.kind === "external") return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;

    if (link.kind === "hash") {
      e.preventDefault();
      if (currentPath !== "/" && navigate) {
        navigate("/");
        setTimeout(() => {
          const id = link.href.slice(2);
          const target = document.getElementById(id);
          if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 50);
        return;
      }
      const id = link.href.slice(2);
      const target = document.getElementById(id);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    if (link.kind === "internal") {
      e.preventDefault();
      if (navigate) navigate(link.href);
    }
  };

  return (
    <footer className="site-footer">
      <div className="foot-inner">
        <div className="foot-grid">
          <div className="foot-brand">
            <BarsGlyph size={44} />
            <span className="wm">Odds Primer</span>
            <span className="pub">
              The <span className="flame">AI</span> sports desk for <span className="flame">market edge</span>.
            </span>
          </div>

          <div className="foot-col">
            <h4>Editorial</h4>
            <ul>
              {FOOT_LINKS.editorial.map((l) => (
                <li key={l.label}>
                  <a href={l.href} onClick={handle(l)}>{l.label}</a>
                </li>
              ))}
            </ul>
          </div>

          <div className="foot-col">
            <h4>Company</h4>
            <ul>
              {FOOT_LINKS.company.map((l) => (
                <li key={l.label}>
                  <a href={l.href} onClick={handle(l)}>{l.label}</a>
                </li>
              ))}
            </ul>
          </div>

          <div className="foot-col">
            <h4>Legal</h4>
            <ul>
              {FOOT_LINKS.legal.map((l) => (
                <li key={l.label}>
                  <a href={l.href} onClick={handle(l)}>{l.label}</a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="foot-discl">
          <span className="dag">†</span> Odds Primer is an editorial publication. We do not take wagers,
          hold reader funds, or execute trades. Prediction-market trading involves risk; check your
          local laws before acting on what you read. 21+ in NY, MA, NJ, and others. When you act on
          a "View source on" link and trade at a partner venue, the venue may share a portion of
          its trading fee with us — disclosed in full on the{" "}
          <a href="/affiliate-disclosure">Affiliate disclosure</a> page. Our editorial coverage is
          independent of that revenue.
        </p>

        <div className="foot-meta">
          <span>© 2026 Odds Primer.</span>
          <span>Published from the United Kingdom.</span>
          <span>Built with the Odds Primer Design System.</span>
        </div>
      </div>
    </footer>
  );
}
