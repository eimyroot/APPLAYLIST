from __future__ import annotations

import inspect

from services.intelligence import fresh_personal_holdout_runner as runner


def test_holdout_selection_call_has_no_human_or_challenger_inputs() -> None:
    source = inspect.getsource(runner.materialize_fresh_personal_holdout_r1)
    selection_call = source.split("select_holdout_cases_r2(", 1)[1].split(")", 1)[0].lower()
    for forbidden in ("preference", "rating", "review", "challenger", "shadow"):
        assert forbidden not in selection_call


def test_reviewer_packet_builder_has_no_strategy_or_challenger_parameters() -> None:
    parameters = set(inspect.signature(runner._reviewer_case).parameters)
    assert parameters == {"item", "names"}


def test_private_manifest_freezes_source_review_cases_for_unblinding() -> None:
    source = inspect.getsource(runner.materialize_fresh_personal_holdout_r1)
    assert '"source_review_cases"' in source
    assert "asdict(by_case[case_id].case)" in source
    assert '"source_review_cases_frozen_before_reviewer_publication": True' in source


def test_runner_has_no_activation_path() -> None:
    source = inspect.getsource(runner).lower()
    assert "activation_authorized\": true" not in source
    assert "personal_dj_model_training_authorized\": true" not in source
