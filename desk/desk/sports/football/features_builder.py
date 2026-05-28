"""Football feature builder.

Translates a `FixtureRef` into a `FootballFeatures` row by joining:

  - Elo (international from `data/elo_seed.py`, club ditto — live ingest
    arrives in v1.1)
  - Venue resolution + host / altitude lookup (PR 3 data tables)
  - Altitude-acclimatised flag for international sides

For PR 4, Polymarket's gamma payload doesn't carry per-fixture stadium
data, so most fixtures end up with `venue_*` fields unpopulated and the
host / home / altitude bonuses simply don't fire. The model still
returns useful probabilities — pure-Elo with no venue wash. PR 6 (or a
3.1 follow-up) will join FIFA's fixture-to-stadium map for WC 2026 to
unlock those bonuses for the launch wedge.
"""

from __future__ import annotations

from typing import Protocol

from desk.sport import FixtureRef
from desk.sports.football.data.elo_seed import (
    club_elo,
    club_elo_source,
    is_altitude_acclimatised,
    national_elo,
    national_elo_source,
)
from desk.sports.football.metadata.club import home_ground_of
from desk.sports.football.metadata.fifa import (
    host_iso3_for_competition,
    venue_for_match,
)
from desk.sports.football.model import FootballFeatures
from desk.sports.football.teams import is_international_competition


class _FormSource(Protocol):
    """Minimal read interface — anything that can look up form_delta +
    injury_penalty for a national ISO3. `APIFootballRuntime` satisfies
    this without being imported (decouples the features-builder from
    the data layer's concrete deps)."""
    def form_delta_for_iso3(self, iso3: str) -> float | None: ...
    def injury_penalty_for_iso3(self, iso3: str) -> float | None: ...


class _EloSource(Protocol):
    """Live-Elo read interface. `EloRuntime` satisfies this. When
    omitted, the features-builder reads only the static seed —
    preserving the pre-Phase-1b path byte-for-byte (the regression
    gate for Phase 1b is the WC-2022 backtest, which never wires
    `elo_source`)."""
    def national_elo(self, iso3: str) -> float: ...
    def national_elo_source(self, iso3: str) -> str: ...
    def club_elo(self, club_id: str) -> float: ...
    def club_elo_source(self, club_id: str) -> str: ...


def _team_iso3_from_match_id(match_id: str, *, position: int) -> str | None:
    """Extract the home or away team slug from a `fb-{comp}-{home}-{away}-{date}`
    match_id. Useful only for international fixtures, where the slug fragment IS
    the ISO3 (after Polymarket's overrides have been mapped, e.g. `kr → kor`).
    """
    parts = match_id.split("-")
    # fb · comp · ... · home · away · date — last two before date.
    if len(parts) < 5:
        return None
    return parts[-3] if position == 0 else parts[-2]


def _club_id_from_match_id(match_id: str, *, position: int) -> str | None:
    """A club's `{league}-{short}` ID inside the match_id is two segments
    that include the league prefix. PR 4 leaves this empty until the
    fixture-mapping table is wired in a follow-up.
    """
    return None  # TODO(PR 4.5): join Polymarket club codes → spec club IDs.


def build_features(
    fx: FixtureRef,
    *,
    form_source: _FormSource | None = None,
    elo_source:  _EloSource  | None = None,
) -> FootballFeatures:
    """Build a `FootballFeatures` row for a fixture.

    When `form_source` is provided (typically an `APIFootballRuntime`
    bound to the api-football cache), each national side's form_delta
    is looked up by ISO3 and threaded onto the features. Missing
    entries stay None — the model hook treats absent as zero
    contribution per Phase B.1 spec.

    When `elo_source` is provided (typically an `EloRuntime` bound to
    the live-Elo cache), national + club Elo + their source labels
    flow from the live ingest. Missing entries fall back to the
    static seed via the runtime — so the source label stays accurate
    ("eloratings" / "clubelo" for live; "wiki" / "stub" for seed).
    When `elo_source` is None, the static seed is read directly,
    preserving the pre-Phase-1b behaviour byte-for-byte (the regression
    gate is the WC-2022 backtest, which never wires elo_source).

    The hook in `_adjusted_elos` is still gated on
    `DESK_FORM_RANK_RESIDUAL=1`, so populating form_delta here is a
    Shadow-mode no-op until the operator flips that flag.
    """
    international = is_international_competition(fx.competition_code)

    # ── Elo prior + source provenance (PR 4.5; Phase 1b live layer) ─
    if international:
        a_iso = _team_iso3_from_match_id(fx.match_id, position=0)
        b_iso = _team_iso3_from_match_id(fx.match_id, position=1)
        if elo_source is not None:
            a_elo = elo_source.national_elo(a_iso) if a_iso else 1500.0
            b_elo = elo_source.national_elo(b_iso) if b_iso else 1500.0
            a_src = elo_source.national_elo_source(a_iso) if a_iso else "stub"
            b_src = elo_source.national_elo_source(b_iso) if b_iso else "stub"
        else:
            a_elo = national_elo(a_iso) if a_iso else 1500.0
            b_elo = national_elo(b_iso) if b_iso else 1500.0
            a_src = national_elo_source(a_iso) if a_iso else "stub"
            b_src = national_elo_source(b_iso) if b_iso else "stub"
    else:
        a_id = _club_id_from_match_id(fx.match_id, position=0)
        b_id = _club_id_from_match_id(fx.match_id, position=1)
        a_iso = b_iso = None
        if elo_source is not None:
            a_elo = elo_source.club_elo(a_id) if a_id else 1500.0
            b_elo = elo_source.club_elo(b_id) if b_id else 1500.0
            a_src = elo_source.club_elo_source(a_id) if a_id else "stub"
            b_src = elo_source.club_elo_source(b_id) if b_id else "stub"
        else:
            a_elo = club_elo(a_id) if a_id else 1500.0
            b_elo = club_elo(b_id) if b_id else 1500.0
            a_src = club_elo_source(a_id) if a_id else "stub"
            b_src = club_elo_source(b_id) if b_id else "stub"

    # ── Venue + altitude ───────────────────────────────────────────
    venue_host_iso3:    str | None   = None
    venue_altitude_m:   float | None = None

    if international:
        host_set = host_iso3_for_competition(fx.competition_code)
        if fx.venue_country and fx.venue_country.upper() in {
            v.country_iso2 for v in (
                # quick reverse-lookup so we can tolerate either iso2 or iso3 inputs
                __import__("desk.sports.football.data.wc26_venues", fromlist=["WC26_VENUES"]).WC26_VENUES.values()
            )
        }:
            # The country is one of the host venues; figure its ISO3.
            from desk.sports.football.data.wc26_venues import WC26_VENUES
            for v in WC26_VENUES.values():
                if v.country_iso2 == fx.venue_country.upper():
                    if v.country_iso3 in host_set:
                        venue_host_iso3 = v.country_iso3
                    break
        if fx.venue_stadium:
            v = venue_for_match(fx.competition_code, fx.venue_stadium)
            if v is not None:
                venue_altitude_m = v.altitude_m
                if v.country_iso3 in host_set:
                    venue_host_iso3 = v.country_iso3

    # ── Home grounds (clubs) ──────────────────────────────────────
    a_home_ground = b_home_ground = None
    if not international:
        a_id = _club_id_from_match_id(fx.match_id, position=0)
        b_id = _club_id_from_match_id(fx.match_id, position=1)
        if a_id:
            g = home_ground_of(a_id)
            if g:
                a_home_ground = g.stadium
        if b_id:
            g = home_ground_of(b_id)
            if g:
                b_home_ground = g.stadium

    # ── Phase B.1 — form_delta from api-football cache ──────────
    # Internationals only in v1 (the WC26 registry is national-side
    # only; clubs land in a later phase). rank_residual stays None —
    # api-football doesn't expose FIFA world rank directly without
    # the FIFA-ranking-only paid plan, so we defer that to a follow-up.
    a_form = b_form = None
    a_inj = b_inj = None
    if international and form_source is not None:
        # `injury_penalty_for_iso3` is a Phase-B.3 addition; older
        # form_source implementations (and test doubles that predate
        # B.3) may not expose it. Tolerate that — absent = zero
        # contribution per spec §3.6.
        get_inj = getattr(form_source, "injury_penalty_for_iso3", None)
        if a_iso:
            a_form = form_source.form_delta_for_iso3(a_iso)
            if get_inj is not None:
                a_inj = get_inj(a_iso)
        if b_iso:
            b_form = form_source.form_delta_for_iso3(b_iso)
            if get_inj is not None:
                b_inj = get_inj(b_iso)

    return FootballFeatures(
        team_a_name=fx.team_a, team_b_name=fx.team_b,
        team_a_elo=a_elo,      team_b_elo=b_elo,
        is_international=international,
        team_a_iso3=a_iso, team_b_iso3=b_iso,
        venue_host_iso3=venue_host_iso3,
        team_a_home_ground=a_home_ground,
        team_b_home_ground=b_home_ground,
        venue_stadium=fx.venue_stadium,
        venue_altitude_m=venue_altitude_m,
        team_a_altitude_acclimatised=bool(a_iso) and is_altitude_acclimatised(a_iso),
        team_b_altitude_acclimatised=bool(b_iso) and is_altitude_acclimatised(b_iso),
        team_a_elo_source=a_src,
        team_b_elo_source=b_src,
        team_a_form_delta=a_form,
        team_b_form_delta=b_form,
        team_a_injury_elo_penalty=a_inj,
        team_b_injury_elo_penalty=b_inj,
    )
