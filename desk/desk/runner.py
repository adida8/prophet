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
from desk.distribute import (
    BodyTooLarge,
    DistributeConfig,
    Outbox,
    canonical_body,
    detect_withdrawn,
    enqueue_match,
    load_config as load_distribute_config,
    snapshot_prior_index,
)
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
    hard_signal_adjustments=None,
    market_sources=None,
    market_prices=None,
    consensus_fair=None,
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
    if market_sources:
        kwargs["market_sources"] = list(market_sources)
    if market_prices:
        kwargs["market_prices"] = list(market_prices)
    if consensus_fair:
        kwargs["consensus_fair"] = dict(consensus_fair)
    if hard_signal_adjustments:
        kwargs["hard_signal_adjustments"] = list(hard_signal_adjustments)
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

    # Distribute layer is push-side-effect only: when DESK_DISTRIBUTE_PUSH=0
    # (default) the call is a no-op. We hold one outbox handle for the
    # whole run so per-fixture enqueue doesn't re-open the SQLite file.
    distribute_cfg, distribute_outbox = _open_distribute()

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

    # api-football form-delta cache. If `desk fetch-rank-form` has been
    # run, this carries last-10 weighted points-per-game for every WC26
    # team and the features-builder threads it onto each fixture. With
    # the B.1 hook flag off (default), populated values are inert —
    # they're recorded so the forward-validation logger can score the
    # lever against the published verdicts.
    from desk.data.api_football import APIFootballRuntime, default_cache_path
    api_football_runtime: APIFootballRuntime | None = None
    if default_cache_path().exists():
        api_football_runtime = APIFootballRuntime()

    # Live-Elo runtime (Phase 1b). Reads eloratings.net + clubelo
    # values populated by `desk fetch-elo`. When the cache file
    # doesn't exist, the runtime falls back to the static seed for
    # every lookup — pre-Phase-1b behaviour is preserved byte-for-byte.
    from desk.data.elo import EloRuntime, default_cache_path as _elo_default_path
    elo_runtime: EloRuntime | None = None
    if _elo_default_path().exists():
        elo_runtime = EloRuntime()

    # Non-US pivot — odds-api cache (sportsbooks + exchange). When
    # `DESK_CROSS_VENUE_EDGE=1` and the cache file exists, the sport
    # adapter merges cached venues into each fixture's snapshot before
    # the verdict runs. With the cache missing the flag is a no-op.
    from desk.data.oddsapi import OddsAPICache, default_cache_path as _odds_default_path
    oddsapi_cache = None
    if config.CROSS_VENUE_EDGE_ENABLED and _odds_default_path().exists():
        try:
            oddsapi_cache = OddsAPICache(_odds_default_path())
        except Exception as e:                          # noqa: BLE001
            log.warning("odds-api cache open failed: %s", e)
            oddsapi_cache = None

    # Forward-validation logger (Phase B.1 Shadow). Open once per run
    # so per-fixture inserts don't re-open the sqlite file. The logger
    # writes BOTH the published prediction (residual off, today's path)
    # AND a shadow prediction (residual on, what would publish if the
    # flag were flipped). Comparing Brier scores across the two
    # columns at outcome resolution is what graduates the coupled unit
    # Shadow → Live per data-layer spec §5.
    from desk.verdict.forward_validation import (
        ForwardValidationLog, PredictionRow, default_log_path as _fv_default_path,
    )
    forward_validation_log: ForwardValidationLog | None = None
    if api_football_runtime is not None:
        try:
            forward_validation_log = ForwardValidationLog(_fv_default_path())
        except Exception as e:                          # noqa: BLE001
            log.warning("forward-validation log open failed: %s", e)
            forward_validation_log = None

    for sport in active_sports():
        any_sport_ran = True
        # Snapshot the prior per-sport index BEFORE write_index overwrites
        # it. Used after the loop to detect withdrawn match_ids — fixtures
        # that were in the prior index but aren't in this run's published set.
        prior_index_snap = snapshot_prior_index(pub, sport.code)
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

        # api-football coverage report (Phase 2 §3.3). Computed pre-
        # publish so we get an early WARN when a competition's alias
        # coverage falls below the floor. We don't BLOCK publication
        # in v1 — fixtures with absent form_delta still ship (zero
        # contribution per spec §3.6); but the warning is the
        # discipline gate that drives onboarding work for new comps.
        if api_football_runtime is not None and sport.code == "football":
            _emit_coverage_warnings(api_football_runtime, pairs=pairs)

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
                hard_adjustments = None
                market_sources = None
                market_prices = None
                consensus_fair_pkt = None
                try:
                    if hasattr(sport, "decide_and_explain"):
                        # Pass the signals runtime through (PR F). Sports
                        # that don't accept the kwarg silently ignore it,
                        # but FootballSport uses it to apply bounded
                        # hard-signal Elo adjustments before the model.
                        try:
                            result = sport.decide_and_explain(
                                fx, snapshot,
                                signals_runtime=signals_runtime,
                                api_football_runtime=api_football_runtime,
                                elo_runtime=elo_runtime,
                                oddsapi_cache=oddsapi_cache,
                            )
                        except TypeError:
                            # Older sport adapters may not accept all
                            # runtime kwargs. Fall back stepwise.
                            try:
                                result = sport.decide_and_explain(
                                    fx, snapshot,
                                    signals_runtime=signals_runtime,
                                    api_football_runtime=api_football_runtime,
                                    elo_runtime=elo_runtime,
                                )
                            except TypeError:
                                try:
                                    result = sport.decide_and_explain(
                                        fx, snapshot,
                                        signals_runtime=signals_runtime,
                                        api_football_runtime=api_football_runtime,
                                    )
                                except TypeError:
                                    try:
                                        result = sport.decide_and_explain(
                                            fx, snapshot, signals_runtime=signals_runtime,
                                        )
                                    except TypeError:
                                        result = sport.decide_and_explain(fx, snapshot)
                        # decide_and_explain may return (v, copy),
                        # (v, copy, DecisionMeta),
                        # (v, copy, DecisionMeta, hard_signal_adjustments),
                        # (v, ..., market_sources), or that plus the
                        # cross-venue (market_prices, consensus_fair).
                        # Older sports without the later slots leave
                        # them None.
                        if len(result) == 7:
                            (v, copy, meta, hard_adjustments,
                             market_sources, market_prices,
                             consensus_fair_pkt) = result
                        elif len(result) == 5:
                            v, copy, meta, hard_adjustments, market_sources = result
                        elif len(result) == 4:
                            v, copy, meta, hard_adjustments = result
                        elif len(result) == 3:
                            v, copy, meta = result
                        else:
                            v, copy = result
                            meta = None
                        if meta is not None and meta.forced_pass_reason == "illiquid":
                            n_illiquid += 1
                        elif meta is not None and meta.forced_pass_reason == "stub_elo":
                            n_stub_elo += 1
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
                    m = _build_match(
                        fx, verdict=v, now=now, copy=copy,
                        hard_signal_adjustments=hard_adjustments,
                        market_sources=market_sources,
                        market_prices=market_prices,
                        consensus_fair=consensus_fair_pkt,
                    )
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

                # Distribute: wire-equivalent of the disk write. Same
                # canonical bytes go to disk + outbox; the receiver dedupes
                # on (match_id, updated_at). No-op when push is disabled.
                _try_enqueue(m, cfg=distribute_cfg, outbox=distribute_outbox)

                # Forward-validation Shadow log. Dual prediction lives
                # on `sport._last_model_outputs[match_id]`; runner reads
                # + writes. Wrapped in try so a logger failure never
                # blocks the publish.
                if forward_validation_log is not None:
                    try:
                        _log_forward_validation(
                            forward_validation_log,
                            sport=sport, fx=fx, now=now,
                        )
                    except Exception as e:                  # noqa: BLE001
                        log.warning("forward-validation log failed for %s: %s",
                                    fx.match_id, e)

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

        # Withdrawn detection: any match_id in the prior index that didn't
        # publish this run. Writes a final withdrawn JSON to disk (NOT
        # added to the index — the index reflects live fixtures only) and
        # enqueues it. Single-shot: next run's prior_index won't carry it.
        try:
            published_ids = [m.match_id for m in matches]
            withdrawn_matches = detect_withdrawn(
                sport=sport.code,
                publisher=pub,
                prior_index=prior_index_snap,
                current_match_ids=published_ids,
                now=now,
            )
            for wm in withdrawn_matches:
                _try_enqueue(wm, cfg=distribute_cfg, outbox=distribute_outbox)
                n_published += 1
        except Exception as e:                              # noqa: BLE001
            log.warning("withdrawn detection failed for %s: %s", sport.code, e)

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

    if distribute_outbox is not None:
        try:
            distribute_outbox.close()
        except Exception as e:                          # noqa: BLE001
            log.warning("distribute outbox close failed: %s", e)

    if api_football_runtime is not None:
        try:
            api_football_runtime.close()
        except Exception as e:                          # noqa: BLE001
            log.warning("api-football runtime close failed: %s", e)

    if elo_runtime is not None:
        try:
            elo_runtime.close()
        except Exception as e:                          # noqa: BLE001
            log.warning("elo runtime close failed: %s", e)

    if forward_validation_log is not None:
        try:
            forward_validation_log.close()
        except Exception as e:                          # noqa: BLE001
            log.warning("forward-validation log close failed: %s", e)

    if oddsapi_cache is not None:
        try:
            oddsapi_cache.close()
        except Exception as e:                          # noqa: BLE001
            log.warning("odds-api cache close failed: %s", e)

    return written


def _emit_coverage_warnings(runtime, *, pairs) -> None:
    """Build a per-competition coverage report for the priced fixture
    set and WARN when either floor isn't cleared. No-op when the cache
    isn't open. Wrapped in try so a coverage failure never blocks the
    publish."""
    try:
        cache = runtime._ensure()
        if cache is None:
            return
        from desk.data.api_football.coverage import build_coverage_report
        from desk.sports.football.teams import iso3_for_name

        # Group fixtures by competition_code so each competition gets
        # its own report — onboarding decisions are per-competition.
        by_comp: dict[str, list[tuple[str, str, str]]] = {}
        for fx, _snapshot in pairs:
            iso_a = (iso3_for_name(fx.team_a) or "").lower()
            iso_b = (iso3_for_name(fx.team_b) or "").lower()
            by_comp.setdefault(fx.competition_code, []).append(
                (fx.match_id, iso_a, iso_b)
            )

        for comp, triples in by_comp.items():
            report = build_coverage_report(
                cache=cache,
                competition_code=comp,
                priced_fixture_iso3_pairs=triples,
            )
            if report.fixtures_total == 0:
                # Non-WC26 competition (clubs, friendlies); registry
                # doesn't cover it, so no coverage to report.
                continue
            level = "info" if report.both_floors_cleared else "warning"
            getattr(log, level)("%s", report.headline())
            if not report.both_floors_cleared and report.teams_uncovered:
                log.warning(
                    "uncovered teams (first 10): %s",
                    ", ".join(report.teams_uncovered[:10]),
                )
    except Exception as e:                                  # noqa: BLE001
        log.warning("coverage report failed: %s", e)


def _log_forward_validation(
    log_handle, *, sport, fx, now: datetime,
) -> None:
    """Append one PredictionRow per fixture, only when residual data
    actually changed the prediction. Reads dual outputs from
    `sport._last_model_outputs[fx.match_id]`."""
    import json

    from desk.verdict.forward_validation import PredictionRow

    outputs = getattr(sport, "_last_model_outputs", {}).get(fx.match_id)
    features = getattr(sport, "_last_features", {}).get(fx.match_id)
    if outputs is None or features is None:
        return
    published, shadow = outputs
    # Skip when the residual didn't move anything — saves disk + keeps
    # the table focused on rows where we actually have something to
    # measure.
    if (published.p_a == shadow.p_a
            and published.p_draw == shadow.p_draw
            and published.p_b == shadow.p_b):
        return
    feature_payload = {
        "team_a_form_delta":  features.team_a_form_delta,
        "team_b_form_delta":  features.team_b_form_delta,
        "team_a_rank_residual": features.team_a_rank_residual,
        "team_b_rank_residual": features.team_b_rank_residual,
        "team_a_elo": features.team_a_elo,
        "team_b_elo": features.team_b_elo,
    }
    asof_iso = now.replace(microsecond=0).isoformat()
    log_handle.log_prediction(PredictionRow(
        match_id=fx.match_id,
        asof_iso=asof_iso,
        phase="B.1.form",
        p_a_without_residual=published.p_a,
        p_draw_without_residual=published.p_draw,
        p_b_without_residual=published.p_b,
        p_a_with_residual=shadow.p_a,
        p_draw_with_residual=shadow.p_draw,
        p_b_with_residual=shadow.p_b,
        feature_set=json.dumps(feature_payload, sort_keys=True),
        logged_at=datetime.now(tz=timezone.utc).isoformat(),
    ))


def _open_distribute() -> tuple[DistributeConfig | None, Outbox | None]:
    """Resolve distribute config + open the outbox if push is enabled.

    Returns (None, None) when the config can't be loaded (e.g. push=1
    without URL/secret). The runner logs and continues — disk writes
    are decoupled from the wire.
    """
    try:
        cfg = load_distribute_config()
    except ValueError as e:
        log.warning("distribute config invalid, push disabled this run: %s", e)
        return None, None
    if not cfg.push_enabled:
        return cfg, None
    try:
        return cfg, Outbox(cfg.db_path)
    except Exception as e:                                  # noqa: BLE001
        log.warning("distribute outbox open failed, push disabled: %s", e)
        return cfg, None


def _try_enqueue(
    match: MatchOutput,
    *,
    cfg: DistributeConfig | None,
    outbox: Outbox | None,
    body: bytes | None = None,
) -> None:
    """Best-effort enqueue. Never raises — the on-disk write is the
    canonical receipt, the wire is a secondary delivery channel."""
    if cfg is None or outbox is None or not cfg.push_enabled:
        return
    try:
        enqueue_match(match, config=cfg, outbox=outbox, body=body)
    except BodyTooLarge as e:
        log.error("distribute enqueue rejected (oversized): %s", e)
    except Exception as e:                                  # noqa: BLE001
        log.warning("distribute enqueue failed for %s: %s", match.match_id, e)


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
