from __future__ import annotations

import json
from pathlib import Path


def test_competitive_curation_benchmark_fixture_is_bounded_and_complete() -> None:
    path = Path("tests/fixtures/competitive_curation_r1.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema"] == "applaylist-competitive-curation-benchmark-r1"
    assert payload["provenance"]["human_feedback_fabricated"] is False
    scenarios = payload["scenarios"]
    assert len(scenarios) == 5
    assert {item["scenario_id"] for item in scenarios} == {
        "coherent-house-tech-house-peak",
        "ukg-saturation",
        "sudden-rave-techno-drift",
        "under-energy-peak",
        "near-equivalent-alternatives",
    }
