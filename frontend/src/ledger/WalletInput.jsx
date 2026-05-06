// Empty-state wallet input. The activation moment is paste-and-see —
// one field, one button. No copy ceremony.

import { useState } from "react";

const ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;

export default function WalletInput({ onSubmit }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState(null);

  const trimmed = value.trim();
  const valid = ADDRESS_RE.test(trimmed);

  function handleSubmit(e) {
    e.preventDefault();
    if (!valid) {
      setError("Address must be 0x followed by 40 hex characters.");
      return;
    }
    setError(null);
    onSubmit(trimmed.toLowerCase());
  }

  return (
    <div className="op-empty">
      <p className="op-eyebrow">Phase 0 · Polymarket only · read-only</p>
      <h1 className="op-empty__title">
        Paste a wallet. See the portfolio behind it.
      </h1>
      <p className="op-empty__deck">
        Polymarket wallets are public. Drop one in and we'll show every open
        position, every closed position, and the cumulative profit and loss
        over time.
      </p>

      <form className="op-empty__form" onSubmit={handleSubmit}>
        <label className="op-empty__label" htmlFor="wallet-input">
          Wallet address
        </label>
        <div className="op-empty__row">
          <input
            id="wallet-input"
            className="op-input"
            type="text"
            placeholder="0x…"
            spellCheck={false}
            autoComplete="off"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (error) setError(null);
            }}
          />
          <button
            type="submit"
            className="op-btn op-btn--primary"
            disabled={!valid}
          >
            Open ledger
          </button>
        </div>
        {error ? <p className="op-empty__error">{error}</p> : null}
        <p className="op-footnote op-empty__hint">
          † A Polymarket wallet is the address you see on a profile page —
          forty hex characters after <code>0x</code>. We never write to it.
        </p>
      </form>
    </div>
  );
}
