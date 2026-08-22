from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from core.intelligence.meaningful_diversity_contract import MeaningfulDiversityStatus
from services.intelligence.real_library_pilot import RealLibraryPilotError


def test_dangling_evidence_symlink_is_rejected_before_write(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import services.intelligence.real_library_meaningful_review as module

    snapshot_path = tmp_path / "snapshot.json"
    selection_path = tmp_path / "selection.json"
    snapshot_path.write_text(json.dumps({"placeholder": True}), encoding="utf-8")
    selection_path.write_text(
        json.dumps(
            {
                "case_specs": [
                    {
                        "case_spec_id": "case-security",
                        "seed_track_id": "seed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    materialized = SimpleNamespace(case=SimpleNamespace(case_id="case-security"))
    monkeypatch.setattr(module, "analyze_real_tracks", lambda **_: {})
    monkeypatch.setattr(module, "materialize_cases", lambda **_: (materialized,))
    monkeypatch.setattr(
        module,
        "evaluate_materialized_case_r1",
        lambda **_: {
            "case_id": "case-security",
            "status": MeaningfulDiversityStatus.SUFFICIENT.value,
        },
    )

    output = tmp_path / "output"
    output.mkdir()
    outside = tmp_path / "outside-report.json"
    report = output / "APPLAYLIST_MEANINGFUL_DIVERSITY_STYLE_ENERGY_R1_REPORT.json"
    report.symlink_to(outside)

    with pytest.raises(RealLibraryPilotError, match="refusing to overwrite evidence artifact"):
        module.materialize_real_library_pilot_meaningful_r1(
            snapshot_path=snapshot_path,
            selection_path=selection_path,
            output_dir=output,
            database_path=tmp_path / "pilot.sqlite",
            generated_at="2026-08-22T01:00:00Z",
            blinding_seed="local-test-seed",
        )

    assert report.is_symlink()
    assert not outside.exists()
    assert not (output / "APPLAYLIST_BLINDED_HUMAN_DJ_REVIEW_PACKET_R1.json").exists()
    assert not (output / "APPLAYLIST_REAL_LIBRARY_RUNTIME_EVIDENCE_R1.private.json").exists()
