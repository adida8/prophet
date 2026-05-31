"""`desk` CLI.

Sub-commands:
    desk run [--once]                     Run the engine. v1: --once only (PR 6 adds the loop).
    desk sports                           List registered sports.
    desk match <id>                       Print the current published JSON for one match.
    desk backtest --tournament wc-2022    Replay the engine across a historical tournament.
    desk replay <id>                      PR 6+ — placeholder for as-of replay from snapshots.

Designed to be runnable two ways during development:
    python -m desk        # via the package
    desk                  # via the project.scripts entry point
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from desk import config
from desk.publish import Publisher
from desk.runner import run_once
from desk.sports import SPORT_REGISTRY


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(name)-32s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # httpx INFO-level logs every request URL including query params,
    # which leaks any key passed as a query string (e.g. OpenWeatherMap's
    # `appid`). Squelch to WARNING unless --verbose is on — operators
    # opt into the leak when they're debugging, not by default.
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


def _cmd_run(args: argparse.Namespace) -> int:
    if not args.once:
        print("desk run currently supports only --once (PR 6 adds the loop)", file=sys.stderr)
        return 2
    written = run_once(output_dir=Path(args.output_dir) if args.output_dir else None)
    total = sum(len(v) for v in written.values())
    print(f"wrote {total} files across {len(written)} sport(s)")
    for sport, paths in written.items():
        print(f"  {sport}: {len(paths)} file(s)")

    if not args.skip_outrights:
        from desk.outrights.run import run_once as run_outrights_once
        out_root = Path(args.output_dir) if args.output_dir else None
        out_dir = (out_root / "outrights") if out_root else None
        try:
            path = run_outrights_once(out_dir=out_dir)
            print(f"outrights: wrote {path}")
        except Exception as e:  # noqa: BLE001 — never break matches if outrights fail
            print(f"outrights: skipped — {e}", file=sys.stderr)
    return 0


def _cmd_outrights(args: argparse.Namespace) -> int:
    from desk.outrights.run import run_once as run_outrights_once
    out_dir = Path(args.output_dir) / "outrights" if args.output_dir else None
    path = run_outrights_once(
        sims=args.sims,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_sims=args.bootstrap_sims,
        seed=args.seed,
        out_dir=out_dir,
    )
    print(f"outrights: wrote {path}")
    return 0


def _cmd_sports(_: argparse.Namespace) -> int:
    for code, sport in SPORT_REGISTRY.items():
        print(f"{code}\t{sport.short_code}\t{sport.label}")
    return 0


def _cmd_match(args: argparse.Namespace) -> int:
    pub = Publisher(output_dir=Path(args.output_dir) if args.output_dir else config.OUTPUT_DIR)
    sport = args.match_id.split("-", 1)[0]
    sport = "football" if sport == "fb" else sport
    try:
        m = pub.read_match(sport, args.match_id)
    except FileNotFoundError:
        print(f"no published JSON for {args.match_id}", file=sys.stderr)
        return 1
    print(json.dumps(m.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    print("desk replay is a PR 6 placeholder — coming with the scheduler", file=sys.stderr)
    return 2


def _cmd_fetch_signals(args: argparse.Namespace) -> int:
    """Fetch the trusted-core sources into the signals cache.

    Read-only against the engine — does nothing to /api/desk/* output.
    Useful for poking at what the registry actually pulls down. Long-
    tail aggregators (GDELT) are off by default since they hit external
    APIs whose query has to be tuned per use case; opt in with
    `--include-long-tail`.
    """
    from desk.signals.cache import SignalsCache
    from desk.signals.fetch import fetch_all
    from desk.signals.registry import Registry

    reg = Registry.from_csv()
    from desk.signals.runtime import default_cache_path
    db_path = Path(args.db) if args.db else default_cache_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tiers: tuple[str, ...] = ("trusted_core",)
    if args.include_long_tail:
        tiers = tiers + ("long_tail",)
    with SignalsCache(db_path) as cache:
        outcomes = fetch_all(reg, cache, tiers=tiers)

    totals = {"new": 0, "changed": 0, "unchanged": 0}
    for o in outcomes:
        totals["new"]       += o.new
        totals["changed"]   += o.changed
        totals["unchanged"] += o.unchanged
        suffix = f"  err={o.error}" if o.error else ""
        print(
            f"  {o.source_id:28s}  {o.status:14s}  "
            f"new={o.new:3d}  changed={o.changed:3d}  unchanged={o.unchanged:3d}{suffix}"
        )
    print()
    print(f"  totals: new={totals['new']}  changed={totals['changed']}  "
          f"unchanged={totals['unchanged']}  (db: {db_path})")
    return 0


def _cmd_extract_signals(args: argparse.Namespace) -> int:
    """Run the LLM extractor across the signals cache. Idempotent — items
    we've already extracted (at the same content_hash) are skipped."""
    import os

    from desk.signals.cache import SignalsCache
    from desk.signals.extract import AnthropicExtractor, extract_all

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    from desk.signals.runtime import default_cache_path
    db_path = Path(args.db) if args.db else default_cache_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    extractor = AnthropicExtractor(model=args.model)
    with SignalsCache(db_path) as cache:
        outcomes = extract_all(
            cache,
            extractor=extractor,
            source_ids=set(args.source) if args.source else None,
            limit_per_source=args.limit,
        )

    counts: dict[str, int] = {}
    new = 0
    for o in outcomes:
        counts[o.status] = counts.get(o.status, 0) + 1
        new += o.new_signals
    for status, n in sorted(counts.items()):
        print(f"  {status:18s}  {n}")
    print()
    print(f"  signals written: {new}  (db: {db_path})")
    return 0


def _cmd_distribute_drain(args: argparse.Namespace) -> int:
    """Single-sweep drainer for the MTA push outbox.

    Designed to be called repeatedly (e.g. every 30s by the
    project-root async loop). Exits cleanly when push is disabled so a
    cron-style caller can fire it unconditionally without an env check.
    """
    import asyncio

    from desk.distribute import Outbox, drain_once, load_config
    from desk.distribute.client import MTAClient

    try:
        cfg = load_config()
    except ValueError as e:
        print(f"distribute-drain: {e}", file=sys.stderr)
        return 2

    if not cfg.push_enabled:
        print("distribute-drain: DESK_DISTRIBUTE_PUSH=0 — nothing to do")
        return 0

    async def _run() -> int:
        assert cfg.webhook_url and cfg.webhook_secret  # load_config guarantees
        client = MTAClient(
            webhook_url=cfg.webhook_url,
            webhook_secret=cfg.webhook_secret,
        )
        try:
            with Outbox(cfg.db_path) as ob:
                pending_before = ob.pending_count()
                dead_before    = ob.dead_count()
                stats = await drain_once(
                    ob, client,
                    max_in_flight=cfg.max_in_flight,
                    rate_per_min=cfg.rate_per_min,
                )
                pending_after = ob.pending_count()
                dead_after    = ob.dead_count()
        finally:
            await client.aclose()

        print(
            f"distribute-drain: claimed={stats.claimed} sent={stats.sent} "
            f"retried={stats.retried} dead={stats.dead} "
            f"(pending {pending_before}→{pending_after}, "
            f"dead {dead_before}→{dead_after})"
        )
        if stats.errors_by_kind:
            kinds = " ".join(f"{k}={v}" for k, v in sorted(stats.errors_by_kind.items()))
            print(f"  errors: {kinds}")
        return 0

    return asyncio.run(_run())


def _cmd_signals_validate(args: argparse.Namespace) -> int:
    """Load + report on the source seed.

    Catches malformed seeds before they reach the fetcher / explainer.
    Prints one line per source with its trust-gate verdict and a
    summary so the operator can eyeball the registry shape.
    """
    from desk.signals.registry import DEFAULT_SEED_PATH, Registry
    from desk.signals.resolve import sources_for

    seed_path = Path(args.seed) if args.seed else DEFAULT_SEED_PATH
    try:
        reg = Registry.from_csv(seed_path)
    except (ValueError, FileNotFoundError) as e:
        print(f"validate: {e}", file=sys.stderr)
        return 2

    enabled       = reg.enabled()
    model_eligible = [s for s in enabled if s.can_feed_model]
    editorial      = [s for s in enabled if s.editorial_only]
    by_feed_type:  dict[str, int] = {}
    for s in enabled:
        by_feed_type[s.feed_type] = by_feed_type.get(s.feed_type, 0) + 1

    print(f"seed: {seed_path}")
    print(f"  rows: {len(reg.all())}  enabled: {len(enabled)}  "
          f"disabled: {len(reg.all()) - len(enabled)}")
    print(f"  can_feed_model: {len(model_eligible)}  "
          f"editorial_only: {len(editorial)}")
    print(f"  by feed_type: " + ", ".join(
        f"{ft}={n}" for ft, n in sorted(by_feed_type.items())
    ))
    print()
    print(f"  {'id':24s} {'feed_type':11s} {'rel':>5s}  bias       tier         gate")
    for s in reg.all():
        gate = "model" if s.can_feed_model else "editorial-only"
        enabled_mark = " " if s.enabled else "X"
        print(f"  {enabled_mark} {s.id:22s} {s.feed_type:11s} "
              f"{s.reliability:>5.2f}  {s.bias_flag:9s}  "
              f"{s.tier:11s}  {gate}")

    # Smoke the resolver on the most common tag set so a regression in
    # tag intersection at least one row off the seed gets caught here.
    if args.resolve:
        tags = set(args.resolve.split(","))
        print()
        print(f"resolve {sorted(tags)}: {len(sources_for(tags, reg))} match(es)")
    return 0


def _cmd_fetch_rank_form(args: argparse.Namespace) -> int:
    """Refresh api-football form_delta values for every WC26 team.

    Per-team cost: 1 call to `/teams?search=` on first run (cached
    forever), 1 call to `/fixtures?team=...&last=10` per run. Across
    ~70 WC26 teams that's ≈70 calls/day — well under api-football
    Pro's 7,500/day cap.

    Designed to be idempotent and rerunnable: on retry, cached team_ids
    skip the resolution call, and the fixtures upsert is keyed on
    (team_id, fixture_id) so re-fetching the same window is a no-op.
    """
    import asyncio

    from desk import config

    if not config.API_FOOTBALL_KEY:
        print("API_FOOTBALL_KEY not set — see .env.example", file=sys.stderr)
        return 2

    from desk.data.api_football import (
        APIFootballCache, APIFootballClient, default_cache_path, refresh_all,
    )

    db_path = Path(args.db) if args.db else default_cache_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    iso3s = args.iso3 or None

    async def _run() -> tuple[int, list, int]:
        async with APIFootballClient(config.API_FOOTBALL_KEY) as client:
            with APIFootballCache(db_path) as cache:
                outcomes = await refresh_all(
                    client=client, cache=cache, iso3s=iso3s,
                )
        # Sum the surface-level counters the caller cares about.
        ok = sum(1 for o in outcomes if o.status in ("ok", "resolved_then_ok"))
        return ok, outcomes, len(outcomes)

    ok, outcomes, total = asyncio.run(_run())

    by_status: dict[str, int] = {}
    for o in outcomes:
        by_status[o.status] = by_status.get(o.status, 0) + 1
        if o.error:
            print(f"  {o.iso3:5s}  {o.status:18s}  err={o.error}")
        else:
            fd = (f"form_delta={o.form_delta:+.3f}"
                  if o.form_delta is not None else "(no form_delta)")
            print(f"  {o.iso3:5s}  {o.status:18s}  team_id={o.team_id}  "
                  f"sample={o.sample_size:2d}  {fd}")
    print()
    for status, n in sorted(by_status.items()):
        print(f"  {status:18s}  {n}")
    print()
    print(f"  total: {total}  ok: {ok}  (db: {db_path})")
    return 0 if ok > 0 else 2


def _cmd_schedule(args: argparse.Namespace) -> int:
    """Run the refresh loop (PR 6).

    Folds the project-root `desk_refresh_loop.py` into the unified
    `desk` CLI surface. Same control file (Ops dashboard
    `/desk/ops/admin`), same env-var-gated steps (fetch-signals /
    extract-signals / fetch-rank-form / fetch-injuries / fetch-elo /
    fv-ingest-outcomes), same cost ledger and tick-totals.

    `--once` runs a single tick and exits — useful for cron-style
    invocations + smoke tests. Without `--once` the loop runs forever,
    sleeping until each scheduled UTC hour.
    """
    import asyncio
    import importlib.util
    import os

    # Find the loop script — sits at the project root, two levels up
    # from desk/desk/cli.py.
    here = Path(__file__).resolve()
    project_root = here.parents[2]
    loop_path = project_root / "desk_refresh_loop.py"
    if not loop_path.exists():
        print(f"desk_refresh_loop.py not found at {loop_path}",
              file=sys.stderr)
        return 2

    spec = importlib.util.spec_from_file_location(
        "desk_refresh_loop", str(loop_path),
    )
    assert spec is not None and spec.loader is not None
    loop_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loop_mod)

    if args.once:
        # _tick is the per-iteration body that the loop calls inside
        # its sleep cycle. Run it once + exit.
        loop_mod._tick()
        return 0

    # Multi-iteration mode — defer to the loop's existing async
    # entry-point. It honours the control file + the autorun env.
    return asyncio.run(loop_mod.run_desk_loop()) or 0


def _cmd_b3_audit(args: argparse.Namespace) -> int:
    """Run the Phase B.3 source audit against api-football.

    Probes a fixed set of cached team_ids, hits /injuries for each,
    measures coverage_rate + has_position_rate + has_type_rate per
    spec §5 Phase 4. Operator reads the headline to decide whether
    to flip DESK_INJURY_FETCH=1.

    Spends ~N api-football calls (N = number of probed teams). Default
    probes 8 teams ≈ 8 calls, well within the daily Pro cap.
    """
    import asyncio

    from desk import config
    from desk.data.api_football import APIFootballCache
    from desk.data.api_football.client import APIFootballClient
    from desk.data.api_football.injuries import run_source_audit
    from desk.data.api_football.runtime import default_cache_path

    if not config.API_FOOTBALL_KEY:
        print("API_FOOTBALL_KEY not set", file=sys.stderr)
        return 2

    db_path = Path(args.af_db) if args.af_db else default_cache_path()
    if not db_path.exists():
        print(f"api-football cache not found at {db_path}", file=sys.stderr)
        return 2

    iso3s = args.iso3 or ["fra", "bra", "mex", "eng", "esp", "arg", "ger", "ita"]

    async def _run():
        async with APIFootballClient(config.API_FOOTBALL_KEY) as client:
            with APIFootballCache(db_path) as cache:
                team_ids: list[int] = []
                for iso3 in iso3s:
                    tid = cache.team_id_for_iso3(iso3)
                    if tid is None:
                        print(f"  skip {iso3}: not in team_resolution cache",
                              file=sys.stderr)
                        continue
                    team_ids.append(tid)
                if not team_ids:
                    print("no probed teams resolved", file=sys.stderr)
                    return None
                return await run_source_audit(
                    team_ids, season=args.season, client=client,
                )

    audit = asyncio.run(_run())
    if audit is None:
        return 2
    print()
    print(audit.headline())
    print(f"  probed team_ids: {list(audit.probed_team_ids)}")
    print(f"  rows seen:       {audit.rows_total}")
    return 0 if audit.passes else 1


def _cmd_fetch_injuries(args: argparse.Namespace) -> int:
    """Refresh api-football injuries cache + recompute per-team Elo
    penalty. Mirror of `desk fetch-rank-form` shape — same auth /
    abort discipline, same writes to the api-football sqlite."""
    import asyncio

    from desk import config
    from desk.data.api_football import APIFootballCache
    from desk.data.api_football.client import APIFootballClient
    from desk.data.api_football.injuries_refresh import refresh_injuries_all
    from desk.data.api_football.runtime import default_cache_path

    if not config.API_FOOTBALL_KEY:
        print("API_FOOTBALL_KEY not set", file=sys.stderr)
        return 2

    db_path = Path(args.db) if args.db else default_cache_path()

    async def _run():
        async with APIFootballClient(config.API_FOOTBALL_KEY) as client:
            with APIFootballCache(db_path) as cache:
                return await refresh_injuries_all(
                    season=args.season, client=client, cache=cache,
                    iso3s=args.iso3 or None,
                )

    outcomes = asyncio.run(_run())
    by_status: dict[str, int] = {}
    for o in outcomes:
        by_status[o.status] = by_status.get(o.status, 0) + 1
        if o.error:
            print(f"  {o.iso3:5s}  {o.status:14s}  err={o.error}")
        else:
            print(f"  {o.iso3:5s}  {o.status:14s}  "
                  f"team_id={o.team_id}  n={o.n_players}  "
                  f"penalty={o.elo_penalty:.1f}")
    print()
    for status, n in sorted(by_status.items()):
        print(f"  {status:14s}  {n}")
    print()
    print(f"  total: {len(outcomes)}  (db: {db_path})")
    n_ok = by_status.get("ok", 0)
    return 0 if n_ok > 0 else 2


def _cmd_fetch_cards(args: argparse.Namespace) -> int:
    """Refresh api-football card accumulation per team (Q5 of the
    squad-paragraph spec).

    Calls `/players?team=&season=&league=` once per WC26 team and
    derives `at_risk = (yellows == threshold-1)` per spec §Q1. Drops
    any player already suspended from the at-risk set (suspension is
    the confirmed absence; we'd never name the same player twice).
    """
    import asyncio

    from desk import config
    from desk.data.api_football import APIFootballCache
    from desk.data.api_football.client import APIFootballClient
    from desk.data.api_football.cards_refresh import refresh_cards_all
    from desk.data.api_football.runtime import default_cache_path

    if not config.API_FOOTBALL_KEY:
        print("API_FOOTBALL_KEY not set", file=sys.stderr)
        return 2

    db_path = Path(args.db) if args.db else default_cache_path()

    async def _run():
        async with APIFootballClient(config.API_FOOTBALL_KEY) as client:
            with APIFootballCache(db_path) as cache:
                return await refresh_cards_all(
                    season=args.season,
                    competition=args.competition,
                    client=client, cache=cache,
                    iso3s=args.iso3 or None,
                )

    outcomes = asyncio.run(_run())
    by_status: dict[str, int] = {}
    for o in outcomes:
        by_status[o.status] = by_status.get(o.status, 0) + 1
        if o.error:
            print(f"  {o.iso3:5s}  {o.status:14s}  err={o.error}")
        else:
            print(f"  {o.iso3:5s}  {o.status:14s}  "
                  f"team_id={o.team_id}  rows={o.n_rows:2d}  "
                  f"at_risk={o.n_at_risk}")
    print()
    for status, n in sorted(by_status.items()):
        print(f"  {status:14s}  {n}")
    print()
    print(f"  total: {len(outcomes)}  competition: {args.competition}  "
          f"(db: {db_path})")
    n_ok = by_status.get("ok", 0)
    return 0 if n_ok > 0 else 2


def _cmd_fetch_lineups(args: argparse.Namespace) -> int:
    """Refresh api-football /fixtures/lineups for priced fixtures whose
    kickoff lands inside a window from now.

    Two callers:
      * daily refresh tick — `--window-hours 24` (default)
      * T-90m polling loop — `--window-hours 2`

    Builds the target list from the live football priced-fixture pool
    so we never fetch lineups for matches the engine isn't publishing.
    Cost: 1 call to /fixtures (cached forever per match) + 1 call to
    /fixtures/lineups per fixture. Well under Pro-tier 7,500/day even
    at the tightest loop cadence.
    """
    import asyncio

    from desk import config
    from desk.data.api_football import APIFootballCache
    from desk.data.api_football.client import APIFootballClient
    from desk.data.api_football.lineups_refresh import (
        LineupRefreshTarget, fixtures_in_window, refresh_lineups_for_targets,
    )
    from desk.data.api_football.runtime import default_cache_path
    from desk.sports.football.fixtures import list_priced_football_fixtures
    from desk.sports.football.teams import iso3_for_name

    if not config.API_FOOTBALL_KEY:
        print("API_FOOTBALL_KEY not set", file=sys.stderr)
        return 2

    db_path = Path(args.db) if args.db else default_cache_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async def _gather_targets() -> list[LineupRefreshTarget]:
        targets: list[LineupRefreshTarget] = []
        # `list_priced_football_fixtures()` is async; awaitable here.
        fixtures = await list_priced_football_fixtures()
        for fx in fixtures:
            home_iso3 = iso3_for_name(fx.team_a)
            away_iso3 = iso3_for_name(fx.team_b)
            if not home_iso3 or not away_iso3:
                continue
            targets.append(LineupRefreshTarget(
                match_id=fx.match_id,
                home_iso3=home_iso3,
                away_iso3=away_iso3,
                kickoff_utc=fx.kickoff_utc,
            ))
        return targets

    async def _run():
        targets = await _gather_targets()
        scoped = fixtures_in_window(targets, window_hours=args.window_hours)
        if args.match_id:
            wanted = set(args.match_id)
            scoped = [t for t in scoped if t.match_id in wanted]
        if not scoped:
            return [], 0
        async with APIFootballClient(config.API_FOOTBALL_KEY) as client:
            with APIFootballCache(db_path) as cache:
                outcomes = await refresh_lineups_for_targets(
                    scoped, season=args.season,
                    client=client, cache=cache,
                )
        return outcomes, len(scoped)

    outcomes, n_targets = asyncio.run(_run())
    by_status: dict[str, int] = {}
    for o in outcomes:
        by_status[o.status] = by_status.get(o.status, 0) + 1
        suffix = ""
        if o.home_lineup is not None:
            suffix += f"  home={o.home_lineup.state}/{len(o.home_lineup.starters)}"
        if o.away_lineup is not None:
            suffix += f"  away={o.away_lineup.state}/{len(o.away_lineup.starters)}"
        if o.error:
            suffix += f"  err={o.error}"
        print(f"  {o.match_id:42s}  {o.status:18s}{suffix}")
    print()
    for status, n in sorted(by_status.items()):
        print(f"  {status:18s}  {n}")
    print()
    print(f"  targets: {n_targets}  attempted: {len(outcomes)}  (db: {db_path})")
    n_ok = by_status.get("ok", 0)
    return 0 if n_targets == 0 or n_ok > 0 else 2


def _cmd_fetch_elo(args: argparse.Namespace) -> int:
    """Refresh live Elo values (national + club) into the cache.

    No external API key needed — both providers are free:
      * eloratings.net  — World.tsv (parser-hardened; bad parse keeps last-good)
      * api.clubelo.com — per-club CSV (top-5 league + WC26 club starter set)

    Default behaviour fetches both; --skip-national / --skip-club let
    you scope the refresh during smoke tests.
    """
    import asyncio

    from desk.data.elo import EloCache, default_cache_path

    db_path = Path(args.db) if args.db else default_cache_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async def _run() -> tuple[int, int, int, int]:
        n_nat = n_club_ok = n_club_skipped = n_club_err = 0
        with EloCache(db_path) as cache:
            if not args.skip_national:
                from desk.data.elo.eloratings import refresh_nationals
                parsed = await refresh_nationals(cache=cache)
                if parsed.ok:
                    n_nat = len(parsed.rows)
                    print(f"  eloratings · ok · wrote {n_nat} nationals")
                else:
                    print(f"  eloratings · FAIL · {parsed.error}",
                          file=sys.stderr)
            if not args.skip_club:
                from desk.data.elo.clubelo import (
                    CLUB_ID_TO_CLUBELO_NAME, refresh_clubs,
                )
                club_ids = args.club or list(CLUB_ID_TO_CLUBELO_NAME)
                outcomes = await refresh_clubs(club_ids, cache=cache)
                for o in outcomes:
                    if o.status == "ok":
                        n_club_ok += 1
                        print(f"  clubelo · {o.club_id:18s}  ok  "
                              f"elo={o.elo:.1f}  rows={o.rows_parsed}")
                    elif o.status == "no_history":
                        n_club_skipped += 1
                    else:
                        n_club_err += 1
                        print(f"  clubelo · {o.club_id:18s}  {o.status}  "
                              f"{o.error or ''}", file=sys.stderr)
        return n_nat, n_club_ok, n_club_skipped, n_club_err

    n_nat, n_ok, n_skip, n_err = asyncio.run(_run())
    print()
    print(f"  totals: nationals={n_nat}  "
          f"clubs ok={n_ok} skipped={n_skip} err={n_err}  "
          f"(db: {db_path})")
    return 0 if (n_nat > 0 or n_ok > 0) else 2


def _cmd_fv_ingest_outcomes(args: argparse.Namespace) -> int:
    """Ingest resolved match outcomes into forward_validation.db.

    Reads pending match_ids (predictions logged, no outcome yet),
    hits api-football for each, writes (match_id, outcome) when the
    fixture has settled. Idempotent — already-resolved matches skip
    the network entirely.
    """
    import asyncio

    from desk import config
    from desk.data.api_football import APIFootballCache
    from desk.data.api_football.client import APIFootballClient
    from desk.data.api_football.runtime import default_cache_path as af_default
    from desk.verdict.forward_validation import (
        ForwardValidationLog, default_log_path as fv_default,
    )
    from desk.verdict.outcomes_ingest import ingest_pending

    if not config.API_FOOTBALL_KEY:
        print("API_FOOTBALL_KEY not set — see .env.example", file=sys.stderr)
        return 2

    fv_path = Path(args.fv_db) if args.fv_db else fv_default()
    af_path = Path(args.af_db) if args.af_db else af_default()
    if not fv_path.exists():
        print(f"forward-validation db not found at {fv_path}", file=sys.stderr)
        return 2
    if not af_path.exists():
        print(f"api-football cache not found at {af_path}", file=sys.stderr)
        return 2

    async def _run():
        async with APIFootballClient(config.API_FOOTBALL_KEY) as client:
            with APIFootballCache(af_path) as af_cache, \
                 ForwardValidationLog(fv_path) as fv_log:
                pending = fv_log.pending_match_ids()
                if args.limit is not None:
                    pending = pending[: args.limit]
                outcomes = await ingest_pending(
                    pending, client=client, af_cache=af_cache,
                )
                n_ok = 0
                for o in outcomes:
                    if o.status == "ok" and o.outcome:
                        fv_log.record_outcome(o.match_id, o.outcome)
                        n_ok += 1
                return n_ok, outcomes

    n_ok, outcomes = asyncio.run(_run())
    by_status: dict[str, int] = {}
    for o in outcomes:
        by_status[o.status] = by_status.get(o.status, 0) + 1
        if o.status == "ok":
            print(f"  {o.match_id:42s}  resolved → {o.outcome}")
        else:
            print(f"  {o.match_id:42s}  {o.status:22s}  {o.error or ''}")
    print()
    for status, n in sorted(by_status.items()):
        print(f"  {status:22s}  {n}")
    print()
    print(f"  resolved this run: {n_ok}")
    return 0


def _cmd_fv_report(args: argparse.Namespace) -> int:
    """Forward-validation calibration report (Phase B.1).

    Joins resolved predictions × outcomes from `forward_validation.db`
    and reports:
      * mean Brier without_residual vs with_residual
      * Brier delta + §1.4 gate verdict
      * directional sanity check
      * reliability-bin breakdown for the with-residual probabilities
        on the team_a side (diagnostic)
    Exits 0 if the gate clears, 1 if not yet (sample too small or
    Brier regressed).
    """
    from desk.verdict.forward_validation import (
        ForwardValidationLog, default_log_path as fv_default,
    )
    from desk.verdict.scoring import (
        BrierPair, aggregate_calibration, brier_3way,
        directional_sanity, reliability_bins,
    )

    fv_path = Path(args.fv_db) if args.fv_db else fv_default()
    if not fv_path.exists():
        print(f"forward-validation db not found at {fv_path}", file=sys.stderr)
        return 2

    with ForwardValidationLog(fv_path) as fv_log:
        triples = fv_log.resolved_prediction_pairs(phase=args.phase)

    if not triples:
        print(f"no resolved predictions in phase {args.phase!r} yet")
        return 1

    pairs: list[BrierPair] = []
    reliability_samples: list[tuple[float, bool]] = []
    for match_id, outcome, pred in triples:
        b_without = brier_3way(
            pred.p_a_without_residual, pred.p_draw_without_residual,
            pred.p_b_without_residual, outcome,
        )
        b_with = brier_3way(
            pred.p_a_with_residual, pred.p_draw_with_residual,
            pred.p_b_with_residual, outcome,
        )
        pairs.append(BrierPair(
            match_id=match_id,
            without_residual=b_without, with_residual=b_with,
        ))
        reliability_samples.append((pred.p_a_with_residual, outcome == "a"))

    report = aggregate_calibration(
        pairs, tolerance=args.tolerance, min_sample_size=args.min_sample,
    )
    sane = directional_sanity(pairs)

    print()
    print(report.headline())
    print(f"  sample-size gate: {'✓' if report.sample_size_cleared else '✗'} "
          f"({report.sample_size} / {report.min_sample_size})")
    print(f"  no-regression gate: {'✓' if report.no_regression else '✗'} "
          f"(Δ {report.brier_delta:+.4f} ≤ {report.tolerance:+.4f})")
    print(f"  directional sanity: {'✓' if sane else '✗'} "
          f"(with-residual wins ≥45% of differing rows)")
    print()
    print("  reliability bins (with-residual p_a vs observed team_a hit rate):")
    print(f"    {'bin':>14s}  {'n':>4s}  {'mean_p':>7s}  {'observed':>9s}  {'gap':>7s}")
    for b in reliability_bins(reliability_samples, n_bins=10):
        print(f"    [{b.lower_pct:.2f}, {b.upper_pct:.2f})  "
              f"{b.n:>4d}  {b.mean_p:>7.3f}  {b.observed_rate:>9.3f}  {b.gap:>+7.3f}")
    print()
    if report.gate_cleared and sane:
        print("  → §1.4 gate cleared + direction sane. Safe to flip "
              "DESK_FORM_RANK_RESIDUAL=1.")
        return 0
    return 1


def _cmd_rate_budget(args: argparse.Namespace) -> int:
    """Print the api-football daily-call budget vs the Pro cap.

    Walks the cadences declared in spec §3.6 + the refresh-loop
    wire-up and prints a per-call-class breakdown. Closes data-layer
    spec §4.1's instrumentation acceptance: "shown to fit inside
    every source's cap with headroom for retries."
    """
    from desk.data.api_football.rate_budget import build_report

    report = build_report(
        fetch_ticks_per_day=max(1, args.ticks_per_day),
        daily_cap=args.daily_cap,
    )
    print()
    print(report.headline())
    print()
    print(f"  {'phase':18s} {'endpoint':38s} {'calls/day':>9s}  cadence")
    print(f"  {'-'*18} {'-'*38} {'-'*9}  {'-'*40}")
    for line in report.lines:
        print(f"  {line.phase:18s} {line.endpoint:38s} "
              f"{line.calls_per_day:>9d}  {line.cadence_desc}")
    print()
    print(f"  total                                                  "
          f"{report.total_calls_per_day:>9d} / {report.daily_cap}")
    return 0 if report.within_cap else 2


def _cmd_verify_data_sources(args: argparse.Namespace) -> int:
    """Smoke-test the external data layer keys.

    Closes guardrail 4 of `THE_DESK_DATA_LAYER_SPEC.md` — "API-Football,
    OpenWeatherMap, and Railway assumptions in §4 / §3.4 are verified
    against current vendor terms before any code is written." Hits the
    cheapest endpoint each provider exposes and reports the plan tier +
    quota so the operator can confirm the keys match the spec's spine.

    Exit codes:
      0 — both providers usable AND api-football tier clears Pro (≥1000 req/day)
      1 — keys work but api-football tier is below Pro (only B.1 smoke OK)
      2 — at least one provider's key failed
    """
    import asyncio

    from desk import config

    async def _run() -> tuple[int, list[str]]:
        lines: list[str] = []
        rc = 0

        # ── api-football ───────────────────────────────────────────
        if not config.API_FOOTBALL_KEY:
            lines.append("api-football · SKIP — API_FOOTBALL_KEY not set")
            rc = max(rc, 2)
        else:
            from desk.data.api_football import (
                APIFootballClient, APIFootballError, fetch_status,
            )
            try:
                async with APIFootballClient(config.API_FOOTBALL_KEY) as c:
                    status = await fetch_status(c)
            except APIFootballError as e:
                lines.append(f"api-football · FAIL ({e.kind}) — {e}")
                rc = max(rc, 2)
            else:
                lines.append(status.headline())
                if status.email:
                    lines.append(f"  account: {status.email}")
                if status.plan_end:
                    lines.append(f"  plan ends: {status.plan_end}")
                if not status.plan_active:
                    lines.append("  WARNING: subscription marked INACTIVE")
                    rc = max(rc, 2)
                elif not status.is_pro_or_higher:
                    lines.append(
                        "  WARNING: daily limit below 1000 — only B.1 smoke "
                        "tests will fit; B.3 (injuries + lineups) needs Pro+."
                    )
                    rc = max(rc, 1)

        # ── openweathermap ─────────────────────────────────────────
        if not config.OPENWEATHERMAP_API_KEY:
            lines.append("openweathermap · SKIP — OPENWEATHERMAP_API_KEY not set")
            rc = max(rc, 2)
        else:
            from desk.data.openweathermap import (
                OpenWeatherClient, OpenWeatherError, probe_status,
            )
            try:
                async with OpenWeatherClient(config.OPENWEATHERMAP_API_KEY) as c:
                    ow = await probe_status(c)
            except OpenWeatherError as e:
                lines.append(f"openweathermap · FAIL ({e.kind}) — {e}")
                rc = max(rc, 2)
            else:
                lines.append(ow.headline())
                if not ow.ok:
                    rc = max(rc, 2)

        # ── odds-api (non-US sportsbooks) ──────────────────────────
        if not config.ODDS_API_KEY:
            lines.append("odds-api · SKIP — ODDS_API_KEY not set")
            # Soft-skip — odds-api is optional in v1 (non-US adapter); don't
            # bump rc.
        else:
            from desk.data.oddsapi import (
                OddsAPIClient, OddsAPIError, fetch_quota_status,
            )
            try:
                async with OddsAPIClient(config.ODDS_API_KEY) as c:
                    qs = await fetch_quota_status(c)
            except OddsAPIError as e:
                lines.append(f"odds-api · FAIL ({e.kind}) — {e}")
                rc = max(rc, 2)
            else:
                lines.append(qs.headline())
                if not qs.key_ok:
                    lines.append("  WARNING: /v4/sports returned empty list")
                    rc = max(rc, 2)

        return rc, lines

    rc, lines = asyncio.run(_run())
    for line in lines:
        print(line)
    return rc


def _cmd_fetch_odds(args: argparse.Namespace) -> int:
    """Pull h2h prices from The Odds API into the oddsapi cache.

    Default sport_key: `soccer_fifa_world_cup` (the headline launch
    surface — matches the default DESK_COMPETITIONS=wc26 site filter).
    Override with `--sport-key soccer_epl` (repeatable) or via the
    `DESK_ODDS_SPORT_KEYS` env var (comma-separated).

    Cost: 1 credit per region asked per call; default regions = `uk,eu`
    (2 credits per sport_key per tick).

    Exit codes:
      0 — refresh succeeded, at least one row persisted
      1 — refresh ran but no rows persisted (likely region misconfig
          or empty card the day of)
      2 — API key missing / call failed
    """
    import asyncio
    import os
    from pathlib import Path

    from desk import config
    from desk.data.oddsapi import DEFAULT_SPORT_KEYS, refresh_all

    if not config.ODDS_API_KEY:
        print("ODDS_API_KEY not set in .env", file=sys.stderr)
        return 2

    if args.sport_key:
        sport_keys = tuple(args.sport_key)
    else:
        # Env-driven override falls between CLI flags and the in-code
        # default. Lets the operator change which leagues the refresh
        # loop fetches without a redeploy.
        env_keys = os.getenv("DESK_ODDS_SPORT_KEYS", "").strip()
        if env_keys:
            sport_keys = tuple(k.strip() for k in env_keys.split(",") if k.strip())
        else:
            sport_keys = DEFAULT_SPORT_KEYS

    cache_path = Path(args.db) if args.db else None

    report = asyncio.run(refresh_all(
        api_key=config.ODDS_API_KEY,
        sport_keys=sport_keys,
        cache_path=cache_path,
        regions=args.regions,
    ))
    print(report.headline())
    if report.error:
        return 2
    if report.events_persisted == 0:
        return 1
    return 0


def _cmd_social_draft_daily(args: argparse.Namespace) -> int:
    """Run the daily social-draft path.

    Reads published MatchOutputs off disk, picks the highest-conviction
    Pick, renders 4 stub PNGs, writes captions, persists a `Draft`. No
    network calls — the operator approves manually before any post
    leaves the queue.
    """
    from desk.social import SocialQueue, load_config

    try:
        cfg = load_config()
    except ValueError as e:
        print(f"social: {e}", file=sys.stderr)
        return 2

    if not cfg.enabled:
        print("social: DESK_SOCIAL_ENABLED=0 — skipping")
        return 0

    from desk.publish import Publisher
    from desk.social.runner import draft_daily

    pub_root = Path(args.output_dir) if args.output_dir else config.OUTPUT_DIR
    pub = Publisher(output_dir=pub_root)

    with SocialQueue(cfg.db_path) as queue:
        draft = draft_daily(
            queue=queue,
            assets_dir=cfg.assets_dir,
            publisher=pub,
            min_edge_pp=cfg.min_edge_pp,
        )
    if draft is None:
        print("social: nothing qualifies today")
        return 0
    print(f"social: drafted {draft.draft_id} (kind={draft.kind.value}, "
          f"match={draft.match_id})")
    return 0


def _cmd_social_draft_weekly(args: argparse.Namespace) -> int:
    """Run the weekly social-draft path."""
    from desk.social import SocialQueue, load_config
    from desk.social.runner import draft_weekly, stub_outcome_lookup

    try:
        cfg = load_config()
    except ValueError as e:
        print(f"social: {e}", file=sys.stderr)
        return 2

    if not cfg.enabled:
        print("social: DESK_SOCIAL_ENABLED=0 — skipping")
        return 0

    from desk.publish import Publisher

    pub_root = Path(args.output_dir) if args.output_dir else config.OUTPUT_DIR
    pub = Publisher(output_dir=pub_root)

    with SocialQueue(cfg.db_path) as queue:
        draft = draft_weekly(
            queue=queue,
            assets_dir=cfg.assets_dir,
            outcome_lookup=stub_outcome_lookup,
            publisher=pub,
        )
    if draft is None:
        print("social: no roundup drafted (window already covered or no Picks)")
        return 0
    print(f"social: drafted {draft.draft_id} (week_starting={draft.week_starting})")
    return 0


def _cmd_backtest(args: argparse.Namespace) -> int:
    """Run the historical backtest harness.

    Lazy-imports the backtest package so the rest of the CLI is fast and
    doesn't depend on openpyxl when only `desk run` is used.
    """
    from desk.backtest.runner import ALL_WINDOWS, run_backtest
    from desk.backtest.tournaments import TOURNAMENTS

    if args.all:
        keys = sorted(TOURNAMENTS)
    else:
        keys = list(args.tournament or [])
    if not keys:
        print("Provide --tournament <key> [--tournament ...] or --all.", file=sys.stderr)
        print(f"Known tournaments: {sorted(TOURNAMENTS)}", file=sys.stderr)
        return 2

    if args.windows:
        windows = tuple(args.windows)
    else:
        windows = ALL_WINDOWS

    # Walk up until we find the workbook scaffold so the resolved path is
    # robust whether `desk` is invoked from the project root or from inside `desk/`.
    here = Path(__file__).resolve()
    candidate_root: Path | None = None
    for ancestor in (*here.parents, here):
        if (ancestor / "desk_backtest.xlsx").exists():
            candidate_root = ancestor
            break
    project_root = candidate_root or here.parents[3]
    workbook_path  = Path(args.workbook)  if args.workbook  else project_root / "desk_backtest.xlsx"
    dashboard_path = Path(args.dashboard) if args.dashboard else project_root / "desk_backtest_dashboard.html"

    try:
        summary = run_backtest(
            tournament_keys=keys,
            windows=windows,
            limit=args.limit,
            workbook_path=workbook_path,
            dashboard_path=dashboard_path,
        )
    except (ValueError, FileNotFoundError, NotImplementedError) as e:
        print(f"backtest failed: {e}", file=sys.stderr)
        return 2

    print()
    print(f"  tournaments       {', '.join(summary['tournaments'])}")
    print(f"  matches           {summary['matches']}")
    print(f"  snapshots         {summary['snapshots']}  (KO: {summary['ko_snapshots']})")
    print(f"  mean Brier        model {summary['mean_brier']:.4f}  | "
          f"closing market {summary['mean_market_brier']:.4f}")
    diff = summary['mean_brier'] - summary['mean_market_brier']
    arrow = "▲ worse" if diff > 0 else ("▼ better" if diff < 0 else "= equal")
    print(f"                    {arrow} by {abs(diff):.4f}")
    print(f"  verdicts          {summary['verdict_counts']}")
    print(f"  workbook          {summary['workbook']}")
    print(f"  dashboard         {summary['dashboard']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="desk", description="The Desk — engine CLI.")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--output-dir", help="override DESK_OUTPUT_DIR")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the engine")
    r.add_argument("--once", action="store_true", help="single pass, then exit")
    r.add_argument("--skip-outrights", action="store_true",
                   help="don't run the outright winner sim (matches only)")
    r.set_defaults(func=_cmd_run)

    o = sub.add_parser("outrights", help="run the outright winner sim only")
    o.add_argument("--sims", type=int, default=10_000)
    o.add_argument("--bootstrap-samples", type=int, default=100)
    o.add_argument("--bootstrap-sims", type=int, default=1_000)
    o.add_argument("--seed", type=int, default=42)
    o.set_defaults(func=_cmd_outrights)

    s = sub.add_parser("sports", help="list registered sports")
    s.set_defaults(func=_cmd_sports)

    m = sub.add_parser("match", help="print one published match JSON")
    m.add_argument("match_id")
    m.set_defaults(func=_cmd_match)

    rp = sub.add_parser("replay", help="re-derive a match as-of (PR 6)")
    rp.add_argument("match_id")
    rp.add_argument("--as-of", required=False)
    rp.set_defaults(func=_cmd_replay)

    fs = sub.add_parser("fetch-signals", help="fetch trusted-core sources into the signals cache")
    fs.add_argument("--db", help="override signals DB path (default: desk/data/signals.db)")
    fs.add_argument("--include-long-tail", action="store_true",
                    help="also fetch long-tail aggregators (e.g. GDELT) — extra cost")
    fs.set_defaults(func=_cmd_fetch_signals)

    es = sub.add_parser("extract-signals",
                        help="run the LLM extractor across cached items (needs ANTHROPIC_API_KEY)")
    es.add_argument("--db", help="override signals DB path (default: desk/data/signals.db)")
    es.add_argument("--model", default="claude-haiku-4-5",
                    help="Claude model id (default: claude-haiku-4-5)")
    es.add_argument("--source", action="append",
                    help="restrict to source(s) by id; repeatable")
    es.add_argument("--limit", type=int, default=None,
                    help="extract at most N items per source (smoke-testing)")
    es.set_defaults(func=_cmd_extract_signals)

    dd = sub.add_parser("distribute-drain",
                        help="drain pending outbox rows to MTA (one sweep)")
    dd.set_defaults(func=_cmd_distribute_drain)

    vd = sub.add_parser(
        "verify-data-sources",
        help="smoke-test API_FOOTBALL_KEY + OPENWEATHERMAP_API_KEY (closes guardrail 4)",
    )
    vd.set_defaults(func=_cmd_verify_data_sources)

    fr = sub.add_parser(
        "fetch-rank-form",
        help="refresh api-football form_delta values into the cache (Phase B.1 data side)",
    )
    fr.add_argument("--db", help="override cache path (default: desk/data/api_football.db)")
    fr.add_argument("--iso3", action="append",
                    help="restrict to ISO3(s) (repeatable); default = WC26 registry")
    fr.set_defaults(func=_cmd_fetch_rank_form)

    rb = sub.add_parser(
        "rate-budget",
        help="print api-football daily-call budget vs Pro cap (closes spec §4.1)",
    )
    rb.add_argument("--ticks-per-day", type=int, default=1,
                    help="how many fetch ticks per 24h (default 1)")
    rb.add_argument("--daily-cap", type=int, default=7500,
                    help="api-football Pro cap (default 7500)")
    rb.set_defaults(func=_cmd_rate_budget)

    sc = sub.add_parser(
        "schedule",
        help="run the refresh loop (PR 6 — folds desk_refresh_loop.py into the CLI)",
    )
    sc.add_argument("--once", action="store_true",
                    help="run a single tick and exit")
    sc.set_defaults(func=_cmd_schedule)

    ba = sub.add_parser(
        "b3-audit",
        help="source-audit api-football /injuries before flipping DESK_INJURY_FETCH (spec §5)",
    )
    ba.add_argument("--af-db", help="override api-football cache path")
    ba.add_argument("--season", type=int, default=2026,
                    help="season year (default 2026)")
    ba.add_argument("--iso3", action="append",
                    help="probe team(s) by iso3 (repeatable); default = top 8 sides")
    ba.set_defaults(func=_cmd_b3_audit)

    fi = sub.add_parser(
        "fetch-injuries",
        help="refresh api-football /injuries cache + per-team Elo penalty (Phase B.3 data side)",
    )
    fi.add_argument("--db", help="override api-football cache path")
    fi.add_argument("--season", type=int, default=2026, help="season year (default 2026)")
    fi.add_argument("--iso3", action="append",
                    help="restrict to ISO3(s) (repeatable); default = WC26 registry")
    fi.set_defaults(func=_cmd_fetch_injuries)

    fc = sub.add_parser(
        "fetch-cards",
        help="refresh api-football card accumulation per team (squad-paragraph Q5)",
    )
    fc.add_argument("--db", help="override api-football cache path")
    fc.add_argument("--season", type=int, default=2026, help="season year (default 2026)")
    fc.add_argument("--competition", default="wc26",
                    help="competition code from CARD_RULES (default wc26)")
    fc.add_argument("--iso3", action="append",
                    help="restrict to ISO3(s) (repeatable); default = WC26 registry")
    fc.set_defaults(func=_cmd_fetch_cards)

    fl = sub.add_parser(
        "fetch-lineups",
        help="refresh api-football /fixtures/lineups for fixtures inside a kickoff window",
    )
    fl.add_argument("--db", help="override api-football cache path")
    fl.add_argument("--season", type=int, default=2026, help="season year (default 2026)")
    fl.add_argument("--window-hours", type=float, default=24.0,
                    help="kickoff window from now (hours). Default 24; T-90m loop uses 2")
    fl.add_argument("--match-id", action="append",
                    help="restrict to match_id(s) (repeatable)")
    fl.set_defaults(func=_cmd_fetch_lineups)

    fo = sub.add_parser(
        "fetch-odds",
        help="pull h2h sportsbook + exchange prices from The Odds API (non-US pivot)",
    )
    fo.add_argument("--db", help="override oddsapi cache path (default: desk/data/oddsapi.db)")
    fo.add_argument("--sport-key", action="append",
                    help="sport_key to fetch (repeatable). Default: soccer_epl")
    fo.add_argument("--regions", default="uk,eu",
                    help="Odds API regions list (default uk,eu)")
    fo.set_defaults(func=_cmd_fetch_odds)

    fe = sub.add_parser(
        "fetch-elo",
        help="refresh live Elo (eloratings.net + api.clubelo.com) into desk/data/elo.db",
    )
    fe.add_argument("--db", help="override elo cache path (default: desk/data/elo.db)")
    fe.add_argument("--skip-national", action="store_true",
                    help="don't fetch eloratings.net")
    fe.add_argument("--skip-club", action="store_true",
                    help="don't fetch api.clubelo.com")
    fe.add_argument("--club", action="append",
                    help="restrict club fetch to id(s) (repeatable)")
    fe.set_defaults(func=_cmd_fetch_elo)

    fvi = sub.add_parser(
        "fv-ingest-outcomes",
        help="ingest resolved match outcomes into forward_validation.db",
    )
    fvi.add_argument("--fv-db", help="override fv db path")
    fvi.add_argument("--af-db", help="override api-football cache path")
    fvi.add_argument("--limit", type=int, default=None,
                     help="process at most N pending match_ids")
    fvi.set_defaults(func=_cmd_fv_ingest_outcomes)

    fvr = sub.add_parser(
        "fv-report",
        help="forward-validation calibration report (closes spec §1.4 gate)",
    )
    fvr.add_argument("--fv-db", help="override fv db path")
    fvr.add_argument("--phase", default="B.1.form",
                     help="phase label to score (default B.1.form)")
    fvr.add_argument("--tolerance", type=float, default=0.005,
                     help="Brier tolerance for the no-regression gate")
    fvr.add_argument("--min-sample", type=int, default=100,
                     help="minimum resolved-fixture sample (default 100)")
    fvr.set_defaults(func=_cmd_fv_report)

    # `desk signals <subcommand>` — nested subparser. `validate` is the
    # only entry for now; future ops (list, stats, …) plug in here.
    sg = sub.add_parser("signals", help="news-signals subsystem ops")
    sg_sub = sg.add_subparsers(dest="signals_cmd", required=True)
    sv = sg_sub.add_parser("validate", help="load + report on the source seed")
    sv.add_argument("--seed", help="override seed CSV path (default: shipped seed)")
    sv.add_argument("--resolve",
                    help="comma-separated tags; report how many sources match")
    sv.set_defaults(func=_cmd_signals_validate)

    # `desk social <subcommand>` — daily / weekly drafters.
    so = sub.add_parser("social", help="social automation drafters")
    so_sub = so.add_subparsers(dest="social_cmd", required=True)
    so_d = so_sub.add_parser("draft-daily",
                              help="pick today's best Pick + render + caption + enqueue")
    so_d.set_defaults(func=_cmd_social_draft_daily)
    so_w = so_sub.add_parser("draft-weekly",
                              help="build the weekly roundup + enqueue")
    so_w.set_defaults(func=_cmd_social_draft_weekly)

    bt = sub.add_parser("backtest", help="run the historical backtest harness")
    bt.add_argument("--tournament", action="append",
                    help="tournament key (repeatable); e.g. wc-2022")
    bt.add_argument("--all", action="store_true",
                    help="run every configured tournament")
    bt.add_argument("--limit", type=int, default=None,
                    help="smoke-test on first N matches per tournament")
    bt.add_argument("--windows", nargs="+", default=None,
                    choices=["T-38", "T-5", "T-1h", "KO"],
                    help="restrict to the given windows; default = all four")
    bt.add_argument("--workbook",  help="override workbook path (default: project root/desk_backtest.xlsx)")
    bt.add_argument("--dashboard", help="override dashboard path (default: project root/desk_backtest_dashboard.html)")
    bt.set_defaults(func=_cmd_backtest)

    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
