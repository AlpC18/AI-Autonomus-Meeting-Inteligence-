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
use std::sync::{Mutex, OnceLock, PoisonError};
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
    /// Starts the engine found in `engine_dir` with `uv run recall-engine`.
    ///
    /// Settings are read from `engine_dir/.env` when that file exists. The
    /// engine's log output goes to the app's own standard output and error.
    ///
    /// # Errors
    /// Returns the underlying I/O error if `uv` is not installed or
    /// `engine_dir` does not exist.
    pub fn spawn(engine_dir: &Path) -> io::Result<Self> {
        Self::spawn_with(engine_dir, &[])
    }

    /// Like [`EngineProcess::spawn`], with extra environment variables on top of the settings.
    ///
    /// # Errors
    /// Returns the I/O error if the engine cannot be started.
    pub fn spawn_with(engine_dir: &Path, extra: &[(&str, &str)]) -> io::Result<Self> {
        let mut command = uv_run(engine_dir, "recall-engine");
        command.env("RECALL_EXIT_ON_STDIN_EOF", "1");
        for (key, value) in extra {
            command.env(key, value);
        }
        Self::spawn_command(command)
    }

    /// Whether the engine has stopped by itself (or was already shut down).
    pub fn exited(&self) -> bool {
        self.child
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .as_mut()
            .is_none_or(|child| !matches!(child.try_wait(), Ok(None)))
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

/// Builds the command `uv run <script>` for a console script of the engine.
///
/// Runs in `engine_dir` with the settings made in the app as environment
/// variables. `engine_dir/.env` is also loaded when it exists; the app's
/// settings take precedence over it. The caller adds arguments and decides
/// how to run it.
pub fn uv_run(engine_dir: &Path, script: &str) -> Command {
    let bundle = BUNDLE
        .get()
        .filter(|bundle| bundle.engine_dir == engine_dir);
    let settings = crate::settings::engine_env();
    let mut command =
        Command::new(bundle.map_or_else(|| PathBuf::from("uv"), |bundle| bundle.uv.clone()));
    command.arg("run");
    if let Some(bundle) = bundle {
        command.args(bundle.run_args(&settings)).envs(bundle.env());
    } else if engine_dir.join(".env").is_file() {
        command.args(["--env-file", ".env"]);
    }
    command
        .arg(script)
        .current_dir(engine_dir)
        .envs(settings);
    command
}

/// The engine shipped inside a release build, with the `uv` that runs it.
///
/// On first use `uv` installs the locked Python environment into the app's
/// data folder (this needs an internet connection once); later starts reuse it.
#[derive(Debug)]
pub struct Bundle {
    /// The engine sources inside the app's resources (read-only).
    pub engine_dir: PathBuf,
    /// The bundled `uv` binary, next to the app's executable.
    pub uv: PathBuf,
    /// Writable folder for the Python environment.
    pub data_dir: PathBuf,
    /// Writable folder for downloads and caches.
    pub cache_dir: PathBuf,
}

impl Bundle {
    /// Optional engine features installed with the app, given its settings.
    ///
    /// Speaker names (PyTorch, about a gigabyte) are installed only once a
    /// Hugging Face token is set, since nothing else uses them; PyTorch has no
    /// Intel Mac build, so they are never installed there.
    pub fn extras(settings: &[(String, String)]) -> Vec<&'static str> {
        let mut extras = vec!["claude", "documents"];
        if cfg!(all(target_os = "macos", target_arch = "aarch64")) {
            extras.push("apple");
        }
        let has_token = settings
            .iter()
            .any(|(key, value)| key == "HF_TOKEN" && !value.trim().is_empty());
        if has_token && !cfg!(all(target_os = "macos", target_arch = "x86_64")) {
            extras.push("diarization");
        }
        extras
    }

    /// Arguments after `uv run`: never touch the lock file, no dev tools.
    pub fn run_args(&self, settings: &[(String, String)]) -> Vec<String> {
        let mut args = vec![String::from("--frozen"), String::from("--no-dev")];
        for extra in Self::extras(settings) {
            args.extend([String::from("--extra"), extra.to_owned()]);
        }
        args
    }

    /// Where uv and Python keep their files, all outside the read-only bundle.
    ///
    /// Python itself is a uv-managed 3.12 (what the lock file was made with),
    /// never whatever happens to be installed on the machine.
    pub fn env(&self) -> Vec<(&'static str, PathBuf)> {
        vec![
            ("UV_PYTHON", PathBuf::from("3.12")),
            ("UV_PYTHON_PREFERENCE", PathBuf::from("only-managed")),
            ("UV_PROJECT_ENVIRONMENT", self.data_dir.join("venv")),
            ("UV_PYTHON_INSTALL_DIR", self.data_dir.join("python")),
            ("UV_CACHE_DIR", self.cache_dir.join("uv")),
            ("PYTHONPYCACHEPREFIX", self.cache_dir.join("pycache")),
            ("HF_HOME", self.data_dir.join("models")),
        ]
    }
}

static BUNDLE: OnceLock<Bundle> = OnceLock::new();

/// Uses the engine bundled in `resource_dir`, if the app has one.
///
/// Returns whether a bundled engine was found. `RECALL_ENGINE_DIR` still
/// takes precedence (see [`engine_dir`]).
pub fn use_bundle(resource_dir: &Path, data_dir: &Path, cache_dir: &Path) -> bool {
    let engine_dir = resource_dir.join("engine");
    let uv = std::env::current_exe().ok().and_then(|exe| {
        exe.parent()
            .map(|dir| dir.join(if cfg!(windows) { "uv.exe" } else { "uv" }))
    });
    let (Some(uv), true) = (uv, engine_dir.join("pyproject.toml").is_file()) else {
        return false;
    };
    BUNDLE
        .set(Bundle {
            engine_dir,
            uv,
            data_dir: data_dir.to_path_buf(),
            cache_dir: cache_dir.to_path_buf(),
        })
        .is_ok()
}

/// The running engine, if any; replaced when the settings change.
#[derive(Default)]
pub struct EngineSlot(pub Mutex<Option<EngineProcess>>);

impl EngineSlot {
    /// Stops the running engine (if any) and starts a new one from `engine_dir`.
    ///
    /// # Errors
    /// Returns the I/O error if the new engine cannot be started.
    pub fn restart(&self, engine_dir: &Path) -> io::Result<()> {
        self.restart_with(engine_dir, &[])
    }

    /// Like [`EngineSlot::restart`], with extra environment variables for the new engine.
    ///
    /// # Errors
    /// Returns the I/O error if the new engine cannot be started.
    pub fn restart_with(&self, engine_dir: &Path, extra: &[(&str, &str)]) -> io::Result<()> {
        let mut slot = self.0.lock().unwrap_or_else(PoisonError::into_inner);
        if let Some(old) = slot.take() {
            old.shutdown(SHUTDOWN_GRACE);
        }
        *slot = Some(EngineProcess::spawn_with(engine_dir, extra)?);
        Ok(())
    }

    /// Whether an engine is running; forgets one that has exited.
    pub fn running(&self) -> bool {
        let mut slot = self.0.lock().unwrap_or_else(PoisonError::into_inner);
        if slot.as_ref().is_some_and(EngineProcess::exited) {
            *slot = None;
        }
        slot.is_some()
    }

    /// Stops the running engine, if any.
    pub fn stop(&self) {
        if let Some(old) = self.0.lock().unwrap_or_else(PoisonError::into_inner).take() {
            old.shutdown(SHUTDOWN_GRACE);
        }
    }
}

/// The current value of one setting, if set.
pub fn settings_value(key: &str) -> Option<String> {
    crate::settings::engine_env()
        .into_iter()
        .find_map(|(name, value)| (name == key).then_some(value))
}

/// Finds the engine directory to run, if any.
///
/// `RECALL_ENGINE_DIR` wins when set. Otherwise the engine bundled with a
/// release build is used, and development builds use the `engine/` folder of
/// the repository they were compiled from.
pub fn engine_dir() -> Option<PathBuf> {
    if let Some(dir) = std::env::var_os("RECALL_ENGINE_DIR") {
        return Some(PathBuf::from(dir));
    }
    if let Some(bundle) = BUNDLE.get() {
        return Some(bundle.engine_dir.clone());
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
    #[cfg(unix)]
    fn process_that_honours_closed_stdin_exits_on_its_own() {
        let engine = EngineProcess::spawn_command(Command::new("cat")).expect("spawn cat");

        assert!(engine.shutdown(Duration::from_secs(5)));
    }

    #[test]
    #[cfg(unix)]
    fn process_that_ignores_closed_stdin_is_killed_after_the_grace_period() {
        let mut command = Command::new("sleep");
        command.arg("30");
        let engine = EngineProcess::spawn_command(command).expect("spawn sleep");
        let started = Instant::now();

        assert!(!engine.shutdown(Duration::from_millis(200)));
        assert!(started.elapsed() < Duration::from_secs(5));
    }

    #[test]
    #[cfg(unix)]
    fn shutdown_twice_is_harmless() {
        let engine = EngineProcess::spawn_command(Command::new("cat")).expect("spawn cat");
        engine.shutdown(Duration::from_secs(5));

        assert!(!engine.shutdown(Duration::from_secs(5)));
    }

    #[test]
    fn bundled_engine_never_writes_inside_the_app() {
        let bundle = Bundle {
            engine_dir: PathBuf::from("/App.app/Contents/Resources/engine"),
            uv: PathBuf::from("/App.app/Contents/MacOS/uv"),
            data_dir: PathBuf::from("/data"),
            cache_dir: PathBuf::from("/cache"),
        };
        let args = bundle.run_args(&[]);
        assert!(args.starts_with(&[String::from("--frozen"), String::from("--no-dev")]));
        assert!(args.contains(&String::from("claude")));
        for (_, path) in bundle.env() {
            assert!(
                !path.starts_with("/App.app"),
                "{path:?} is inside the bundle"
            );
        }
        assert!(
            bundle
                .env()
                .contains(&("UV_PYTHON_PREFERENCE", PathBuf::from("only-managed")))
        );
    }

    fn setting(key: &str, value: &str) -> Vec<(String, String)> {
        vec![(key.to_owned(), value.to_owned())]
    }

    #[test]
    fn pdf_import_and_claude_are_always_installed() {
        let extras = Bundle::extras(&[]);
        assert!(extras.contains(&"claude"));
        assert!(extras.contains(&"documents"));
    }

    #[test]
    fn speaker_names_are_installed_only_with_a_hugging_face_token() {
        assert!(!Bundle::extras(&[]).contains(&"diarization"));
        assert!(!Bundle::extras(&setting("HF_TOKEN", "")).contains(&"diarization"));
        let with_token = Bundle::extras(&setting("HF_TOKEN", "hf_abc"));
        // PyTorch has no Intel Mac build, so there is nothing to install there.
        let intel_mac = cfg!(all(target_os = "macos", target_arch = "x86_64"));
        assert_eq!(with_token.contains(&"diarization"), !intel_mac);
    }

    #[test]
    fn missing_program_is_reported_as_an_error() {
        assert!(EngineProcess::spawn_command(Command::new("recall-no-such-program")).is_err());
    }
}
