#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct PlatformInfo {
    os: &'static str,
    arch: &'static str,
    debug: bool,
    app_version: String,
}

#[derive(Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DaemonSession {
    url: String,
    token: String,
    #[serde(default)]
    pid: u32,
    #[serde(default)]
    version: u32,
    #[serde(default, alias = "product_version")]
    product_version: String,
}

const SESSION_FILE: &str = "daemon-session.json";
const LOOPBACK_PREFIXES: [&str; 3] = ["http://127.0.0.1:", "http://localhost:", "http://[::1]:"];

fn validate_session(raw: &[u8]) -> Result<DaemonSession, String> {
    if raw.len() > 64 * 1024 {
        return Err("daemon session file is too large".into());
    }
    let session: DaemonSession =
        serde_json::from_slice(raw).map_err(|e| format!("invalid daemon session: {e}"))?;
    if !LOOPBACK_PREFIXES
        .iter()
        .any(|prefix| session.url.starts_with(prefix))
    {
        return Err("daemon url is not a loopback address".into());
    }
    if session.token.is_empty() || session.token.len() > 512 {
        return Err("daemon session token is invalid".into());
    }
    Ok(session)
}

fn read_session_file(path: &Path) -> Result<DaemonSession, String> {
    if path.file_name().and_then(|n| n.to_str()) != Some(SESSION_FILE) {
        return Err("unexpected daemon session file name".into());
    }
    let raw = std::fs::read(path).map_err(|e| format!("cannot read daemon session: {e}"))?;
    validate_session(&raw)
}

#[tauri::command]
fn platform_info() -> PlatformInfo {
    PlatformInfo {
        os: std::env::consts::OS,
        arch: std::env::consts::ARCH,
        debug: cfg!(debug_assertions),
        app_version: env!("CARGO_PKG_VERSION").to_string(),
    }
}

#[tauri::command]
fn read_daemon_session(session_path: String) -> Result<DaemonSession, String> {
    let path = PathBuf::from(&session_path);
    if !path.is_absolute() {
        return Err("session path must be absolute".into());
    }
    read_session_file(&path)
}

#[tauri::command]
fn discover_daemon_session(repo_root: String) -> Result<DaemonSession, String> {
    let root = PathBuf::from(&repo_root);
    if !root.is_absolute() {
        return Err("repository root must be absolute".into());
    }
    read_session_file(&root.join(".astra").join("state").join(SESSION_FILE))
}

#[tauri::command]
fn reveal_path(path: String) -> Result<(), String> {
    let target = PathBuf::from(&path);
    if !target.is_absolute() {
        return Err("path must be absolute".into());
    }
    if !target.exists() {
        return Err("path does not exist".into());
    }
    #[cfg(target_os = "windows")]
    let spawned = std::process::Command::new("explorer")
        .arg(format!("/select,{}", target.display()))
        .spawn();
    #[cfg(target_os = "macos")]
    let spawned = std::process::Command::new("open").arg(&target).spawn();
    #[cfg(target_os = "linux")]
    let spawned = std::process::Command::new("xdg-open").arg(&target).spawn();
    #[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
    let spawned: std::io::Result<std::process::Child> =
        Err(std::io::Error::other("unsupported platform"));
    spawned.map_err(|e| e.to_string())?;
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            platform_info,
            read_daemon_session,
            discover_daemon_session,
            reveal_path
        ])
        .run(tauri::generate_context!())
        .expect("AstraVCS desktop runtime failed")
}
