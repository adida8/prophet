# Distribute — sample wire payloads for Market Tips AI

Reference payloads for the outbound MTA wire (`desk/desk/distribute/`).
These are committed so MTAI can run them through their validator without
us standing up a live push.

## `fb-wc26-winner.mta-sample.json`

A real `content_type: "outright"` payload, produced by
`outright_wire_payload()` over the live `fb-wc26-winner.json` publish.
Regenerate with:

```bash
cd desk && PYTHONPATH=. python -c "import json; \
from desk.distribute.outright import outright_wire_payload; \
print(json.dumps(outright_wire_payload(json.load(open('data/output/outrights/fb-wc26-winner.json', encoding='utf-8'))), indent=2, ensure_ascii=False))"
```

What the wire transform does to the published outright JSON (MTA contract
v1.2, agreed 2026-05-31):

1. adds `content_type: "outright"` — routes off the same webhook as
   matches (matches default to `"match"` on MTA's side).
2. lifts `model.hard_signal_adjustments` to a top-level
   `hard_signal_adjustments` list of **structured objects** (always
   present, even empty) so it sits where matches carry it. Outright
   nudges key on `team` — there is no `a/b` `side` a two-team match has.

Everything else (sport, competition, copy, verdict, ladder, resolves_at,
updated_at) already mirrors the `MatchOutput` spine and passes through
unchanged. On the wire the body is canonical-JSON (sorted keys, no
whitespace); the pretty-printed file here is for human review only.
