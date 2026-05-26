// Global site footer — runs across every editorial page. Carries the
// newsletter signup at the top, two short nav columns, the legal /
// educational-publication disclaimer, and a single baseline line with
// the contact mailto. The navy ink background ties it to the masthead
// rule at the top of every page.

import FooterSignup from "./FooterSignup";

const FOOT_LINKS = {
  read: [
    { label: "Matches", href: "/matches", kind: "external" },
    { label: "Learn",   href: "/learn",   kind: "internal" },
  ],
  about: [
    { label: "How it works",         href: "/methodology",                  kind: "external" },
    { label: "How to read a price", href: "/learn/how-prices-are-set",     kind: "internal" },
    { label: "Contact",             href: "mailto:editor@oddsprimer.com",  kind: "external" },
  ],
};

// TODO: add a "Follow" column once we have real handles for the
// publication (X, Bluesky, etc.). Leaving it out for now beats shipping
// placeholder/dead social links.

export default function Footer({ navigate, currentPath: _currentPath = "/" }) {
  const handleLink = (link) => (e) => {
    if (link.kind === "external") return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    if (link.kind === "internal") {
      e.preventDefault();
      if (navigate) navigate(link.href);
    }
  };

  return (
    <footer className="site-footer">
      <FooterSignup navigate={navigate} />

      <div className="foot-inner">
        <div className="foot-grid">
          <div className="foot-col">
            <h4>Read</h4>
            <ul>
              {FOOT_LINKS.read.map((l) => (
                <li key={l.label}>
                  <a href={l.href} onClick={handleLink(l)}>{l.label}</a>
                </li>
              ))}
            </ul>
          </div>

          <div className="foot-col">
            <h4>About</h4>
            <ul>
              {FOOT_LINKS.about.map((l) => (
                <li key={l.label}>
                  <a href={l.href} onClick={handleLink(l)}>{l.label}</a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="foot-legal">
          Odds Primer is an educational publication. It compares prices and explains them
          &mdash; it does not offer betting advice or take wagers. 18+. Please gamble responsibly.
        </p>

        <div className="foot-baseline">
          <span className="foot-baseline__copy">
            &copy; 2026 Odds Primer &middot;{" "}
            <a href="/terms">Terms &amp; legal</a>
          </span>
          <a
            className="foot-baseline__contact"
            href="mailto:hello@oddsprimer.com"
          >
            hello@oddsprimer.com
          </a>
        </div>
      </div>
    </footer>
  );
}
