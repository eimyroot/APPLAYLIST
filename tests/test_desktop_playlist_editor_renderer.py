from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_playlist_editor_renderer_is_strict_and_host_mediated() -> None:
    editor = (ROOT / "desktop" / "host-proof" / "playlist-editor.js").read_text(encoding="utf-8")
    html = (ROOT / "desktop" / "host-proof" / "index.html").read_text(encoding="utf-8")

    for command in (
        "playlist_editor_accept",
        "playlist_editor_reorder",
        "playlist_editor_lock",
        "playlist_editor_replace",
        "playlist_editor_history",
    ):
        assert command in editor
    assert "applaylist-desktop-playlist-revision-r1" in editor
    assert "applaylist-desktop-playlist-history-r1" in editor
    assert "production_activation_authorized !== false" in editor
    assert "personal_dj_model_training_authorized !== false" in editor
    assert "exactKeys" in editor
    assert "textContent" in editor
    assert "innerHTML" not in editor
    assert "fetch(" not in editor
    assert "XMLHttpRequest" not in editor
    assert "localStorage" not in editor
    assert "sessionStorage" not in editor
    assert "playlist-editor.js" in html
    assert "playlist-editor.css" in html
    assert 'id="playlist-editor"' in html


def test_playlist_editor_tauri_surface_is_explicit_and_separate() -> None:
    lib = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
    build = (ROOT / "src-tauri" / "build.rs").read_text(encoding="utf-8")
    capability = (
        ROOT / "src-tauri" / "capabilities" / "main-playlist-editor.json"
    ).read_text(encoding="utf-8")
    config = (ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")

    for command in (
        "playlist_editor_accept",
        "playlist_editor_reorder",
        "playlist_editor_lock",
        "playlist_editor_replace",
        "playlist_editor_history",
    ):
        assert command in lib
        assert command in build
        assert f"allow-{command.replace('_', '-')}" in capability
    assert '"main-playlist-editor"' in config
    assert '"connect-src \'none\'"' not in config  # CSP remains serialized as one string
    assert "connect-src 'none'" in config
