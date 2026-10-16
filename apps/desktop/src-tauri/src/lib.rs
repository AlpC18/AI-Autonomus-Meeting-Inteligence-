// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

//! Desktop shell for Project Continuum.
//!
//! Builds the Tauri application, registers frontend-callable commands, and
//! runs the Python engine for as long as the app is open. All behaviour lives
//! in dedicated modules; this file only wires them up.

pub mod commands;
pub mod engine;

use tauri::{Manager, RunEvent, WindowEvent};

use engine::{EngineProcess, SHUTDOWN_GRACE};

/// Starts the engine and hands it to Tauri's state so it lives with the app.
///
/// A failure to start is reported on standard error and the app continues:
/// the window then shows that the engine is not running and keeps retrying.
fn start_engine(app: &tauri::App) {
    let Some(dir) = engine::engine_dir() else {
        eprintln!("Continuum engine not started: set CONTINUUM_ENGINE_DIR to its folder.");
        return;
    };
    match EngineProcess::spawn(&dir) {
        Ok(process) => {
            app.manage(process);
        }
        Err(error) => eprintln!(
            "Continuum engine could not be started from {}: {error}",
            dir.display()
        ),
    }
}

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
        .setup(|app| {
            start_engine(app);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            // The overlay window is usually hidden, so the app must quit with
            // the main window or it would keep running, and recording, unseen.
            if let RunEvent::WindowEvent {
                label,
                event: WindowEvent::Destroyed,
                ..
            } = &event
                && label == "main"
            {
                app.exit(0);
            }
            if let RunEvent::Exit = event
                && let Some(process) = app.try_state::<EngineProcess>()
            {
                process.shutdown(SHUTDOWN_GRACE);
            }
        });
}
