from __future__ import annotations

import inspect

from services.intelligence import human_review_protocol_r2


def test_curation_calibration_public_api_has_no_transition_or_execution_inputs() -> None:
    case_signature = inspect.signature(human_review_protocol_r2.calibrate_curation_case_r3)
    report_signature = inspect.signature(human_review_protocol_r2.build_curation_calibration_report_r3)

    forbidden = {
        "transition",
        "execution",
        "render",
        "audition",
    }
    for signature in (case_signature, report_signature):
        parameter_names = {name.lower() for name in signature.parameters}
        assert not any(
            token in parameter_name
            for parameter_name in parameter_names
            for token in forbidden
        )


def test_holdout_selection_api_has_no_human_label_or_challenger_inputs() -> None:
    signature = inspect.signature(human_review_protocol_r2.select_holdout_cases_r2)
    parameter_names = {name.lower() for name in signature.parameters}
    forbidden = {
        "review",
        "human",
        "preference",
        "rating",
        "challenger",
        "shadow",
        "score",
    }
    assert not any(
        token in parameter_name
        for parameter_name in parameter_names
        for token in forbidden
    )


def test_curation_service_does_not_import_execution_or_audition_contracts() -> None:
    source = inspect.getsource(human_review_protocol_r2)
    assert "HumanExecutionReviewR2" not in source
    assert "HumanTransitionAuditionReviewR2" not in source


def test_protocol_service_has_no_audio_filesystem_network_or_provider_execution_path() -> None:
    source = inspect.getsource(human_review_protocol_r2)
    forbidden_tokens = (
        "requests.",
        "httpx.",
        "urllib.",
        "socket.",
        "librosa",
        "BaselineLibrosaMIR",
        "analyze_real_tracks",
        "Path(",
        ".read_bytes(",
        ".read_text(",
        ".write_bytes(",
        ".write_text(",
    )
    for token in forbidden_tokens:
        assert token not in source
