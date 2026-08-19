from services.desktop.playlist_editor_sidecar import install_playlist_editor_sidecar
from services.desktop.playlist_evidence_export_sidecar import (
    install_playlist_evidence_export_sidecar,
)
from services.desktop.playlist_export_sidecar import install_playlist_export_sidecar
from services.desktop.playlist_vendor_interop_sidecar import (
    install_playlist_vendor_interop_sidecar,
)
from services.desktop.set_proposal_sidecar import install_set_proposal_sidecar
from services.desktop.sidecar import main
from services.desktop.transition_inspector_sidecar import install_transition_inspector_sidecar


install_set_proposal_sidecar()
install_playlist_editor_sidecar()
install_playlist_export_sidecar()
install_playlist_evidence_export_sidecar()
install_playlist_vendor_interop_sidecar()
install_transition_inspector_sidecar()


if __name__ == "__main__":
    raise SystemExit(main())