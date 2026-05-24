# ADR 0001 — `VerdictState.WITHDRAWN`

- Date: 2026-05-24
- Status: Accepted
- Driver: External-consumer wire (Market Tips AI, see `desk/desk/distribute/`)
- Authority: `THE_DESK_SPEC.md` §6 (contract changes require an ADR)

## Context

The published `MatchOutput` carries a `verdict.state` enum:

```python
class VerdictState(str, Enum):
    PICK  = "pick"
    PASS  = "pass"
    AVOID = "avoid"
```

Until now the contract had no lifecycle vocabulary for *a match the engine
stops publishing*. Fixtures cancelled, postponed beyond the slug's date,
renamed (which forces a new `match_id`), or simply de-listed from
Polymarket would just disappear from `index.json` — the previously
published per-match JSON kept its last verdict on disk forever.

For our own static site that's tolerable: the index regenerates and the
detail page becomes unreachable. For an **external consumer that durably
stores the payload** (Market Tips AI's webhook receiver), silence is
indistinguishable from "engine is offline". The receiver has no signal
that the match has left our live universe — only that we've stopped
pushing.

## Decision

Add a fourth state:

```python
class VerdictState(str, Enum):
    PICK      = "pick"
    PASS      = "pass"
    AVOID     = "avoid"
    WITHDRAWN = "withdrawn"
```

Field-level semantics on `Verdict` match pass/avoid:

| Field          | pick    | pass / avoid / **withdrawn** |
| -------------- | ------- | ---------------------------- |
| `side`         | set     | null                         |
| `market_venue` | set     | null                         |
| `price`        | set     | null                         |
| `edge_pp`      | set     | optional                     |
| `model_p`      | set     | null                         |
| `market_p`     | set     | null                         |
| `market_url`   | set     | optional                     |

The existing `_state_invariants` validator branches on `state == PICK`; the
"not pick" branch already requires the right fields to be null. Extending
the enum is enough — withdrawn falls into the existing not-pick branch.

## Detection

`desk/desk/distribute/withdrawn.py` diffs the per-sport `index.json`
written by the *previous* run against the in-memory list of matches the
*current* run published. Any `match_id` present in the prior index but
absent from the current run is a withdrawal: the engine emits one final
`MatchOutput` for it with `verdict.state = "withdrawn"`, writes it to
disk through the normal `Publisher`, and enqueues it to the distribute
outbox. Subsequent runs no longer see that `match_id` in the prior index
(because the current run's index excluded it), so withdrawn payloads
emit exactly once per fixture.

The withdrawn payload reuses the previously-published `team_a`, `team_b`,
`kickoff_utc`, `competition`, `venue`, and `market_outcomes` from the
prior on-disk JSON. The verdict is replaced; `copy` is rewritten to a
short stub explaining the withdrawal. `updated_at` is set to the current
run's clock, preserving the strict-monotonic invariant per `match_id`
that the external wire depends on.

## Invariants

1. **One-shot.** A withdrawn payload is published exactly once per
   `match_id`. The next run no longer carries that match_id in either
   the prior index (the writer overwrote it with the new index) or the
   current run (the fixture is gone from ingest). The match_id leaves
   the live universe.
2. **No resurrection inside a slug.** If a fixture re-appears under the
   same `match_id` after a withdrawal, we treat it as a fresh stream
   under the same id. The receiver MUST tolerate a non-withdrawn
   payload following a withdrawn one for the same `match_id` (idempotent
   on `(match_id, updated_at)` covers this — the newer `updated_at`
   replaces the prior state). In practice this only happens after
   operator intervention; the engine doesn't currently un-withdraw on
   its own.
3. **`match_id` immutability is unchanged.** Renames or fixture moves
   still require publishing the original slug once as `withdrawn` and
   starting a new `match_id` for the renamed/moved fixture.

## Consumer migration

- Any consumer that switches on `verdict.state` MUST add a branch for
  `"withdrawn"`. Pydantic / Zod validators that hard-error on unknown
  enum values will reject a withdrawn payload until updated.
- Consumers that treat `verdict.state` opaquely (string passthrough)
  need no change.
- The JSON Schema at `desk/contract.schema.json` is regenerated as part
  of this change; the in-sync test (`tests/test_contract.py::test_schema_file_in_sync`)
  enforces it.

## Alternatives considered

- **Out-of-band lifecycle envelope** (separate `{event: "withdrawn", ...}`
  message, contract untouched). Rejected: requires the distribute layer
  to carry a payload shape distinct from the disk JSON, which opens a
  long-term divergence problem. Keeping disk == push byte-identical is
  load-bearing for our debugging story ("what did we push for X?" →
  read the file on disk).
- **Pseudo-state via `verdict.state="pass"` + a sentinel in `copy`**.
  Rejected: pass already carries meaning ("we looked, no edge"); the
  receiver can't disambiguate "still tracking, no edge" from "no longer
  tracking" without parsing `copy`, and parsing prose is exactly what a
  typed contract exists to avoid.
- **Stop pushing, let the receiver time out.** Rejected: silent. The
  receiver has no actionable signal to render to the operator on the
  B2C side.

## References

- `desk/desk/publish/contract.py` — the enum + validator
- `desk/desk/distribute/withdrawn.py` — detection
- `desk/CONTRACT_CHANGELOG.md` — public changelog entry
- `desk/contract.schema.json` — regenerated schema
