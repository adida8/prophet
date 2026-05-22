"""Engine runner — orchestrates one full pass.

PR 4: pipeline is now end-to-end. For each priced fixture we build
features, run the model, compute a verdict, and publish the resulting
`MatchOutput`. Per-fixture failures are isolated per spec §9 — a single
bad row never blocks the rest of the publish.

PR 1 of THE_DESK_OPS_DASHBOARD_SPEC: every pass now also assembles a
`RunReport` and hands it to a `Recorder` for persistence. The published
contract is unchanged — the run log is a separate internal artifact.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from desk import config
from desk.ops import (
    FixtureRow,
    ForcedPassCounts,
    IngestStats,
    Recorder,
    RunReport,
    RunStatus,
    RunTrigger,
    SignalImpactRow,
    SourceStatus,
    StageCount,
    VerdictCounts,
    diff_snapshots,
    fixture_row_from_match,
)
from desk.ops.report import ErrorEntry, ErrorLevel, SourceFreshness, run_id_for
from desk.publish import (
    Competition,
    MatchOutput,
    Publisher,
    Venue,
    Verdict,
)
from desk.publish.contract import VerdictState
from desk.signals.runtime import SignalsRuntime
from desk.sport import FixtureRef
from desk.sports import active_sports
from desk.verdict.compare import MarketSnapshot

log = logging.getLogger("desk.runner")


class _NullCtx:
    """No-op context manager — used when the signals runtime is unavailable
    so the inner loop can unconditionally sit inside `with`."""
    def __enter__(self): return self
    def __exit__(self, *exc): return False


def _build_match(
    fx: FixtureRef,
    *,
    verdict: Verdict,
    now: datetime,
    copy=None,
) -> MatchOutput:
    venue = None
    if fx.venue_city and fx.venue_stadium and fx.venue_country:
        venue = Venue(
            city=fx.venue_city,
            stadium=fx.venue_stadium,
            country=fx.venue_country,
        )
    kwargs = dict(
        match_id=fx.match_id,
        sport=fx.sport,
        competition=Competition(
            code=fx.competition_code,
            label=fx.competition_label,
            stage=fx.competition_stage,
        ),
        kickoff_utc=fx.kickoff_utc,
        team_a=fx.team_a,
        team_b=fx.team_b,
        venue=venue,
        market_outcomes=list(fx.market_outcomes),
        verdict=verdict,
        updated_at=now,
    )
    if copy is not None:
        kwargs["copy"] = copy
    return MatchOutput(**kwargs)


def _venues_in(snapshot: MarketSnapshot) -> list[str]:
    return sorted({p.venue for p in snapshot.prices})


def _competitions_for_report() -> list[str]:
    allow = config.COMPETITION_ALLOWLIST
    if allow is None:
        return ["*"]
    return sorted(allow)


def _classify_status(
    *,
    sources: list[SourceStatus],
    errors: list[ErrorEntry],
    n_published: int,
    any_sport_ran: bool,
) -> RunStatus:
    """Map source/error signals to the three RunStatus buckets.

    - `fail`  when the fixture-of-record source failed OR no sport ran.
    - `partial` when a non-fatal source failed, or a per-fixture error landed.
    - `ok`    otherwise.

    Sources whose id ends in `_gamma` are the fixture-of-record in v1
    (Polymarket). When that one is failed the run can't publish; when a
    secondary source (e.g. `kalshi_kxwcgame`) fails we still publish off
    Polymarket alone.
    """
    if not any_sport_ran:
        return RunStatus.FAIL
    primary_failed = any(
        s.id.endswith("_gamma") and s.status == SourceFreshness.FAILED
        for s in sources
    )
    if primary_failed and n_published == 0:
        return RunStatus.FAIL
    any_source_failed = any(s.status == SourceFreshness.FAILED for s in sources)
    if any_source_failed or errors:
        return RunStatus.PARTIAL
    return RunStatus.OK


def run_once(
    *,
    output_dir: Path | None = None,
    recorder: Recorder | None = None,
    trigger: RunTrigger = RunTrigger.MANUAL,
) -> dict[str, list[Path]]:
    output_dir = Path(output_dir or config.OUTPUT_DIR)
    pub = Publisher(output_dir=output_dir)
    if recorder is None:
        # DESK_OPS_DIR (when set) wins so prod can point ops history at
        # a persistent volume that survives Railway deploys. Otherwise
        # fall back to the runtime output_dir so tests + --output-dir
        # overrides keep working.
        ops_dir_env = os.getenv("DESK_OPS_DIR")
        recorder = Recorder(root=Path(ops_dir_env) if ops_dir_env else output_dir / "ops")

    started_at = datetime.now(tz=timezone.utc)
    written: dict[str, list[Path]] = {}

    # ── Run-level telemetry accumulators ───────────────────────────
    errors:        list[ErrorEntry]      = []
    sources_all:   list[SourceStatus]    = []
    snapshot_rows: list[FixtureRow]      = []
    signal_impact: list[SignalImpactRow] = []
    raw_events_total   = 0
    after_filter_total = 0
    priced_total       = 0
    priced_note        : str | None = None
    n_published        = 0
    n_pick = n_pass = n_avoid = 0
    n_illiquid = n_stub_elo = 0
    any_sport_ran = False

    # News-signals are entirely additive: if the operator has been
    # running `desk fetch-signals` + `desk extract-signals`, the cache
    # file exists and we enrich each match's editorial_citations from
    # it. If it doesn't, we publish exactly what we did before.
    signals_runtime_factory = SignalsRuntime.for_sport

    for sport in active_sports():
        any_sport_ran = True
        log.info("listing priced fixtures for %s", sport.code)
        try:
            pairs = list(sport.list_priced_fixtures())
        except Exception as e:                          # noqa: BLE001 — spec §9
            log.warning("priced ingest failed for %s: %s", sport.code, e)
            errors.append(ErrorEntry(
                level=ErrorLevel.ERROR,
                stage="ingest",
                message=f"{sport.code}: {e}",
            ))
            pairs = []

        stats_fn = getattr(sport, "last_ingest_stats", None)
        stats: IngestStats | None = stats_fn() if callable(stats_fn) else None
        if stats is not None:
            if stats.raw_events is not None:
                raw_events_total += stats.raw_events
            if stats.after_filter is not None:
                after_filter_total += stats.after_filter
            priced_total += stats.priced
            sources_all.extend(stats.sources)
            if priced_note is None and stats.priced_note:
                priced_note = stats.priced_note
        else:
            # Sport doesn't surface stats — at minimum we know how many
            # priced pairs came back, so the funnel isn't empty.
            priced_total += len(pairs)

        log.info("got %d priced fixtures for %s", len(pairs), sport.code)
        if not pairs:
            written[sport.code] = []
            continue

        matches: list[MatchOutput] = []
        paths: list[Path] = []
        now = datetime.now(tz=timezone.utc)

        signals_runtime = signals_runtime_factory(sport, now=now)
        signals_ctx = signals_runtime if signals_runtime is not None else _NullCtx()

        # `signal_impact_snap` is filled inside the `with` (cache open)
        # and consumed outside (cache closed). Initialise to [] so the
        # later append is unconditional.
        signal_impact_snap: list[SignalImpactRow] = []
        with signals_ctx:
            for fx, snapshot in pairs:
                copy = None
                try:
                    if hasattr(sport, "decide_and_explain"):
                        # Pass the signals runtime through (PR F). Sports
                        # that don't accept the kwarg silently ignore it,
                        # but FootballSport uses it to apply bounded
                        # hard-signal Elo adjustments before the model.
                        try:
                            result = sport.decide_and_explain(
                                fx, snapshot, signals_runtime=signals_runtime,
                            )
                        except TypeError:
                            result = sport.decide_and_explain(fx, snapshot)
                        # PR 2: decide_and_explain may return (v, copy) or
                        # (v, copy, DecisionMeta). Forced-pass counts come
                        # from the meta — older sports without it just don't
                        # populate the breakdown.
                        if len(result) == 3:
                            v, copy, meta = result
                            if meta is not None and meta.forced_pass_reason == "illiquid":
                                n_illiquid += 1
                            elif meta is not None and meta.forced_pass_reason == "stub_elo":
                                n_stub_elo += 1
                        else:
                            v, copy = result
                    else:
                        v = sport.decide(fx, snapshot)
                except Exception as e:                      # noqa: BLE001
                    log.warning("decide failed for %s: %s", fx.match_id, e)
                    errors.append(ErrorEntry(
                        level=ErrorLevel.WARN, stage="decide",
                        message=f"{fx.match_id}: {e}",
                    ))
                    v = Verdict(state=VerdictState.PASS)
                try:
                    m = _build_match(fx, verdict=v, now=now, copy=copy)
                except Exception as e:                      # noqa: BLE001
                    log.warning("build_match failed for %s: %s", fx.match_id, e)
                    errors.append(ErrorEntry(
                        level=ErrorLevel.WARN, stage="build_match",
                        message=f"{fx.match_id}: {e}",
                    ))
                    continue

                # Editorial citations now arrive populated on `m.copy`
                # from the sport adapter (FootballSport.decide_and_explain)
                # — and the templated blurb already saw them via build_copy
                # so the press-chorus sentence rides on the published prose.
                # See `desk/explainer/stub.py::_press_chorus`.

                try:
                    path, _ = pub.write_match(m)
                except Exception as e:                      # noqa: BLE001
                    log.warning("write_match failed for %s: %s", fx.match_id, e)
                    errors.append(ErrorEntry(
                        level=ErrorLevel.WARN, stage="publish",
                        message=f"{fx.match_id}: {e}",
                    ))
                    continue

                matches.append(m)
                paths.append(path)
                snapshot_rows.append(
                    fixture_row_from_match(m, venues=_venues_in(snapshot))
                )
                n_published += 1
                if v.state == VerdictState.PICK.value or v.state == VerdictState.PICK:
                    n_pick += 1
                elif v.state == VerdictState.AVOID.value or v.state == VerdictState.AVOID:
                    n_avoid += 1
                else:
                    n_pass += 1

            # Snapshot per-outlet status + this-run contribution counts
            # while the cache is still open. Failure here is a warning,
            # not fatal — the run report is still useful without the
            # news-signals panel.
            if signals_runtime is not None:
                try:
                    signal_impact_snap = signals_runtime.impact()
                except Exception as e:                      # noqa: BLE001
                    log.warning("signals impact snapshot failed: %s", e)

        signal_impact.extend(signal_impact_snap)

        if matches:
            idx_path, _ = pub.write_index(sport.code, matches)
            paths.append(idx_path)
        log.info("%s: %d pick / %d pass / %d avoid",
                 sport.code, n_pick, n_pass, n_avoid)
        written[sport.code] = paths

        # Post-decision: model-derived source rows (e.g. elo_seed K/N).
        # Optional per-sport — football wires it, other sports may not.
        model_sources_fn = getattr(sport, "last_model_sources", None)
        if callable(model_sources_fn):
            try:
                sources_all.extend(model_sources_fn())
            except Exception as e:                      # noqa: BLE001
                log.warning("last_model_sources failed for %s: %s", sport.code, e)

    # ── Assemble + persist the run report ──────────────────────────
    finished_at = datetime.now(tz=timezone.utc)
    forced_pass = ForcedPassCounts(illiquid=n_illiquid, stub_elo=n_stub_elo)
    funnel = [
        StageCount(stage="polymarket_events",        n=raw_events_total),
        StageCount(stage="after_competition_filter", n=after_filter_total),
        StageCount(stage="priced_fixtures",          n=priced_total, note=priced_note),
        StageCount(
            stage="verdict_eligible",
            n=max(0, priced_total - forced_pass.total()),
            note=_eligible_note(forced_pass) if forced_pass.total() else None,
        ),
        StageCount(stage="published",        n=n_published),
    ]
    status = _classify_status(
        sources=sources_all,
        errors=errors,
        n_published=n_published,
        any_sport_ran=any_sport_ran,
    )

    # PR 3: typed change events vs the previous run. First run ever
    # returns []. Failures here must not block persistence — the report
    # is still useful without the diff.
    run_id = run_id_for(started_at)
    changes_payload: list[dict] = []
    try:
        prev_snapshot = recorder.previous_snapshot(before_run_id=run_id)
        changes_payload = [
            c.to_dict() for c in diff_snapshots(prev_snapshot, snapshot_rows)
        ]
    except Exception as e:                              # noqa: BLE001
        log.warning("ops diff failed: %s", e)

    report = RunReport(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        duration_s=(finished_at - started_at).total_seconds(),
        trigger=trigger,
        status=status,
        competitions=_competitions_for_report(),
        funnel=funnel,
        forced_pass=forced_pass,
        verdicts=VerdictCounts(pick=n_pick, pass_=n_pass, avoid=n_avoid),
        sources=sources_all,
        errors=errors,
        changes=changes_payload,
        snapshot=snapshot_rows,
        signal_impact=signal_impact,
    )
    try:
        recorder.persist(report)
    except Exception as e:                              # noqa: BLE001
        log.warning("ops recorder persist failed: %s", e)

    return written


def _eligible_note(forced: ForcedPassCounts) -> str:
    """Annotation for the `verdict_eligible` funnel row when a gate fired.

    Names which sanity gate ate the fixtures so the operator doesn't
    have to cross-reference `forced_pass` separately.
    """
    parts: list[str] = []
    if forced.stub_elo:
        parts.append(f"−{forced.stub_elo} stub_elo")
    if forced.illiquid:
        parts.append(f"−{forced.illiquid} illiquid")
    return " · ".join(parts)
