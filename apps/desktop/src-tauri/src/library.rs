// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

//! Tauri commands for the meeting library: past meetings' notes and recordings.
//!
//! The work is done by the engine's `recall-library` command, which only
//! reads notes inside the configured notes folder. A recording becomes
//! playable in the webview only after that command named it for the meeting
//! being shown; nothing else on disk is exposed.

use std::path::Path;

use serde_json::Value;
use tauri::{AppHandle, Manager};

use crate::engine;

/// Longest search text passed to the engine.
pub const MAX_QUERY_CHARS: usize = 200;

/// Whether `path` may be handed to the engine as a notes file path.
///
/// It must be absolute, so it can never be read as a command-line option, and
/// contain no NUL. The engine still checks that it lies inside the notes folder.
pub fn is_notes_path(path: &str) -> bool {
    Path::new(path).is_absolute() && !path.contains('\0')
}

/// Runs `recall-library <args>` and returns its JSON, turning `{"error"}` into `Err`.
fn library(args: &[&str]) -> Result<Value, String> {
    let dir =
        engine::engine_dir().ok_or_else(|| String::from("The engine folder is not configured."))?;
    let output = engine::uv_run(&dir, "recall-library")
        .args(args)
        .output()
        .map_err(|error| format!("Could not run the library command: {error}"))?;
    let value: Value = serde_json::from_slice(&output.stdout).map_err(|_| {
        let message = String::from_utf8_lossy(&output.stderr);
        message
            .lines()
            .last()
            .unwrap_or("The library command failed.")
            .to_owned()
    })?;
    if let Some(error) = value.get("error").and_then(Value::as_str) {
        return Err(error.to_owned());
    }
    Ok(value)
}

/// Lets the webview play the recording named in `meeting`, if there is one.
fn allow_recording(app: &AppHandle, meeting: &Value) -> Result<(), String> {
    if let Some(audio) = meeting.get("audio").and_then(Value::as_str) {
        app.asset_protocol_scope()
            .allow_file(audio)
            .map_err(|error| format!("Could not open the recording: {error}"))?;
    }
    Ok(())
}

/// Lists past meetings, newest first. Read-only.
///
/// # Errors
/// Returns a user-facing message if the notes folder is not set or unreadable.
#[tauri::command(async)]
pub fn library_list() -> Result<Value, String> {
    library(&["list"])
}

/// Finds transcript lines containing `query` across all meetings. Read-only.
///
/// # Errors
/// Returns a user-facing message for an empty or overlong query, or if the
/// search cannot run.
#[tauri::command(async)]
pub fn library_search(query: String) -> Result<Value, String> {
    let query = query.trim();
    if query.is_empty() || query.chars().count() > MAX_QUERY_CHARS || query.contains('\0') {
        return Err(format!("Search for 1-{MAX_QUERY_CHARS} characters."));
    }
    library(&["search", "--", query])
}

/// Opens one meeting (lines, summary, recording) and makes its recording playable.
///
/// # Errors
/// Returns a user-facing message if `path` is not a notes file in the folder.
#[tauri::command(async)]
pub fn library_show(app: AppHandle, path: String) -> Result<Value, String> {
    if !is_notes_path(&path) {
        return Err(String::from("That is not a meeting in the library."));
    }
    let meeting = library(&["show", "--", &path])?;
    allow_recording(&app, &meeting)?;
    Ok(meeting)
}

/// Summarises one meeting with the configured AI model and saves it in the notes.
///
/// Sends the transcript to the AI provider the user configured; runs only
/// when the user presses the button.
///
/// # Errors
/// Returns a user-facing message if no model is configured or it fails.
#[tauri::command(async)]
pub fn library_summarize(app: AppHandle, path: String) -> Result<Value, String> {
    if !is_notes_path(&path) {
        return Err(String::from("That is not a meeting in the library."));
    }
    let meeting = library(&["summarize", "--", &path])?;
    allow_recording(&app, &meeting)?;
    Ok(meeting)
}

#[cfg(test)]
mod tests {
    use super::is_notes_path;

    #[test]
    fn accepts_absolute_paths() {
        assert!(is_notes_path("/Users/ana/notes/2026-10-14 Meeting.md"));
    }

    #[test]
    fn rejects_relative_paths_options_and_nul() {
        for bad in ["notes/a.md", "--help", "-x", "", "/tmp/a\0.md"] {
            assert!(!is_notes_path(bad), "{bad:?} should be rejected");
        }
    }
}
