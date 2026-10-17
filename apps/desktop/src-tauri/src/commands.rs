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
    crate::settings::with(|settings| settings.update(&values, &secrets))
        .ok_or_else(|| String::from("Settings are not available."))?
        .map_err(|problems| problems.join(" "))?;
    let Some(dir) = crate::engine::engine_dir() else {
        return Ok(vec![String::from(
            "Saved. The engine folder is not configured, so it was not restarted.",
        )]);
    };
    let problems = crate::engine::uv_run(&dir, "recall-check-config")
        .output()
        .ok()
        .and_then(|output| serde_json::from_slice::<serde_json::Value>(&output.stdout).ok())
        .and_then(|reply| reply.get("problems").cloned())
        .and_then(|problems| serde_json::from_value::<Vec<String>>(problems).ok())
        .unwrap_or_else(|| vec![String::from("The settings could not be checked.")]);
    restart_engine(&app, &dir)?;
    Ok(problems)
}

/// Tries every configured outside service and the AI provider once with the
/// saved settings; returns one `{service, ok, detail}` entry per service.
///
/// # Errors
/// Returns a user-facing message if the check could not run.
#[tauri::command(async)]
pub fn check_connections() -> Result<Vec<serde_json::Value>, String> {
    let dir = crate::engine::engine_dir()
        .ok_or_else(|| String::from("The engine folder is not configured."))?;
    let output = crate::engine::uv_run(&dir, "recall-check-connections")
        .output()
        .map_err(|error| format!("Could not start the connection test: {error}"))?;
    serde_json::from_slice::<serde_json::Value>(&output.stdout)
        .ok()
        .and_then(|reply| reply.get("results").cloned())
        .and_then(|results| serde_json::from_value(results).ok())
        .ok_or_else(|| String::from("The connection test ended without an answer."))
}

/// A diagnostics report for a bug report: the app's version, then the
/// engine's report (settings without secret values, problems, recent log
/// lines with personal data removed).
///
/// # Errors
/// Returns a user-facing message if the report could not be made.
#[tauri::command(async)]
pub fn diagnostics() -> Result<String, String> {
    let dir = crate::engine::engine_dir()
        .ok_or_else(|| String::from("The engine folder is not configured."))?;
    let output = crate::engine::uv_run(&dir, "recall-diagnostics")
        .output()
        .map_err(|error| format!("Could not make the diagnostics report: {error}"))?;
    if !output.status.success() {
        return Err(String::from("The diagnostics report could not be made."));
    }
    Ok(format!(
        "Recall desktop {} ({} {})\n\n{}",
        env!("CARGO_PKG_VERSION"),
        std::env::consts::OS,
        std::env::consts::ARCH,
        String::from_utf8_lossy(&output.stdout)
    ))
}

/// Restarts the engine with the saved settings (or stops it under auto-start).
fn restart_engine(app: &tauri::AppHandle, dir: &std::path::Path) -> Result<(), String> {
    use tauri::Manager;

    let slot = app.state::<crate::engine::EngineSlot>();
    if crate::autostart::enabled() {
        // Auto-start: the engine runs only during calls; the supervisor starts it.
        slot.stop();
        return Ok(());
    }
    slot.restart(dir)
        .map_err(|error| format!("Saved, but the engine could not be restarted: {error}"))
}

/// Connects Google: opens the consent page in the browser and, once the user
/// agrees, stores the refresh token in the Keychain and restarts the engine.
///
/// Uses the saved Google client ID and secret. The token never reaches the webview.
///
/// # Errors
/// Returns a user-facing message if consent fails or the token cannot be saved.
#[tauri::command(async)]
pub fn google_connect(app: tauri::AppHandle) -> Result<String, String> {
    let dir = crate::engine::engine_dir()
        .ok_or_else(|| String::from("The engine folder is not configured."))?;
    let output = crate::engine::uv_run(&dir, "recall-google-login")
        .output()
        .map_err(|error| format!("Could not start the Google sign-in: {error}"))?;
    let reply: serde_json::Value = serde_json::from_slice(&output.stdout)
        .map_err(|_| String::from("The Google sign-in ended without an answer."))?;
    if let Some(error) = reply.get("error").and_then(serde_json::Value::as_str) {
        return Err(error.to_owned());
    }
    let token = reply
        .get("refresh_token")
        .and_then(serde_json::Value::as_str)
        .ok_or_else(|| String::from("Google returned no refresh token."))?;
    crate::settings::with(|settings| settings.set_secret("GOOGLE_REFRESH_TOKEN", token))
        .ok_or_else(|| String::from("Settings are not available."))?
        .map_err(|problems| problems.join(" "))?;
    restart_engine(&app, &dir)?;
    Ok(String::from("Google is connected."))
}

/// Whether the engine is running, for the app's start/stop button.
#[tauri::command]
pub fn engine_running(slot: tauri::State<'_, crate::engine::EngineSlot>) -> bool {
    slot.running()
}

/// Starts the engine by hand (or restarts it if it is running).
///
/// # Errors
/// Returns a user-facing message if the engine folder is unknown or it cannot start.
#[tauri::command(async)]
pub fn engine_start(app: tauri::AppHandle) -> Result<(), String> {
    use tauri::Manager;

    let dir = crate::engine::engine_dir()
        .ok_or_else(|| String::from("The engine folder is not configured."))?;
    app.state::<crate::engine::EngineSlot>()
        .restart(&dir)
        .map_err(|error| format!("The engine could not be started: {error}"))
}

/// Stops the engine: nothing is heard or recorded until it is started again.
#[tauri::command(async)]
pub fn engine_stop(slot: tauri::State<'_, crate::engine::EngineSlot>) {
    slot.stop();
}
