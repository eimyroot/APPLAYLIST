from services.desktop.playlist_editor_sidecar import install_playlist_editor_sidecar
from services.desktop.playlist_export_sidecar import install_playlist_export_sidecar
from services.desktop.set_proposal_sidecar import install_set_proposal_sidecar
from services.desktop.sidecar import main


install_set_proposal_sidecar()
install_playlist_editor_sidecar()
install_playlist_export_sidecar()


if __name__ == "__main__":
    raise SystemExit(main())
