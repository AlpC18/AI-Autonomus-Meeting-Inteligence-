// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

//! Lifecycle of the Python engine process that the desktop app runs.
//!
//! The app starts the engine on launch and stops it on exit. The engine is
//! told to quit when its standard input closes, and this module keeps that
//! pipe open for as long as the app lives. If the app dies in any way, the
//! operating system closes the pipe and the engine stops recording by itself.

use std::io;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Mutex, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

/// How long [`EngineProcess::shutdown`] waits for a clean exit before killing.
pub const SHUTDOWN_GRACE: Duration = Duration::from_secs(5);

const POLL_INTERVAL: Duration = Duration::from_millis(50);

/// A running engine child process owned by the desktop app.
///
/// Dropping it shuts the engine down, so the engine cannot outlive this value.
pub struct EngineProcess {
    child: Mutex<Option<Child>>,
}

impl EngineProcess {
    /// Starts the engine found in `engine_dir` with `uv run continuum-engine`.
    ///
    /// Settings are read from `engine_dir/.env` when that file exists. The
    /// engine's log output goes to the app's own standard output and error.
    ///
    /// # Errors
    /// Returns the underlying I/O error if `uv` is not installed or
    /// `engine_dir` does not exist.
    pub fn spawn(engine_dir: &Path) -> io::Result<Self> {
        let mut command = Command::new("uv");
        command.arg("run");
        if engine_dir.join(".env").is_file() {
            command.args(["--env-file", ".env"]);
        }
        command
            .arg("continuum-engine")
            .current_dir(engine_dir)
            .env("CONTINUUM_EXIT_ON_STDIN_EOF", "1");
        Self::spawn_command(command)
    }

    /// Starts `command` with a piped standard input that is held open.
    ///
    /// # Errors
    /// Returns the I/O error from the operating system if the program cannot
    /// be started.
    pub fn spawn_command(mut command: Command) -> io::Result<Self> {
        let child = command.stdin(Stdio::piped()).spawn()?;
        Ok(Self {
            child: Mutex::new(Some(child)),
        })
    }

    /// Stops the engine, waiting up to `grace` for it to exit on its own.
    ///
    /// Closes the engine's standard input, which asks it to stop. If it is
    /// still running after `grace`, it is killed. Safe to call more than once;
    /// later calls do nothing. Returns `true` if the process exited by itself
    /// and `false` if it had to be killed or was already stopped.
    pub fn shutdown(&self, grace: Duration) -> bool {
        let taken = self
            .child
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .take();
        let Some(mut child) = taken else {
            return false;
        };
        drop(child.stdin.take());

        let deadline = Instant::now() + grace;
        while Instant::now() < deadline {
            match child.try_wait() {
                Ok(Some(_)) => return true,
                Ok(None) => thread::sleep(POLL_INTERVAL),
                Err(_) => break,
            }
        }
        // Best effort: if kill or wait fail the process is already gone.
        let _ = child.kill();
        let _ = child.wait();
        false
    }
}

impl Drop for EngineProcess {
    fn drop(&mut self) {
        self.shutdown(SHUTDOWN_GRACE);
    }
}

/// Finds the engine directory to run, if any.
///
/// `CONTINUUM_ENGINE_DIR` wins when set. Otherwise development builds use the
/// `engine/` folder of the repository they were compiled from. Release builds
/// return `None` unless the variable is set, because the engine is not yet
/// bundled with the app.
pub fn engine_dir() -> Option<PathBuf> {
    if let Some(dir) = std::env::var_os("CONTINUUM_ENGINE_DIR") {
        return Some(PathBuf::from(dir));
    }
    if cfg!(debug_assertions) {
        return Some(Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../engine"));
    }
    None
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;

    #[test]
    fn process_that_honours_closed_stdin_exits_on_its_own() {
        let engine = EngineProcess::spawn_command(Command::new("cat")).expect("spawn cat");

        assert!(engine.shutdown(Duration::from_secs(5)));
    }

    #[test]
    fn process_that_ignores_closed_stdin_is_killed_after_the_grace_period() {
        let mut command = Command::new("sleep");
        command.arg("30");
        let engine = EngineProcess::spawn_command(command).expect("spawn sleep");
        let started = Instant::now();

        assert!(!engine.shutdown(Duration::from_millis(200)));
        assert!(started.elapsed() < Duration::from_secs(5));
    }

    #[test]
    fn shutdown_twice_is_harmless() {
        let engine = EngineProcess::spawn_command(Command::new("cat")).expect("spawn cat");
        engine.shutdown(Duration::from_secs(5));

        assert!(!engine.shutdown(Duration::from_secs(5)));
    }

    #[test]
    fn missing_program_is_reported_as_an_error() {
        assert!(EngineProcess::spawn_command(Command::new("continuum-no-such-program")).is_err());
    }
}
