from pathlib import Path
from types import SimpleNamespace

from services.export.exporter import Exporter


def test_exporter_writes_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EXPORTS_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "artifacts"))

    exporter = Exporter()

    tracks = [
        SimpleNamespace(track_id="t1", path="/music/t1.mp3"),
        SimpleNamespace(track_id="t2", path="/music/t2.mp3"),
        SimpleNamespace(track_id="t3", path=None),
    ]

    result = exporter.export_m3u("playlist-test", tracks)

    assert Path(result["m3u_path"]).exists()
    assert Path(result["manifest_path"]).exists()
    assert Path(result["warnings_path"]).exists()
    assert Path(result["audit_path"]).exists()
    assert result["resolved_count"] == 2
    assert result["skipped_count"] == 1
