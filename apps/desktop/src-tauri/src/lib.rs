// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

//! Desktop shell for Project Continuum.
//!
//! Builds the Tauri application and registers frontend-callable commands.
//! All behaviour lives in dedicated modules; this file only wires them up.

pub mod commands;

/// Builds and runs the Tauri application until the last window closes.
///
/// # Panics
/// Panics if the Tauri runtime cannot start (for example, when the webview
/// is unavailable), since the app cannot do anything useful without it.
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![commands::app_info])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
