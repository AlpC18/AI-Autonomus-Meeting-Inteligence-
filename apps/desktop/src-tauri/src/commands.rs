// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

//! Tauri commands callable from the React frontend.
//!
//! Commands here stay thin: they translate between the webview and the Rust
//! side and hold no audio, memory, or action logic.

use serde::Serialize;

/// Identity of the running desktop build, shown by the shell window.
///
/// Values are baked in at compile time from `Cargo.toml`, so they always match
/// the binary and cannot fail to load.
#[derive(Debug, Serialize)]
pub struct AppInfo {
    /// Cargo package name of the desktop crate.
    pub name: &'static str,
    /// Semantic version of the desktop crate.
    pub version: &'static str,
}

/// Returns the name and version of the running desktop build.
///
/// Invoked from the frontend as `invoke("app_info")`. Pure and side-effect
/// free; it never errors and performs no I/O.
#[tauri::command]
pub fn app_info() -> AppInfo {
    AppInfo {
        name: env!("CARGO_PKG_NAME"),
        version: env!("CARGO_PKG_VERSION"),
    }
}

/// Returns the settings screen's data: fields, current values, and which
/// secrets are set. Secret values themselves are never returned.
///
/// # Errors
/// Returns a message if the settings could not be loaded at startup.
#[tauri::command]
pub fn get_settings() -> Result<serde_json::Value, String> {
    crate::settings::with(|settings| settings.view())
        .ok_or_else(|| String::from("Settings are not available."))
}

/// Saves the user's settings, checks them with the engine and restarts it.
///
/// `values` replaces all ordinary settings; each entry of `secrets` sets or
/// (when empty) deletes one secret in the Keychain. Returns the engine's list
/// of configuration problems (empty when everything is fine).
///
/// # Errors
/// Returns every invalid or unknown setting; nothing is saved then.
#[tauri::command(async)]
pub fn save_settings(
    app: tauri::AppHandle,
    values: std::collections::BTreeMap<String, String>,
    secrets: std::collections::BTreeMap<String, String>,
) -> Result<Vec<String>, String> {
    use tauri::Manager;

    crate::settings::with(|settings| settings.update(&values, &secrets))
        .ok_or_else(|| String::from("Settings are not available."))?
        .map_err(|problems| problems.join(" "))?;
    let Some(dir) = crate::engine::engine_dir() else {
        return Ok(vec![String::from(
            "Saved. The engine folder is not configured, so it was not restarted.",
        )]);
    };
    let problems = crate::engine::uv_run(&dir, "continuum-check-config")
        .output()
        .ok()
        .and_then(|output| serde_json::from_slice::<serde_json::Value>(&output.stdout).ok())
        .and_then(|reply| reply.get("problems").cloned())
        .and_then(|problems| serde_json::from_value::<Vec<String>>(problems).ok())
        .unwrap_or_else(|| vec![String::from("The settings could not be checked.")]);
    let slot = app.state::<crate::engine::EngineSlot>();
    if crate::autostart::enabled() {
        // Auto-start: the engine runs only during calls; the supervisor starts it.
        slot.stop();
    } else {
        slot.restart(&dir)
            .map_err(|error| format!("Saved, but the engine could not be restarted: {error}"))?;
    }
    Ok(problems)
}
