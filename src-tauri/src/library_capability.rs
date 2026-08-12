use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    sync::Mutex,
};

use serde::Serialize;
use tauri::{AppHandle, State};
use tauri_plugin_dialog::DialogExt;
use uuid::Uuid;

const CAPABILITY_PREFIX: &str = "lrc_";

#[derive(Debug, Clone, PartialEq, Eq)]
struct CapabilityRecord {
    root: PathBuf,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct CapabilityError {
    code: &'static str,
    message: &'static str,
}

impl CapabilityError {
    const fn invalid_id() -> Self {
        Self {
            code: "invalid_library_root_capability",
            message: "Library folder authorization is invalid.",
        }
    }

    const fn unknown_id() -> Self {
        Self {
            code: "unknown_library_root_capability",
            message: "Library folder authorization is not active.",
        }
    }

    const fn registry_unavailable() -> Self {
        Self {
            code: "library_capability_registry_unavailable",
            message: "Library folder authorization is temporarily unavailable.",
        }
    }

    const fn selected_root_unavailable() -> Self {
        Self {
            code: "selected_library_root_unavailable",
            message: "The selected library folder is unavailable.",
        }
    }

    const fn selected_root_not_directory() -> Self {
        Self {
            code: "selected_library_root_not_directory",
            message: "The selected library root is not a directory.",
        }
    }
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct LibraryRootCapability {
    capability_id: String,
    display_name: String,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct DesktopHostError {
    code: String,
    message: String,
}

impl DesktopHostError {
    pub(crate) fn new(code: &str, message: &str) -> Self {
        Self {
            code: code.to_owned(),
            message: message.to_owned(),
        }
    }
}

impl From<CapabilityError> for DesktopHostError {
    fn from(value: CapabilityError) -> Self {
        Self {
            code: value.code.to_owned(),
            message: value.message.to_owned(),
        }
    }
}

#[derive(Debug, Default)]
pub struct LibraryCapabilityRegistry {
    roots: Mutex<HashMap<Uuid, CapabilityRecord>>,
}

impl LibraryCapabilityRegistry {
    fn parse_id(raw: &str) -> Result<Uuid, CapabilityError> {
        let encoded = raw
            .strip_prefix(CAPABILITY_PREFIX)
            .ok_or_else(CapabilityError::invalid_id)?;

        if encoded.len() != 32
            || !encoded.chars().all(|ch| ch.is_ascii_hexdigit())
            || encoded.chars().any(|ch| ch.is_ascii_uppercase())
        {
            return Err(CapabilityError::invalid_id());
        }

        let parsed = Uuid::parse_str(encoded).map_err(|_| CapabilityError::invalid_id())?;
        if parsed.simple().to_string() != encoded {
            return Err(CapabilityError::invalid_id());
        }
        Ok(parsed)
    }

    fn safe_display_name(root: &Path) -> String {
        let raw = root
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("Selected folder");
        let filtered = raw
            .chars()
            .filter(|ch| !ch.is_control())
            .take(128)
            .collect::<String>();
        let trimmed = filtered.trim();
        if trimmed.is_empty() {
            "Selected folder".to_owned()
        } else {
            trimmed.to_owned()
        }
    }

    fn issue_selected_root(
        &self,
        selected_root: impl AsRef<Path>,
    ) -> Result<LibraryRootCapability, CapabilityError> {
        let canonical = selected_root
            .as_ref()
            .canonicalize()
            .map_err(|_| CapabilityError::selected_root_unavailable())?;

        if !canonical.is_absolute() || !canonical.is_dir() {
            return Err(CapabilityError::selected_root_not_directory());
        }

        let id = Uuid::new_v4();
        let descriptor = LibraryRootCapability {
            capability_id: format!("{CAPABILITY_PREFIX}{}", id.simple()),
            display_name: Self::safe_display_name(&canonical),
        };

        self.roots
            .lock()
            .map_err(|_| CapabilityError::registry_unavailable())?
            .insert(id, CapabilityRecord { root: canonical });

        Ok(descriptor)
    }

    fn resolve_library_root(&self, capability_id: &str) -> Result<PathBuf, CapabilityError> {
        let id = Self::parse_id(capability_id)?;
        let roots = self
            .roots
            .lock()
            .map_err(|_| CapabilityError::registry_unavailable())?;

        roots
            .get(&id)
            .map(|record| record.root.clone())
            .ok_or_else(CapabilityError::unknown_id)
    }

    pub(crate) fn resolve_for_import(
        &self,
        capability_id: &str,
    ) -> Result<PathBuf, DesktopHostError> {
        self.resolve_library_root(capability_id)
            .map_err(DesktopHostError::from)
    }
}

#[tauri::command]
pub async fn library_choose_root(
    app: AppHandle,
    registry: State<'_, LibraryCapabilityRegistry>,
) -> Result<Option<LibraryRootCapability>, DesktopHostError> {
    let Some(selected) = app.dialog().file().blocking_pick_folder() else {
        return Ok(None);
    };

    let selected_path = selected
        .into_path()
        .map_err(|_| DesktopHostError::from(CapabilityError::selected_root_unavailable()))?;

    let capability = registry
        .issue_selected_root(selected_path)
        .map_err(DesktopHostError::from)?;

    registry
        .resolve_library_root(&capability.capability_id)
        .map_err(DesktopHostError::from)?;

    Ok(Some(capability))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    struct TestDirectory {
        path: PathBuf,
    }

    impl TestDirectory {
        fn new(label: &str) -> Self {
            let path = std::env::temp_dir().join(format!(
                "applaylist-library-capability-{label}-{}",
                Uuid::new_v4().simple()
            ));
            fs::create_dir_all(&path).expect("create test directory");
            Self { path }
        }
    }

    impl Drop for TestDirectory {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.path);
        }
    }

    #[test]
    fn issued_capability_is_session_scoped_and_opaque() {
        let directory = TestDirectory::new("session");
        let registry = LibraryCapabilityRegistry::default();

        let capability = registry
            .issue_selected_root(&directory.path)
            .expect("issue capability");
        let resolved = registry
            .resolve_library_root(&capability.capability_id)
            .expect("resolve capability");

        assert_eq!(
            resolved,
            directory.path.canonicalize().expect("canonical test root")
        );
        assert!(capability.capability_id.starts_with(CAPABILITY_PREFIX));
        assert_eq!(capability.capability_id.len(), CAPABILITY_PREFIX.len() + 32);
        assert_eq!(
            capability.display_name,
            directory.path.file_name().unwrap().to_string_lossy()
        );
        assert!(!capability.capability_id.contains('/'));
        assert!(!capability.capability_id.contains('\\'));

        let fresh_session = LibraryCapabilityRegistry::default();
        let error = fresh_session
            .resolve_library_root(&capability.capability_id)
            .expect_err("capability must not cross sessions");
        assert_eq!(error.code, "unknown_library_root_capability");
    }

    #[test]
    fn forged_well_formed_capability_is_rejected() {
        let registry = LibraryCapabilityRegistry::default();
        let forged = format!("{CAPABILITY_PREFIX}{}", Uuid::new_v4().simple());

        let error = registry
            .resolve_library_root(&forged)
            .expect_err("forged capability must fail closed");

        assert_eq!(error.code, "unknown_library_root_capability");
    }

    #[test]
    fn path_shaped_inputs_are_not_capabilities() {
        let registry = LibraryCapabilityRegistry::default();
        for raw in [
            "/Users/example/Music",
            "../../Music",
            "C:\\Music",
            "file:///Users/example/Music",
            "lrc_/Users/example/Music",
            "lrc_../../Music",
        ] {
            let error = registry
                .resolve_library_root(raw)
                .expect_err("path-shaped input must fail closed");
            assert_eq!(error.code, "invalid_library_root_capability", "{raw}");
        }
    }

    #[test]
    fn arbitrary_absolute_path_cannot_be_resolved_as_root() {
        let registry = LibraryCapabilityRegistry::default();
        let error = registry
            .resolve_library_root("/tmp/renderer-controlled-library")
            .expect_err("absolute path must never become renderer filesystem authority");

        assert_eq!(error.code, "invalid_library_root_capability");
    }

    #[test]
    fn selected_file_is_rejected_as_library_root() {
        let directory = TestDirectory::new("file");
        let file = directory.path.join("track.mp3");
        fs::write(&file, b"boundary test only").expect("write test file");

        let registry = LibraryCapabilityRegistry::default();
        let error = registry
            .issue_selected_root(&file)
            .expect_err("regular file must not become root capability");

        assert_eq!(error.code, "selected_library_root_not_directory");
    }

    #[test]
    fn renderer_descriptor_contains_no_absolute_path() {
        let directory = TestDirectory::new("redaction");
        let registry = LibraryCapabilityRegistry::default();

        let capability = registry
            .issue_selected_root(&directory.path)
            .expect("issue capability");
        let absolute = directory
            .path
            .canonicalize()
            .expect("canonical test root")
            .to_string_lossy()
            .into_owned();

        assert_ne!(capability.display_name, absolute);
        assert!(!capability.capability_id.contains(&absolute));
        assert!(!capability.display_name.contains(&absolute));
    }

    #[test]
    fn canonical_root_is_stored_only_in_registry() {
        let directory = TestDirectory::new("canonical");
        let nested = directory.path.join("nested");
        fs::create_dir_all(&nested).expect("create nested directory");

        let registry = LibraryCapabilityRegistry::default();
        let capability = registry
            .issue_selected_root(&nested)
            .expect("issue capability");
        let resolved = registry
            .resolve_library_root(&capability.capability_id)
            .expect("resolve capability");

        assert!(resolved.is_absolute());
        assert_eq!(
            resolved,
            nested.canonicalize().expect("canonical nested path")
        );
        assert!(resolved.is_dir());
        assert_eq!(capability.display_name, "nested");
    }
    #[test]
    #[ignore = "requires APPLAYLIST_TEST_SIDECAR_EXECUTABLE"]
    fn authenticated_sidecar_import_uses_resolved_capability_and_safe_dto() {
        let executable = std::env::var_os("APPLAYLIST_TEST_SIDECAR_EXECUTABLE")
            .expect("APPLAYLIST_TEST_SIDECAR_EXECUTABLE is required");
        let directory = TestDirectory::new("sidecar-import");
        fs::write(directory.path.join("notes.txt"), b"not audio").expect("write unsupported file");
        let registry = LibraryCapabilityRegistry::default();
        let capability = registry
            .issue_selected_root(&directory.path)
            .expect("issue capability");
        let root = registry
            .resolve_for_import(&capability.capability_id)
            .expect("resolve capability for import");
        let bridge = crate::sidecar_bridge::SidecarBridge::for_executable(executable);
        let result = bridge
            .import_root(&root)
            .expect("authenticated sidecar import");
        let encoded = serde_json::to_string(&result).expect("serialize safe renderer dto");
        let absolute = directory
            .path
            .canonicalize()
            .expect("canonical test root")
            .to_string_lossy()
            .into_owned();

        assert_eq!(
            result.folder_name,
            directory.path.file_name().unwrap().to_string_lossy()
        );
        assert_eq!(result.counts.discovered_entries, 1);
        assert_eq!(result.counts.accepted, 0);
        assert_eq!(result.counts.imported, 0);
        assert_eq!(result.counts.persisted, 0);
        assert!(result.tracks.is_empty());
        assert_eq!(result.issues.len(), 1);
        assert_eq!(result.issues[0].file_name.as_deref(), Some("notes.txt"));
        assert!(!encoded.contains(&absolute));
    }
}
