from core.analysis.benchmark_compare import compare_provider_outputs


def test_compare_provider_outputs():
    baseline = {"bpm": 128.0, "key": "8A", "energy": 0.60}
    candidate = {"bpm": 129.0, "key": "8A", "energy": 0.65}

    result = compare_provider_outputs(baseline, candidate)

    assert result["bpm_delta"] == 1.0
    assert result["same_key"] is True
    assert result["energy_delta"] == 0.05
