"""Forward-validation logger — sqlite schema + upserts + lookups."""

from __future__ import annotations

from desk.verdict.forward_validation import (
    ForwardValidationLog, PredictionRow,
)


def _row(match_id="fb-wc26-fra-mex-20260612", asof="2026-06-12T17:00:00Z"):
    return PredictionRow(
        match_id=match_id, asof_iso=asof, phase="B.1.form",
        p_a_without_residual=0.45, p_draw_without_residual=0.25, p_b_without_residual=0.30,
        p_a_with_residual=0.50, p_draw_with_residual=0.23, p_b_with_residual=0.27,
        feature_set='{"form_delta_a":0.4}',
        logged_at="2026-06-12T17:00:01Z",
    )


def test_log_prediction_round_trips(tmp_path):
    with ForwardValidationLog(tmp_path / "fv.db") as log:
        log.log_prediction(_row())
        rows = log.predictions_for("fb-wc26-fra-mex-20260612")
        assert len(rows) == 1
        r = rows[0]
        assert r.phase == "B.1.form"
        assert r.p_a_with_residual == 0.50


def test_log_prediction_upserts_same_key(tmp_path):
    with ForwardValidationLog(tmp_path / "fv.db") as log:
        log.log_prediction(_row())
        # Same match + asof + phase but different probabilities → overwrite.
        log.log_prediction(PredictionRow(
            **{**_row().__dict__, "p_a_with_residual": 0.99},
        ))
        rows = log.predictions_for("fb-wc26-fra-mex-20260612")
        assert len(rows) == 1
        assert rows[0].p_a_with_residual == 0.99


def test_multiple_phases_coexist(tmp_path):
    with ForwardValidationLog(tmp_path / "fv.db") as log:
        log.log_prediction(_row())
        log.log_prediction(PredictionRow(
            **{**_row().__dict__, "phase": "B.2.weather"},
        ))
        rows = log.predictions_for("fb-wc26-fra-mex-20260612")
        assert {r.phase for r in rows} == {"B.1.form", "B.2.weather"}


def test_record_outcome(tmp_path):
    with ForwardValidationLog(tmp_path / "fv.db") as log:
        assert log.resolved_count() == 0
        log.record_outcome("fb-wc26-fra-mex-20260612", "a")
        log.record_outcome("fb-wc26-eng-bra-20260616", "draw")
        assert log.resolved_count() == 2


def test_record_outcome_upserts(tmp_path):
    with ForwardValidationLog(tmp_path / "fv.db") as log:
        log.record_outcome("fb-wc26-fra-mex-20260612", "a")
        log.record_outcome("fb-wc26-fra-mex-20260612", "b")  # correction
        assert log.resolved_count() == 1
