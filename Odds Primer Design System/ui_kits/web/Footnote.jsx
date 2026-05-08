// Footnote.jsx — inline dagger marker + on-hover popover. Also exports a
// FootnoteList for the footer column on long-form pages.
const FootnoteMark = ({ symbol = "†", children, id }) => {
  const [open, setOpen] = React.useState(false);
  return (
    <span style={{ position: "relative", display: "inline" }}
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}>
      <a href={id ? `#fn-${id}` : undefined}
         style={{
           fontFamily: "var(--font-serif)", fontStyle: "italic",
           color: "var(--flame)", fontWeight: 500,
           textDecoration: "none", padding: "0 2px",
           cursor: "help",
         }}>{symbol}</a>
      {open && children && (
        <span style={{
          position: "absolute", left: 0, top: "1.5em", zIndex: 5,
          width: 280, padding: "12px 14px",
          background: "var(--paper-pure)",
          border: "1px solid var(--rule)",
          borderRadius: 6,
          boxShadow: "0 8px 24px rgba(14,34,64,0.08)",
          fontFamily: "var(--font-serif)", fontSize: 13,
          fontStyle: "normal", fontWeight: 400,
          color: "var(--graphite)", lineHeight: 1.55,
        }}>{children}</span>
      )}
    </span>
  );
};

const FootnoteList = ({ items = [] }) => (
  <aside style={{
    padding: "16px 18px",
    background: "var(--paper-warm)",
    borderLeft: "2px solid var(--flame)",
    fontFamily: "var(--font-serif)", fontSize: 13, lineHeight: 1.55,
    color: "var(--graphite)",
  }}>
    {items.map((it, i) => (
      <div key={i} id={`fn-${it.id || i}`} style={{
        display: "flex", gap: 10,
        marginTop: i === 0 ? 0 : 8,
      }}>
        <span style={{ fontStyle: "italic", color: "var(--flame)", fontWeight: 500 }}>{it.symbol || "†"}</span>
        <span><strong style={{ color: "var(--ink)", fontWeight: 500 }}>{it.term}.</strong> {it.body}</span>
      </div>
    ))}
  </aside>
);

window.FootnoteMark = FootnoteMark;
window.FootnoteList = FootnoteList;
