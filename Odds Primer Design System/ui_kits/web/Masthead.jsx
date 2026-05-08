// Masthead.jsx — sticky top, edition strip, live indicator, nav.
const Masthead = ({ tab = "tournament", onTab = () => {}, updated = "12 min ago", live = true }) => {
  const tabs = [
    { id: "tournament", label: "Tournament" },
    { id: "matches",    label: "Matches" },
    { id: "scorer",     label: "Top scorer" },
    { id: "glossary",   label: "Glossary" },
  ];
  return (
    <header style={{
      position: "sticky", top: 0, zIndex: 10,
      background: "var(--paper)",
      borderBottom: "2px solid var(--ink)",
    }}>
      <div style={{
        padding: "16px var(--gutter-page)",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        maxWidth: 1280, margin: "0 auto",
      }}>
        <Wordmark size={18} glyphSize={42} />
        <div style={{
          display: "flex", alignItems: "center", gap: 14,
          fontFamily: "var(--font-sans)",
          fontSize: 11, fontWeight: 600, letterSpacing: "0.08em",
          textTransform: "uppercase", color: "var(--graphite)",
        }}>
          <span>Vol. 1</span>
          <span style={{ color: "var(--rule)" }}>·</span>
          <span>World Cup 2026 Edition</span>
          {live && <>
            <span style={{ color: "var(--rule)" }}>·</span>
            <span>Live · Group stage</span>
          </>}
        </div>
      </div>
      <nav style={{
        padding: "10px var(--gutter-page)",
        borderTop: "1px solid var(--rule)",
        display: "flex", gap: 22, alignItems: "center",
        maxWidth: 1280, margin: "0 auto",
        fontFamily: "var(--font-sans)", fontSize: 13,
      }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => onTab(t.id)} style={{
            background: "none", border: 0, padding: "2px 0", cursor: "pointer",
            fontFamily: "inherit", fontSize: "inherit",
            fontWeight: tab === t.id ? 600 : 400,
            color: tab === t.id ? "var(--ink)" : "var(--graphite)",
            borderBottom: tab === t.id ? "1px solid var(--ink)" : "1px solid transparent",
          }}>{t.label}</button>
        ))}
        <span style={{
          marginLeft: "auto",
          fontFamily: "var(--font-serif)", fontStyle: "italic",
          fontSize: 12, color: "var(--graphite)",
        }}>Updated {updated}</span>
      </nav>
    </header>
  );
};

window.Masthead = Masthead;
