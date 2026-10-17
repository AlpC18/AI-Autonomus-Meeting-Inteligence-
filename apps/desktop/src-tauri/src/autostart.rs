// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

//! Auto-start: listen only while a call is going on.
//!
//! With the "Start when a call begins" setting on, the engine is not started
//! with the app. Instead the engine's `recall-detect-call` watcher reports
//! when another app (Zoom, Meet, Teams, ...) uses the microphone. After
//! [`CALL_CONFIRM`] of that, the engine starts, set to end the meeting and
//! stop itself after a silence; then watching resumes.

use std::io::{BufRead, BufReader};
use std::process::{Child, Stdio};
use std::sync::mpsc::{self, Receiver};
use std::thread;
use std::time::{Duration, Instant};

use serde_json::Value;
use tauri::{AppHandle, Manager};

use crate::engine::{self, EngineSlot};

/// The setting that turns auto-start on.
pub const SETTING: &str = "RECALL_AUTO_START";

/// How long the microphone must be in use before the engine starts.
pub const CALL_CONFIRM: Duration = Duration::from_secs(5);

/// Silence after which an auto-started meeting ends, unless the user set one.
pub const DEFAULT_IDLE_MINUTES: &str = "3";

const TICK: Duration = Duration::from_millis(500);

/// Whether auto-start is turned on in the settings.
pub fn enabled() -> bool {
    engine::settings_value(SETTING).as_deref() == Some("1")
}

/// What the supervisor should do, given what it currently sees.
#[derive(Debug, PartialEq, Eq)]
pub enum Step {
    /// Nothing to do.
    Wait,
    /// Start the call watcher.
    Watch,
    /// Stop the call watcher (auto-start was turned off, or the engine runs).
    StopWatching,
    /// A call is confirmed: start the engine.
    StartEngine,
}

/// Decides the next step. `call_since` is when the microphone came into use, if it is.
pub fn decide(
    enabled: bool,
    engine_running: bool,
    watching: bool,
    call_since: Option<Instant>,
    now: Instant,
) -> Step {
    if !enabled || engine_running {
        return if watching {
            Step::StopWatching
        } else {
            Step::Wait
        };
    }
    if !watching {
        return Step::Watch;
    }
    match call_since {
        Some(since) if now.duration_since(since) >= CALL_CONFIRM => Step::StartEngine,
        _ => Step::Wait,
    }
}

/// The running `recall-detect-call` process and its reported states.
struct Watcher {
    child: Child,
    states: Receiver<bool>,
}

impl Watcher {
    fn start() -> Option<Self> {
        let dir = engine::engine_dir()?;
        let mut child = engine::uv_run(&dir, "recall-detect-call")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .ok()?;
        let stdout = child.stdout.take()?;
        let (sender, states) = mpsc::channel();
        thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                let state = serde_json::from_str::<Value>(&line)
                    .ok()
                    .and_then(|value| value.get("in_call").and_then(Value::as_bool));
                if let Some(state) = state
                    && sender.send(state).is_err()
                {
                    break;
                }
            }
        });
        Some(Self { child, states })
    }

    fn stop(mut self) {
        drop(self.child.stdin.take());
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// Runs the auto-start supervisor in the background for the app's lifetime.
pub fn supervise(app: AppHandle) {
    thread::spawn(move || {
        let mut watcher: Option<Watcher> = None;
        let mut call_since: Option<Instant> = None;
        loop {
            if let Some(active) = &watcher {
                for in_call in active.states.try_iter() {
                    call_since = if in_call {
                        call_since.or(Some(Instant::now()))
                    } else {
                        None
                    };
                }
            }
            let slot = app.state::<EngineSlot>();
            let step = decide(
                enabled(),
                slot.running(),
                watcher.is_some(),
                call_since,
                Instant::now(),
            );
            match step {
                Step::Wait => {}
                Step::Watch => {
                    watcher = Watcher::start();
                    call_since = None;
                }
                Step::StopWatching => {
                    if let Some(active) = watcher.take() {
                        active.stop();
                    }
                }
                Step::StartEngine => {
                    if let Some(active) = watcher.take() {
                        active.stop();
                    }
                    call_since = None;
                    if let Some(dir) = engine::engine_dir() {
                        let idle = engine::settings_value("RECALL_IDLE_END_MINUTES")
                            .unwrap_or_else(|| DEFAULT_IDLE_MINUTES.to_owned());
                        let extra = [
                            ("RECALL_EXIT_WHEN_IDLE", "1"),
                            ("RECALL_IDLE_END_MINUTES", idle.as_str()),
                        ];
                        if let Err(error) = slot.restart_with(&dir, &extra) {
                            eprintln!("Auto-start could not start the engine: {error}");
                        }
                    }
                }
            }
            thread::sleep(TICK);
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn watches_only_while_enabled_and_idle() {
        let now = Instant::now();
        assert_eq!(decide(true, false, false, None, now), Step::Watch);
        assert_eq!(decide(false, false, true, None, now), Step::StopWatching);
        assert_eq!(decide(true, true, true, None, now), Step::StopWatching);
        assert_eq!(decide(false, true, false, None, now), Step::Wait);
    }

    #[test]
    fn a_call_must_last_before_the_engine_starts() {
        let start = Instant::now();
        assert_eq!(
            decide(
                true,
                false,
                true,
                Some(start),
                start + Duration::from_secs(2)
            ),
            Step::Wait
        );
        assert_eq!(
            decide(true, false, true, Some(start), start + CALL_CONFIRM),
            Step::StartEngine
        );
        assert_eq!(
            decide(true, false, true, None, start + CALL_CONFIRM),
            Step::Wait
        );
    }
}
