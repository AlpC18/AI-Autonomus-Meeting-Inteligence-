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
