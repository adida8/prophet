// Masthead — sticky site nav.
//
// Two BrandLock variants per the brief: "canonical" (glyph + wordmark + tagline,
// home only) and "minimal" (glyph + wordmark only, About + Learn).
// Nav links use the OpApp navigate() callback so internal hops don't reload.

import BrandLock from "./BrandLock";

const NAV_ITEMS = [
  { label: "Today",      href: "/#today",      external: false, matchPath: "/" },
  { label: "Outrights",  href: "/#outrights",  external: false, matchPath: "/" },
  { label: "World Cup",  href: "/world-cup",   external: false, matchPath: "/world-cup" },
  { label: "Learn",      href: "/learn",       external: false, matchPath: "/learn" },
  { label: "About",      href: "/about",       external: false, matchPath: "/about" },
];

export default function Masthead({
  variant = "minimal",
  currentPath = "/",
  navigate,
  navMeta,
  editionLeft,
  editionRight,
  sticky = false,
}) {
  const cls = `site-masthead${sticky ? " is-sticky" : ""}`;

  const handleNavClick = (item) => (e) => {
    if (item.external) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;

    // Hash-only on current path → smooth scroll; otherwise SPA-navigate.
    if (item.href.startsWith("/#")) {
      e.preventDefault();
      if (currentPath !== "/" && navigate) {
        navigate("/");
        // Defer hash scroll until home mounts.
        setTimeout(() => {
          const id = item.href.slice(2);
          const target = document.getElementById(id);
          if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 50);
        return;
      }
      const id = item.href.slice(2);
      const target = document.getElementById(id);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    e.preventDefault();
    if (navigate) navigate(item.href);
  };

  const isCurrent = (item) => {
    if (item.href.startsWith("/#")) {
      return currentPath === "/" || currentPath === "";
    }
    if (item.matchPath === "/learn") {
      return currentPath === "/learn" || currentPath.startsWith("/learn/");
    }
    return currentPath === item.matchPath;
  };

  return (
    <header className={cls}>
      <div className="inner">
        <BrandLock variant={variant} href="/" onNavigate={navigate} />

        <nav className="site-nav" aria-label="Primary">
          <ul>
            {NAV_ITEMS.map((item) => (
              <li key={item.label}>
                <a
                  href={item.href}
                  onClick={handleNavClick(item)}
                  aria-current={isCurrent(item) ? "page" : undefined}
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        {navMeta ? <span className="nav-meta">{navMeta}</span> : null}

        <button className="nav-burger" aria-label="Open navigation" type="button">
          <svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">
            <rect y="0"  width="16" height="1.5" fill="currentColor" />
            <rect y="5"  width="16" height="1.5" fill="currentColor" />
            <rect y="10" width="16" height="1.5" fill="currentColor" />
          </svg>
        </button>
      </div>

      {(editionLeft || editionRight) && (
        <div className="edition-strip">
          <div className="inner">
            <span>{editionLeft}</span>
            <span className={editionRight && editionRight.toString().toLowerCase().includes("market") ? "live" : ""}>
              {editionRight}
            </span>
          </div>
        </div>
      )}
    </header>
  );
}
