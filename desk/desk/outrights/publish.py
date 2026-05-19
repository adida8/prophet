"""Write one JSON per outright event to desk/data/output/outrights/.

The static site generator (`site/generate.py`) reads from that directory.
Shape is intentionally close to the per-match `MatchOutput` so the
site's renderers can stay symmetric — but outrights have their own
fields (`outright_id`, `resolves_at`, the position ladder) instead of
match-shaped ones (`match_id`, `kickoff_utc`, two teams).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from desk.outrights.decide import OutrightVerdict, american_for
from desk.outrights.explainer import OutrightCopy
from desk.outrights.ingest_polymarket import OutrightSnapshot
from desk.outrights.model import OutrightModelOutput


def _atomic_write(path: Path, content: str) -> None:
    """Write via a tmp file + os.replace so a partially-written JSON
    never goes live. Match `desk/publish/writer.py`'s pattern.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)


def _outright_id(snapshot: OutrightSnapshot) -> str:
    """Stable, human-readable id for routing and filenames.

    Matches the match-side `match_id` convention (`fb-{competition}-...`)
    but skips the date suffix — outrights have no kickoff.
    """
    return "fb-wc26-winner"


def _verdict_dict(verdict: OutrightVerdict) -> dict:
    if verdict.state == "pick" and verdict.candidate is not None:
        pos = verdict.candidate
        return {
            "state":         "pick",
            "candidate":     pos.label,
            "side":          pos.side,
            "team":          pos.team,
            "edge_pp":       round(pos.edge_pp, 2),
            "lower_edge_pp": round(pos.lower_edge_pp, 2),
            "model_p":       round(pos.model_p, 4),
            "model_p_lower": round(pos.model_p_lower, 4),
            "model_p_upper": round(pos.model_p_upper, 4),
            "market_p":      round(pos.market_p, 4),
            "market_venue":  "polymarket",
            "market_url":    pos.market_url,
            "price":         american_for(pos),
        }
    return {
        "state":     "pass",
        "candidate": None,
    }


def _ladder_dict(verdict: OutrightVerdict, model: OutrightModelOutput) -> list[dict]:
    """One row per team — both sides side-by-side, sorted by model
    P(win) descending. This is what the site renders as a full ladder.

    Each row carries YES and NO data + a per-team verdict: the better
    of the two sides if it clears the Pick gate (lower_edge_pp ≥
    pick_pp), else Pass. Avoid is structurally impossible on this
    market shape (see desk/outrights/decide.py).
    """
    from desk.verdict.thresholds import current as _thresholds
    pick_pp = _thresholds().pick_pp

    yes_by_team: dict[str, "Position"] = {}
    no_by_team:  dict[str, "Position"] = {}
    for pos in verdict.positions:
        bucket = yes_by_team if pos.side == "YES" else no_by_team
        bucket[pos.team] = pos

    rows: list[dict] = []
    for team in yes_by_team:
        yp = yes_by_team[team]
        np_ = no_by_team.get(team)
        if np_ is None:
            continue
        # Per-team verdict: take whichever side clears the gate by the
        # largest lower-edge margin.
        best_side = None
        if yp.lower_edge_pp >= pick_pp and (np_ is None or yp.lower_edge_pp >= np_.lower_edge_pp):
            best_side = "YES"
        elif np_.lower_edge_pp >= pick_pp:
            best_side = "NO"
        rows.append({
            "team":           team,
            "model_p":        round(yp.model_p, 4),         # P(win) — same on YES side
            "model_p_lower":  round(yp.model_p_lower, 4),
            "model_p_upper":  round(yp.model_p_upper, 4),
            "yes_market_p":   round(yp.market_p, 4),
            "no_market_p":    round(np_.market_p, 4),
            "yes_edge_pp":    round(yp.edge_pp, 2),
            "no_edge_pp":     round(np_.edge_pp, 2),
            "yes_lower_edge_pp": round(yp.lower_edge_pp, 2),
            "no_lower_edge_pp":  round(np_.lower_edge_pp, 2),
            "verdict":        "pick" if best_side else "pass",
            "pick_side":      best_side,
        })
    rows.sort(key=lambda r: -r["model_p"])
    return rows


def build_payload(
    snapshot: OutrightSnapshot,
    model: OutrightModelOutput,
    verdict: OutrightVerdict,
    copy: OutrightCopy,
) -> dict:
    oid = _outright_id(snapshot)
    return {
        "outright_id":    oid,
        "sport":          "football",
        "competition": {
            "code":  "wc26",
            "label": "FIFA World Cup 2026",
            "stage": "pre_tournament",
        },
        "market_label":   "World Cup 2026 — outright winner",
        "market_venue":   "polymarket",
        "market_url":     f"https://polymarket.com/event/{snapshot.event_slug}",
        "candidate":      verdict.candidate.team if verdict.candidate else "—",
        "resolves_at":    snapshot.resolution_utc.isoformat().replace("+00:00", "Z"),
        "asof":           snapshot.asof.isoformat().replace("+00:00", "Z"),
        "verdict":        _verdict_dict(verdict),
        "copy": {
            "title":   copy.title,
            "summary": copy.summary,
            "blurb":   copy.blurb,
            "drivers": list(copy.drivers),
        },
        "model": {
            "sims":              model.sims,
            "bootstrap_samples": 100,
            "seed":              model.seed,
            "overround_pp":      round(snapshot.overround * 100, 2),
        },
        "ladder": _ladder_dict(verdict, model),
        "updated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def write(
    out_dir: Path,
    snapshot: OutrightSnapshot,
    model: OutrightModelOutput,
    verdict: OutrightVerdict,
    copy: OutrightCopy,
) -> Path:
    """Write `<outright_id>.json` + a sibling `.etag` (SHA-256 of the
    canonical JSON). Returns the JSON path.
    """
    payload = build_payload(snapshot, model, verdict, copy)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    oid = payload["outright_id"]
    json_path = out_dir / f"{oid}.json"
    etag_path = out_dir / f"{oid}.json.etag"

    _atomic_write(json_path, json.dumps(payload, indent=2, ensure_ascii=False))
    _atomic_write(etag_path, digest)
    return json_path


def write_index(out_dir: Path, snapshots: list[dict]) -> Path:
    """Manifest of all outrights — mirrors `desk/publish/writer.py`'s
    match index file. Includes outright_id + verdict state for the
    site generator and future API consumers.
    """
    payload = {
        "outrights": snapshots,
        "updated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    path = out_dir / "index.json"
    _atomic_write(path, json.dumps(payload, indent=2, ensure_ascii=False))
    return path
