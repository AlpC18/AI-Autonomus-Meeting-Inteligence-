// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

//! The user's settings: what the engine is allowed to do, configured in the app.
//!
//! Every setting is an environment variable of the engine, listed in
//! [`FIELDS`]; nothing else can be stored or passed on. Ordinary values live in
//! a JSON file readable only by the user. Secrets (API keys, tokens) live in the
//! operating system's credential store (the macOS Keychain) and are never sent
//! back to the webview: it only learns whether each secret is set.

use std::collections::BTreeMap;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock, PoisonError};

use serde_json::{Value, json};

/// Keychain service under which secrets are stored.
pub const KEYCHAIN_SERVICE: &str = "com.continuum.desktop";

/// Longest value accepted for any setting.
pub const MAX_VALUE_CHARS: usize = 2000;

/// How a setting is edited and checked.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    /// Free text (paths, ids, URLs, comma-separated lists).
    Text,
    /// A whole number of at least 1.
    Number,
    /// "1" or "0".
    Toggle,
    /// One of the listed values (the first is the default).
    Choice(&'static [&'static str]),
    /// Stored in the credential store; never shown again.
    Secret,
}

/// One setting the user can change.
#[derive(Debug)]
pub struct Field {
    /// The engine's environment variable.
    pub key: &'static str,
    pub label: &'static str,
    pub group: &'static str,
    pub kind: Kind,
    pub help: &'static str,
}

const fn field(
    key: &'static str,
    label: &'static str,
    group: &'static str,
    kind: Kind,
    help: &'static str,
) -> Field {
    Field {
        key,
        label,
        group,
        kind,
        help,
    }
}

/// Every setting, in the order shown.
pub const FIELDS: &[Field] = &[
    field(
        "CONTINUUM_NOTES_DIR",
        "Notes folder",
        "Meetings",
        Kind::Text,
        "Each meeting is saved here as Markdown (e.g. a folder in your Obsidian vault).",
    ),
    field(
        "CONTINUUM_TENANT_ID",
        "Workspace",
        "Meetings",
        Kind::Text,
        "Memory and notes are kept per workspace and project. Letters, digits, '_', '.', '-'.",
    ),
    field(
        "CONTINUUM_PROJECT_ID",
        "Project",
        "Meetings",
        Kind::Text,
        "Set both workspace and project to keep a searchable memory.",
    ),
    field(
        "CONTINUUM_SOURCES",
        "Listen to",
        "Meetings",
        Kind::Choice(&["mic,system", "mic", "system"]),
        "Your microphone, the other participants (system audio), or both.",
    ),
    field(
        "CONTINUUM_WHISPER_MODEL",
        "Speech model",
        "Meetings",
        Kind::Choice(&["base", "tiny", "small", "medium", "large-v3-turbo"]),
        "Larger is more accurate and slower.",
    ),
    field(
        "CONTINUUM_ASR_BACKEND",
        "Speech engine",
        "Meetings",
        Kind::Choice(&["auto", "faster-whisper", "mlx"]),
        "auto uses the Apple Silicon GPU when available.",
    ),
    field(
        "HF_TOKEN",
        "Hugging Face token",
        "Meetings",
        Kind::Secret,
        "Enables telling speakers apart (pyannote).",
    ),
    field(
        "CONTINUUM_REDACT",
        "Hide personal data in saved notes",
        "Privacy",
        Kind::Toggle,
        "E-mails, phone and card numbers, IBANs, keys and passwords are replaced before saving.",
    ),
    field(
        "CONTINUUM_RETENTION_DAYS",
        "Forget memories after (days)",
        "Privacy",
        Kind::Number,
        "Empty keeps everything.",
    ),
    field(
        "CONTINUUM_LLM_PROVIDER",
        "AI provider",
        "AI",
        Kind::Choice(&[
            "",
            "groq",
            "gemini",
            "openrouter",
            "mistral",
            "ollama",
            "lmstudio",
            "openai",
            "anthropic",
            "custom",
        ]),
        "Free: groq, gemini, openrouter, mistral. Local: ollama, lmstudio. Transcripts are sent to the provider you pick.",
    ),
    field(
        "CONTINUUM_LLM_MODEL",
        "AI model",
        "AI",
        Kind::Text,
        "Empty uses the provider's default (required for openrouter, lmstudio and custom).",
    ),
    field(
        "CONTINUUM_LLM_BASE_URL",
        "AI server URL",
        "AI",
        Kind::Text,
        "Only for custom, OpenAI-compatible servers.",
    ),
    field(
        "CONTINUUM_LLM_API_KEY",
        "AI API key",
        "AI",
        Kind::Secret,
        "Not needed for ollama or lmstudio.",
    ),
    field(
        "CONTINUUM_GITHUB_REPOS",
        "GitHub repositories",
        "Actions",
        Kind::Text,
        "Comma-separated owner/name; issues can only be proposed for these.",
    ),
    field(
        "GITHUB_TOKEN",
        "GitHub token",
        "Actions",
        Kind::Secret,
        "Fine-grained token with Issues: read and write.",
    ),
    field(
        "CONTINUUM_SLACK_WEBHOOK_URL",
        "Slack webhook URL",
        "Actions",
        Kind::Secret,
        "Incoming-webhook URL of the one channel messages may go to.",
    ),
    field(
        "CONTINUUM_JIRA_SITE",
        "Jira site",
        "Actions",
        Kind::Text,
        "https://your-team.atlassian.net",
    ),
    field(
        "JIRA_EMAIL",
        "Jira account e-mail",
        "Actions",
        Kind::Text,
        "",
    ),
    field(
        "JIRA_API_TOKEN",
        "Jira API token",
        "Actions",
        Kind::Secret,
        "From id.atlassian.com > Security > API tokens.",
    ),
    field(
        "CONTINUUM_JIRA_PROJECTS",
        "Jira projects",
        "Actions",
        Kind::Text,
        "Comma-separated project keys, e.g. WEB,OPS.",
    ),
    field(
        "GOOGLE_CLIENT_ID",
        "Google client ID",
        "Actions",
        Kind::Text,
        "For calendar deadlines and meeting titles.",
    ),
    field(
        "GOOGLE_CLIENT_SECRET",
        "Google client secret",
        "Actions",
        Kind::Secret,
        "",
    ),
    field(
        "GOOGLE_REFRESH_TOKEN",
        "Google refresh token",
        "Actions",
        Kind::Secret,
        "Needs the calendar.events scope.",
    ),
    field(
        "CONTINUUM_GOOGLE_CALENDAR_ID",
        "Google calendar",
        "Actions",
        Kind::Text,
        "Empty uses your primary calendar.",
    ),
];

/// Looks up a setting by its environment variable.
pub fn find(key: &str) -> Option<&'static Field> {
    FIELDS.iter().find(|field| field.key == key)
}

/// Why `value` cannot be stored for `field`, or `None` when it is fine.
///
/// The empty string always means "not set".
pub fn problem(field: &Field, value: &str) -> Option<String> {
    if value.is_empty() {
        return None;
    }
    if value.chars().count() > MAX_VALUE_CHARS || value.contains(['\0', '\n', '\r']) {
        return Some(format!(
            "{}: use one line of at most {MAX_VALUE_CHARS} characters.",
            field.label
        ));
    }
    match field.kind {
        Kind::Number
            if !value.bytes().all(|byte| byte.is_ascii_digit()) || value.starts_with('0') =>
        {
            Some(format!(
                "{}: use a whole number of at least 1.",
                field.label
            ))
        }
        Kind::Toggle if value != "1" && value != "0" => {
            Some(format!("{}: must be on or off.", field.label))
        }
        Kind::Choice(options) if !options.contains(&value) => Some(format!(
            "{}: choose one of {}.",
            field.label,
            options.join(", ")
        )),
        _ => None,
    }
}

/// Where secrets are kept. The Keychain in the app; a map in tests.
pub trait SecretStore: Send {
    /// The secret for `key`, or `None` when none is stored.
    fn get(&self, key: &str) -> Option<String>;
    /// Stores `value` for `key`, or deletes it when `value` is empty.
    ///
    /// # Errors
    /// Returns a message if the credential store refuses.
    fn set(&mut self, key: &str, value: &str) -> Result<(), String>;
}

/// The operating system's credential store (Keychain on macOS).
pub struct Keychain;

impl SecretStore for Keychain {
    fn get(&self, key: &str) -> Option<String> {
        keyring::Entry::new(KEYCHAIN_SERVICE, key)
            .ok()?
            .get_password()
            .ok()
    }

    fn set(&mut self, key: &str, value: &str) -> Result<(), String> {
        let entry = keyring::Entry::new(KEYCHAIN_SERVICE, key)
            .map_err(|error| format!("The Keychain is not available: {error}"))?;
        let result = if value.is_empty() {
            match entry.delete_credential() {
                Err(keyring::Error::NoEntry) => Ok(()),
                other => other,
            }
        } else {
            entry.set_password(value)
        };
        result.map_err(|error| format!("Could not save to the Keychain: {error}"))
    }
}

/// Settings loaded in memory: the values file plus the secrets read once.
pub struct Settings {
    path: PathBuf,
    values: BTreeMap<String, String>,
    secrets: BTreeMap<String, String>,
    store: Box<dyn SecretStore>,
}

impl Settings {
    /// Loads the values file at `path` (missing means empty) and every secret from `store`.
    ///
    /// Unknown keys and invalid values in the file are ignored.
    pub fn load(path: PathBuf, store: Box<dyn SecretStore>) -> Self {
        let stored: BTreeMap<String, String> = fs::read(&path)
            .ok()
            .and_then(|bytes| serde_json::from_slice(&bytes).ok())
            .unwrap_or_default();
        let values = stored
            .into_iter()
            .filter(|(key, value)| {
                find(key).is_some_and(|field| {
                    field.kind != Kind::Secret && problem(field, value).is_none()
                })
            })
            .collect();
        let secrets = FIELDS
            .iter()
            .filter(|field| field.kind == Kind::Secret)
            .filter_map(|field| {
                store
                    .get(field.key)
                    .map(|value| (field.key.to_owned(), value))
            })
            .collect();
        Self {
            path,
            values,
            secrets,
            store,
        }
    }

    /// The engine's environment: every value and secret that is set.
    pub fn env(&self) -> Vec<(String, String)> {
        self.values
            .iter()
            .chain(self.secrets.iter())
            .filter(|(_, value)| !value.is_empty())
            .map(|(key, value)| (key.clone(), value.clone()))
            .collect()
    }

    /// What the webview may see: the fields, the values, and which secrets are set.
    pub fn view(&self) -> Value {
        let fields: Vec<Value> = FIELDS
            .iter()
            .map(|field| {
                let (kind, options) = match field.kind {
                    Kind::Text => ("text", &[][..]),
                    Kind::Number => ("number", &[][..]),
                    Kind::Toggle => ("toggle", &[][..]),
                    Kind::Choice(options) => ("choice", options),
                    Kind::Secret => ("secret", &[][..]),
                };
                json!({"key": field.key, "label": field.label, "group": field.group,
                       "kind": kind, "options": options, "help": field.help})
            })
            .collect();
        let secrets_set: Vec<&String> = self.secrets.keys().collect();
        json!({"fields": fields, "values": self.values, "secretsSet": secrets_set})
    }

    /// Applies changes: `values` replaces ordinary settings; each entry of
    /// `secrets` sets (or, when empty, deletes) one secret. Secrets left out
    /// are unchanged.
    ///
    /// # Errors
    /// Returns every problem found; nothing is changed unless all are valid.
    pub fn update(
        &mut self,
        values: &BTreeMap<String, String>,
        secrets: &BTreeMap<String, String>,
    ) -> Result<(), Vec<String>> {
        let mut problems = Vec::new();
        for (key, value) in values {
            match find(key) {
                Some(field) if field.kind != Kind::Secret => {
                    problems.extend(problem(field, value.trim()))
                }
                _ => problems.push(format!("Unknown setting {key}.")),
            }
        }
        for (key, value) in secrets {
            match find(key) {
                Some(field) if field.kind == Kind::Secret => {
                    problems.extend(problem(field, value.trim()))
                }
                _ => problems.push(format!("Unknown secret {key}.")),
            }
        }
        if !problems.is_empty() {
            return Err(problems);
        }
        let cleaned: BTreeMap<String, String> = values
            .iter()
            .map(|(key, value)| (key.clone(), value.trim().to_owned()))
            .filter(|(_, value)| !value.is_empty())
            .collect();
        write_private(
            &self.path,
            &serde_json::to_vec_pretty(&cleaned).unwrap_or_default(),
        )
        .map_err(|error| vec![format!("Could not save settings: {error}")])?;
        self.values = cleaned;
        for (key, value) in secrets {
            let value = value.trim();
            self.store.set(key, value).map_err(|error| vec![error])?;
            if value.is_empty() {
                self.secrets.remove(key);
            } else {
                self.secrets.insert(key.clone(), value.to_owned());
            }
        }
        Ok(())
    }
}

/// Writes `bytes` to `path` so that only the current user can read it.
fn write_private(path: &Path, bytes: &[u8]) -> io::Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let temporary = path.with_extension("json.tmp");
    #[cfg(unix)]
    {
        use std::io::Write;
        use std::os::unix::fs::OpenOptionsExt;
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .mode(0o600)
            .open(&temporary)?;
        file.write_all(bytes)?;
    }
    #[cfg(not(unix))]
    fs::write(&temporary, bytes)?;
    fs::rename(temporary, path)
}

static SETTINGS: OnceLock<Mutex<Settings>> = OnceLock::new();

/// Loads the settings once, from `config_dir/settings.json` and the Keychain.
pub fn init(config_dir: &Path) {
    let _ = SETTINGS.set(Mutex::new(Settings::load(
        config_dir.join("settings.json"),
        Box::new(Keychain),
    )));
}

/// Runs `action` with the loaded settings, if [`init`] was called.
pub fn with<T>(action: impl FnOnce(&mut Settings) -> T) -> Option<T> {
    SETTINGS
        .get()
        .map(|settings| action(&mut settings.lock().unwrap_or_else(PoisonError::into_inner)))
}

/// The environment every engine command gets (empty before [`init`]).
pub fn engine_env() -> Vec<(String, String)> {
    with(|settings| settings.env()).unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex as StdMutex};

    #[derive(Clone, Default)]
    struct MemoryStore(Arc<StdMutex<BTreeMap<String, String>>>);

    impl SecretStore for MemoryStore {
        fn get(&self, key: &str) -> Option<String> {
            self.0.lock().unwrap().get(key).cloned()
        }
        fn set(&mut self, key: &str, value: &str) -> Result<(), String> {
            let mut map = self.0.lock().unwrap();
            if value.is_empty() {
                map.remove(key);
            } else {
                map.insert(key.to_owned(), value.to_owned());
            }
            Ok(())
        }
    }

    fn map(pairs: &[(&str, &str)]) -> BTreeMap<String, String> {
        pairs
            .iter()
            .map(|(key, value)| ((*key).to_owned(), (*value).to_owned()))
            .collect()
    }

    #[test]
    fn values_and_secrets_reach_the_engine_but_secrets_never_reach_the_view() {
        let dir = std::env::temp_dir().join(format!("continuum-settings-{}", std::process::id()));
        let store = MemoryStore::default();
        let mut settings = Settings::load(dir.join("settings.json"), Box::new(store.clone()));

        settings
            .update(
                &map(&[
                    ("CONTINUUM_LLM_PROVIDER", "groq"),
                    ("CONTINUUM_TENANT_ID", " acme "),
                ]),
                &map(&[("CONTINUUM_LLM_API_KEY", "gsk-secret")]),
            )
            .unwrap();

        let env = settings.env();
        assert!(env.contains(&("CONTINUUM_TENANT_ID".into(), "acme".into())));
        assert!(env.contains(&("CONTINUUM_LLM_API_KEY".into(), "gsk-secret".into())));
        let view = settings.view().to_string();
        assert!(!view.contains("gsk-secret"));
        assert!(view.contains("CONTINUUM_LLM_API_KEY"));

        let reloaded = Settings::load(dir.join("settings.json"), Box::new(store));
        assert_eq!(reloaded.env(), env);
        let file = fs::read_to_string(dir.join("settings.json")).unwrap();
        assert!(
            !file.contains("gsk-secret"),
            "secrets must not be written to the file"
        );
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mode = fs::metadata(dir.join("settings.json"))
                .unwrap()
                .permissions()
                .mode();
            assert_eq!(mode & 0o077, 0, "settings file must be private");
        }
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn empty_secret_deletes_it() {
        let dir =
            std::env::temp_dir().join(format!("continuum-settings-del-{}", std::process::id()));
        let store = MemoryStore::default();
        let mut settings = Settings::load(dir.join("settings.json"), Box::new(store.clone()));
        settings
            .update(&BTreeMap::new(), &map(&[("GITHUB_TOKEN", "ghp_x")]))
            .unwrap();
        settings
            .update(&BTreeMap::new(), &map(&[("GITHUB_TOKEN", "")]))
            .unwrap();

        assert!(store.get("GITHUB_TOKEN").is_none());
        assert!(settings.env().is_empty());
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn invalid_or_unknown_settings_change_nothing() {
        let dir =
            std::env::temp_dir().join(format!("continuum-settings-bad-{}", std::process::id()));
        let mut settings =
            Settings::load(dir.join("settings.json"), Box::new(MemoryStore::default()));
        for (values, secrets) in [
            (map(&[("PATH", "/evil")]), BTreeMap::new()),
            (map(&[("CONTINUUM_RETENTION_DAYS", "0")]), BTreeMap::new()),
            (map(&[("CONTINUUM_REDACT", "yes")]), BTreeMap::new()),
            (
                map(&[("CONTINUUM_ASR_BACKEND", "parakeet")]),
                BTreeMap::new(),
            ),
            (map(&[("CONTINUUM_NOTES_DIR", "a\nb")]), BTreeMap::new()),
            (
                map(&[("GITHUB_TOKEN", "in the wrong place")]),
                BTreeMap::new(),
            ),
            (
                BTreeMap::new(),
                map(&[("CONTINUUM_NOTES_DIR", "not a secret")]),
            ),
        ] {
            assert!(settings.update(&values, &secrets).is_err());
        }
        assert!(settings.env().is_empty());
        assert!(!dir.join("settings.json").exists());
    }

    /// Touches the real credential store; run with `cargo test -- --ignored`.
    #[test]
    #[ignore = "uses the real Keychain"]
    fn keychain_round_trip() {
        let key = "CONTINUUM_TEST_ONLY_SECRET";
        let mut keychain = Keychain;
        keychain.set(key, "round-trip-value").unwrap();
        assert_eq!(keychain.get(key).as_deref(), Some("round-trip-value"));
        keychain.set(key, "").unwrap();
        assert_eq!(keychain.get(key), None);
        keychain.set(key, "").unwrap();
    }

    #[test]
    fn every_choice_default_is_valid() {
        for field in FIELDS {
            if let Kind::Choice(options) = field.kind {
                assert!(problem(field, options[0]).is_none(), "{}", field.key);
            }
        }
    }
}
