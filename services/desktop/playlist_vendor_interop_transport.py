from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

from services.desktop.playlist_export_transport import (
    DesktopPlaylistExportTransport,
    DesktopPlaylistExportTransportError,
)

_MAX_VENDOR_EXPORT_BYTES = 128 * 1024
_PREVIEW_SCHEMA = "applaylist-desktop-vendor-interop-preview-r1"
_MATERIAL_SCHEMA = "applaylist-desktop-vendor-interop-material-r1"
_CATALOG_VERSION = "vendor-interop-catalog-r1"
_VERIFIED_AT = "2026-08-19"
_REKORDBOX_FORMAT = "rekordbox_xml"


class DesktopPlaylistVendorInteropError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DesktopPlaylistVendorInteropTransport:
    """Read-only vendor handoff over one exact immutable PlaylistRevision."""

    def __init__(
        self,
        *,
        export: DesktopPlaylistExportTransport | None = None,
    ) -> None:
        self.export = export or DesktopPlaylistExportTransport()

    def preview(self, *, revision_id: str) -> dict[str, object]:
        preview, material = self._canonical_pair(revision_id)
        return {
            "schema": _PREVIEW_SCHEMA,
            "catalog_version": _CATALOG_VERSION,
            "verified_at": _VERIFIED_AT,
            "revision_id": preview["revision_id"],
            "playlist_id": preview["playlist_id"],
            "revision_index": preview["revision_index"],
            "track_count": preview["track_count"],
            "m3u8_path_valid": True,
            "m3u8_content_sha256": material["content_sha256"],
            "capabilities": self._capabilities(),
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }

    def rekordbox_material(self, *, revision_id: str) -> dict[str, object]:
        preview, material = self._canonical_pair(revision_id)
        sequence = preview["sequence"]
        if not isinstance(sequence, (tuple, list)):
            raise DesktopPlaylistVendorInteropError(
                "vendor_interop_revision_invalid",
                "The immutable playlist revision sequence is invalid.",
            )

        m3u8_lines = str(material["content_utf8"]).splitlines()
        expected_line_count = 1 + int(preview["track_count"]) * 2
        if (
            not m3u8_lines
            or m3u8_lines[0] != "#EXTM3U"
            or len(m3u8_lines) != expected_line_count
        ):
            raise DesktopPlaylistVendorInteropError(
                "vendor_interop_m3u8_invalid",
                "The canonical M3U8 material is invalid.",
            )
        canonical_paths = tuple(m3u8_lines[index] for index in range(2, len(m3u8_lines), 2))
        if len(canonical_paths) != len(sequence):
            raise DesktopPlaylistVendorInteropError(
                "vendor_interop_m3u8_invalid",
                "The canonical M3U8 material does not match the selected revision.",
            )

        root = ET.Element("DJ_PLAYLISTS", {"Version": "1.0.0"})
        ET.SubElement(
            root,
            "PRODUCT",
            {"Name": "APPLAYLIST", "Version": "1.0", "Company": "APPLAYLIST"},
        )
        collection = ET.SubElement(root, "COLLECTION", {"Entries": str(len(sequence))})
        for track_id, (item, canonical_path) in enumerate(
            zip(sequence, canonical_paths, strict=True),
            start=1,
        ):
            ET.SubElement(
                collection,
                "TRACK",
                {
                    "TrackID": str(track_id),
                    "Name": str(item["display_name"]),
                    "Location": self._rekordbox_location(canonical_path),
                },
            )

        playlists = ET.SubElement(root, "PLAYLISTS")
        root_node = ET.SubElement(
            playlists,
            "NODE",
            {"Type": "0", "Name": "ROOT", "Count": "1"},
        )
        playlist_node = ET.SubElement(
            root_node,
            "NODE",
            {
                "Name": self._playlist_name(str(preview["revision_id"])),
                "Type": "1",
                "KeyType": "0",
                "Entries": str(len(sequence)),
            },
        )
        for track_id in range(1, len(sequence) + 1):
            ET.SubElement(playlist_node, "TRACK", {"Key": str(track_id)})

        content = (
            '<?xml version="1.0" encoding="UTF-8" ?>\n'
            + ET.tostring(root, encoding="unicode", short_empty_elements=True)
            + "\n"
        )
        encoded = content.encode("utf-8")
        if len(encoded) > _MAX_VENDOR_EXPORT_BYTES:
            raise DesktopPlaylistVendorInteropError(
                "vendor_interop_export_too_large",
                "The vendor export exceeds the bounded XML size limit.",
            )
        return {
            "schema": _MATERIAL_SCHEMA,
            "vendor": "rekordbox",
            "format": _REKORDBOX_FORMAT,
            "revision_id": preview["revision_id"],
            "playlist_id": preview["playlist_id"],
            "revision_index": preview["revision_index"],
            "suggested_filename": self._suggested_filename(str(preview["revision_id"])),
            "track_count": len(sequence),
            "content_utf8": content,
            "content_sha256": hashlib.sha256(encoded).hexdigest(),
            "byte_count": len(encoded),
            "m3u8_content_sha256": material["content_sha256"],
            "vendor_database_mutation_authorized": False,
            "personal_dj_model_training_authorized": False,
            "production_activation_authorized": False,
        }

    def _canonical_pair(
        self,
        revision_id: str,
    ) -> tuple[dict[str, object], dict[str, object]]:
        try:
            preview = self.export.preview(revision_id=revision_id)
            material = self.export.material(revision_id=revision_id)
        except DesktopPlaylistExportTransportError as exc:
            raise DesktopPlaylistVendorInteropError(exc.code, exc.message) from exc

        if not (
            preview.get("revision_id") == material.get("revision_id")
            and preview.get("playlist_id") == material.get("playlist_id")
            and preview.get("revision_index") == material.get("revision_index")
            and preview.get("track_count") == material.get("track_count")
            and material.get("format") == "m3u8"
            and isinstance(material.get("content_sha256"), str)
        ):
            raise DesktopPlaylistVendorInteropError(
                "vendor_interop_revision_mismatch",
                "The canonical export projections do not identify the same immutable revision.",
            )
        return preview, material

    @staticmethod
    def _capabilities() -> tuple[dict[str, object], ...]:
        return (
            {
                "vendor": "rekordbox",
                "status": "documented_format_export",
                "artifact_format": _REKORDBOX_FORMAT,
                "source_reference_code": "rekordbox_xml_bridge_official",
                "user_action_code": "import_xml_via_bridge",
                "artifact_export_available": True,
                "vendor_database_mutation_authorized": False,
            },
            {
                "vendor": "traktor",
                "status": "guidance_only_nml_required",
                "artifact_format": None,
                "source_reference_code": "traktor_nml_import_official",
                "user_action_code": "use_supported_nml_import_workflow",
                "artifact_export_available": False,
                "vendor_database_mutation_authorized": False,
            },
            {
                "vendor": "serato",
                "status": "guidance_only_files_crate",
                "artifact_format": None,
                "source_reference_code": "serato_files_crate_official",
                "user_action_code": "drag_files_or_folder_to_crate",
                "artifact_export_available": False,
                "vendor_database_mutation_authorized": False,
            },
        )

    @staticmethod
    def _rekordbox_location(canonical_path: str) -> str:
        if (
            not isinstance(canonical_path, str)
            or not canonical_path
            or "\r" in canonical_path
            or "\n" in canonical_path
            or "\x00" in canonical_path
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in canonical_path)
        ):
            raise DesktopPlaylistVendorInteropError(
                "vendor_interop_path_invalid",
                "A canonical track path cannot be represented safely for rekordbox.",
            )
        path = Path(canonical_path)
        if not path.is_absolute() or not path.is_file():
            raise DesktopPlaylistVendorInteropError(
                "vendor_interop_path_invalid",
                "A canonical track path is unavailable.",
            )
        uri = path.as_uri()
        if uri.startswith("file:///"):
            uri = "file://localhost/" + uri[len("file:///") :]
        if not uri.startswith("file://localhost/"):
            raise DesktopPlaylistVendorInteropError(
                "vendor_interop_path_invalid",
                "A canonical track path cannot be represented as a local file URI.",
            )
        return uri

    @staticmethod
    def _playlist_name(revision_id: str) -> str:
        if (
            not isinstance(revision_id, str)
            or not revision_id
            or revision_id.strip() != revision_id
            or len(revision_id) > 256
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in revision_id)
        ):
            raise DesktopPlaylistVendorInteropError(
                "vendor_interop_revision_invalid",
                "The immutable playlist revision identity is invalid.",
            )
        return f"APPLAYLIST {revision_id}"

    @staticmethod
    def _suggested_filename(revision_id: str) -> str:
        safe = "".join(
            ch for ch in revision_id if ch.isascii() and (ch.isalnum() or ch in "_-")
        )
        if not safe:
            safe = "playlist-revision"
        return f"APPLAYLIST_{safe[:84]}_rekordbox.xml"


__all__ = [
    "DesktopPlaylistVendorInteropError",
    "DesktopPlaylistVendorInteropTransport",
]
