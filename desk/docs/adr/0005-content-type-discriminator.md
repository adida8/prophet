# ADR 0005 — `content_type` payload discriminator on `MatchOutput`

- Date: 2026-05-31
- Status: Accepted
- Driver: Outright distribution to Market Tips AI (MTA) over a shared webhook
- Authority: `THE_DESK_SPEC.md` §6 (contract changes require an ADR)

## Context

MTA consumes two Desk payload shapes over **one** webhook: per-match
verdicts (`MatchOutput`) and per-outright verdicts (the outright wire
payload — see `desk/desk/distribute/outright.py`). MTA needs to route an
incoming body to the right handler/validator without sniffing fields.

The outright wire already carries `content_type: "outright"` (injected by
`outright_wire_payload`). Matches carried no discriminator, so MTA relied
on a "missing → match" default. That default is live in MTA prod, but an
explicit field is cleaner and removes the implicit coupling: every body
now self-declares its type.

## Decision

Add an additive, defaulted discriminator to `MatchOutput`:

```python
content_type: Literal["match"] = "match"
```

- **Match** payloads emit `"content_type": "match"` (on disk and on the
  wire — it's a real contract field now).
- **Outright** payloads emit `"content_type": "outright"`, added by the
  wire transform (the outright on-disk JSON is an internal artefact, not a
  `MatchOutput`, so it is not bound by this contract).

## Consequences

- **Additive-optional.** The field defaults, so any consumer that ignores
  it — or defaults missing→`"match"`, as MTA does — is unaffected. No
  migration required. Logged in `CONTRACT_CHANGELOG.md` as v1.5.0 `add`.
- The published per-match JSON Faktor consumes now carries
  `content_type: "match"`. Harmless; Faktor ignores unknown/extra keys.
- `desk/contract.schema.json` regenerated (`scripts/regen_schema.py`);
  the in-sync test enforces it.
- The committed match sample at `docs/distribute/` is regenerated to
  carry the field so it reflects the live wire shape.
