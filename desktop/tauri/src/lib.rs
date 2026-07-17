use serde::Serialize;
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    sync::{Mutex, MutexGuard},
};
use tauri::{AppHandle, State};
use tauri_plugin_dialog::DialogExt;
use uuid::Uuid;

const DESKTOP_PROTOCOL: &str = "applaylist-desktop-v1";

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct DesktopStatus {
    protocol: &'static str,
    state: &'static str,
    capability_count: usize,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct LibraryRootCapability {
    capability_id: String,
    display_name: String,
}

#[derive(Debug)]
enum CapabilityError {
    PathUnavailable,
    NotDirectory,
    RegistryUnavailable,
}

#[derive(Default)]
pub struct CapabilityRegistry {
    roots: Mutex<HashMap<String, PathBuf>>,
}

impl CapabilityRegistry {
    fn lock(&self) -> Result<MutexGuard<'_, HashMap<String, PathBuf>>, CapabilityError> {
        self.roots
            .lock()
            .map_err(|_| CapabilityError::RegistryUnavailable)
    }

    fn register(&self, selected: &Path) -> Result<LibraryRootCapability, CapabilityError> {
        let canonical = selected
            .canonicalize()
            .map_err(|_| CapabilityError::PathUnavailable)?;
        if !canonical.is_dir() {
            return Err(CapabilityError::NotDirectory);
        }

        let display_name = canonical
            .file_name()
            .and_then(|name| name.to_str())
            .filter(|name| !name.trim().is_empty())
            .unwrap_or("Selected folder")
            .to_owned();
        let capability_id = format!("libroot_{}", Uuid::new_v4().simple());

        self.lock()?
            .insert(capability_id.clone(), canonical);

        Ok(LibraryRootCapability {
            capability_id,
            display_name,
        })
    }

    fn resolve(&self, capability_id: &str) -> Result<Option<PathBuf>, CapabilityError> {
        Ok(self.lock()?.get(capability_id).cloned())
    }

    fn revoke(&self, capability_id: &str) -> Result<bool, CapabilityError> {
        Ok(self.lock()?.remove(capability_id).is_some())
    }

    fn count(&self) -> Result<usize, CapabilityError> {
        Ok(self.lock()?.len())
    }
}

#[tauri::command]
fn desktop_status(registry: State<'_, CapabilityRegistry>) -> Result<DesktopStatus, String> {
    let capability_count = registry
        .count()
        .map_err(|_| "desktop host state is unavailable".to_owned())?;
    Ok(DesktopStatus {
        protocol: DESKTOP_PROTOCOL,
        state: "host-ready",
        capability_count,
    })
}

#[tauri::command]
async fn choose_library_root(
    app: AppHandle,
    registry: State<'_, CapabilityRegistry>,
) -> Result<Option<LibraryRootCapability>, String> {
    let selected = app.dialog().file().blocking_pick_folder();
    let Some(selected) = selected else {
        return Ok(None);
    };
    let path = selected
        .into_path()
        .map_err(|_| "selected folder could not be authorized".to_owned())?;

    registry
        .register(&path)
        .map(Some)
        .map_err(|_| "selected folder could not be authorized".to_owned())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(CapabilityRegistry::default())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![desktop_status, choose_library_root])
        .run(tauri::generate_context!())
        .expect("APPLAYLIST desktop host failed to start");
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{fs, time::SystemTime};

    fn unique_path(label: &str) -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .expect("clock must be after epoch")
            .as_nanos();
        std::env::temp_dir().join(format!("applaylist-{label}-{stamp}-{}", Uuid::new_v4()))
    }

    #[test]
    fn registry_returns_opaque_capability_and_retains_canonical_path() {
        let directory = unique_path("library");
        fs::create_dir_all(&directory).expect("temporary directory must be created");
        let registry = CapabilityRegistry::default();

        let capability = registry
            .register(&directory)
            .expect("valid directory must be registered");

        assert!(capability.capability_id.starts_with("libroot_"));
        assert!(!capability.capability_id.contains(directory.to_string_lossy().as_ref()));
        assert_eq!(capability.display_name, directory.file_name().unwrap().to_string_lossy());
        assert_eq!(
            registry
                .resolve(&capability.capability_id)
                .expect("registry lookup must succeed"),
            Some(directory.canonicalize().expect("directory must canonicalize"))
        );
        assert_eq!(registry.count().expect("registry count must succeed"), 1);

        fs::remove_dir_all(directory).expect("temporary directory must be removed");
    }

    #[test]
    fn registry_generates_distinct_ids_and_supports_revocation() {
        let directory = unique_path("revoke");
        fs::create_dir_all(&directory).expect("temporary directory must be created");
        let registry = CapabilityRegistry::default();

        let first = registry.register(&directory).expect("first registration must work");
        let second = registry.register(&directory).expect("second registration must work");

        assert_ne!(first.capability_id, second.capability_id);
        assert!(registry
            .revoke(&first.capability_id)
            .expect("revocation must succeed"));
        assert_eq!(
            registry
                .resolve(&first.capability_id)
                .expect("lookup must succeed"),
            None
        );
        assert!(registry
            .resolve(&second.capability_id)
            .expect("lookup must succeed")
            .is_some());

        fs::remove_dir_all(directory).expect("temporary directory must be removed");
    }

    #[test]
    fn registry_rejects_regular_files() {
        let file = unique_path("file");
        fs::write(&file, b"not a directory").expect("temporary file must be created");
        let registry = CapabilityRegistry::default();

        assert!(matches!(
            registry.register(&file),
            Err(CapabilityError::NotDirectory)
        ));
        assert_eq!(registry.count().expect("registry count must succeed"), 0);

        fs::remove_file(file).expect("temporary file must be removed");
    }
}
