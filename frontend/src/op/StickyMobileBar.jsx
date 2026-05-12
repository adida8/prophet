// Sticky mobile bottom bar — home only, under 820px viewport (CSS-controlled).

export default function StickyMobileBar({ navigate, summary }) {
  const handleLearn = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (navigate) navigate("/learn");
  };

  const handleToBoard = (e) => {
    e.preventDefault();
    const target = document.getElementById("today");
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const { picks = 0, passes = 0, avoids = 0 } = summary || {};

  return (
    <div className="sticky-bar" role="navigation" aria-label="Quick actions">
      <a className="count" href="#today" onClick={handleToBoard}>
        Today: <strong><span className="pp">{picks} {picks === 1 ? "pick" : "picks"}</span> · {passes} passes · {avoids} {avoids === 1 ? "avoid" : "avoids"}</strong>
      </a>
      <a className="pill" href="/learn" onClick={handleLearn}>
        Learn <span className="arr">↗</span>
      </a>
    </div>
  );
}
