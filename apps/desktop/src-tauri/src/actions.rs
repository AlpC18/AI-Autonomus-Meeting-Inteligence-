// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

//! Tauri commands that let the user review actions the assistant proposed.
//!
//! These are the only path by which a proposed action is executed from the
//! desktop app, and they run only in response to the user pressing a button.
//! The work itself is done by the engine's `recall-actions-review` command;
//! this module passes the decision on and returns the command's JSON output.

use serde_json::Value;

use crate::engine;

/// Whether `id` has the shape of an action id (32 lowercase hex characters).
///
/// Ids are passed to a child process as an argument, so anything else is
/// refused before a process is started.
pub fn is_action_id(id: &str) -> bool {
    id.len() == 32
        && id
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

/// Runs `recall-actions-review --json <args>` and parses what it prints.
///
/// # Errors
/// Returns a message for the user if the engine folder is unknown, `uv`
/// cannot be started, the command reports a failure, or its output is not
/// valid JSON.
fn review(args: &[&str]) -> Result<Value, String> {
    let dir =
        engine::engine_dir().ok_or_else(|| String::from("The engine folder is not configured."))?;
    let output = engine::uv_run(&dir, "recall-actions-review")
        .arg("--json")
        .args(args)
        .output()
        .map_err(|error| format!("Could not run the review command: {error}"))?;
    if !output.status.success() && output.stdout.is_empty() {
        let message = String::from_utf8_lossy(&output.stderr);
        let last_line = message.lines().last().unwrap_or("unknown error");
        return Err(last_line.to_owned());
    }
    serde_json::from_slice(&output.stdout)
        .map_err(|error| format!("The review command returned unreadable output: {error}"))
}

/// Lists the actions waiting for the user's decision.
///
/// Read-only. Returns a JSON array of actions (id, kind, payload, status).
///
/// # Errors
/// Returns a user-facing message if the list cannot be read.
#[tauri::command(async)]
pub fn pending_actions() -> Result<Value, String> {
    review(&["list"])
}

/// Approves or rejects one pending action on the user's behalf.
///
/// Approving executes the action for real (for example, creates the GitHub
/// issue) exactly once; a second call for the same id fails. Returns the
/// action with its final status and result.
///
/// # Errors
/// Returns a user-facing message if `id` is malformed, the action was already
/// decided, or the review command fails to run.
#[tauri::command(async)]
pub fn decide_action(id: String, approve: bool) -> Result<Value, String> {
    if !is_action_id(&id) {
        return Err(String::from("That is not a valid action id."));
    }
    if approve {
        review(&["approve", &id, "--yes"])
    } else {
        review(&["reject", &id])
    }
}

#[cfg(test)]
mod tests {
    use super::is_action_id;

    #[test]
    fn accepts_a_32_character_lowercase_hex_id() {
        assert!(is_action_id("d6a95db036d64664911f8e533e0226fb"));
    }

    #[test]
    fn rejects_anything_else() {
        for bad in [
            "",
            "d6a95db0",
            "D6A95DB036D64664911F8E533E0226FB",
            "d6a95db036d64664911f8e533e0226f; rm",
            "--yes",
            "d6a95db036d64664911f8e533e0226fbb",
        ] {
            assert!(!is_action_id(bad), "{bad:?} should be rejected");
        }
    }
}
