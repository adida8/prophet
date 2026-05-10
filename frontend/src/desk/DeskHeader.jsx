// Masthead for /desk — Odds Primer wordmark + edition strip
// "The Desk · World Cup 2026", with a back affordance when the user
// is on a match page.

import { Wordmark } from "../ledger/Wordmark";

export default function DeskHeader({ inMatch, onBack }) {
  return (
    <header className="op-masthead">
      <div className="op-masthead__row">
        <div className="op-masthead__left">
          <a
            href="/desk"
            onClick={(e) => {
              if (inMatch) {
                e.preventDefault();
                onBack();
              }
            }}
            style={{ display: "inline-flex", textDecoration: "none" }}
            aria-label="Back to The Desk"
          >
            <Wordmark glyphHeight={42} fontSize={18} fontWeight={700} />
          </a>
          <span className="op-masthead__divider" aria-hidden="true" />
          <span className="op-masthead__edition">The Desk · Vol. 1 · World Cup 2026</span>
        </div>
      </div>
    </header>
  );
}
