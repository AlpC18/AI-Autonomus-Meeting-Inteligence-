# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""One way to ask a language model for text, whichever provider the user picked.

Free and local providers (Groq, Gemini, OpenRouter, Mistral, Ollama, LM
Studio) and any other OpenAI-compatible server are reached over their
``/chat/completions`` endpoint. Claude goes through the official Anthropic
SDK, installed with the ``claude`` extra.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from continuum import net

CLAUDE = "anthropic"
"""Provider name for Claude."""

CLAUDE_MODEL = "claude-opus-5-5"
_CLAUDE_FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
_TIMEOUT_S = 180.0


@dataclass(frozen=True, slots=True)
class Preset:
    """Where an OpenAI-compatible provider lives and what it runs by default."""

    base_url: str | None
    model: str | None
    key_variable: str | None


PRESETS: dict[str, Preset] = {
    "groq": Preset("https://api.groq.com/openai/v1", "openai/gpt-oss-120b", "GROQ_API_KEY"),
    "gemini": Preset(
        "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash", "GEMINI_API_KEY"
    ),
    # Free OpenRouter models come and go, so the user names one (an id ending in ":free").
    "openrouter": Preset("https://openrouter.ai/api/v1", None, "OPENROUTER_API_KEY"),
    "mistral": Preset("https://api.mistral.ai/v1", "mistral-small-latest", "MISTRAL_API_KEY"),
    "ollama": Preset("http://localhost:11434/v1", "llama3.2", None),
    "lmstudio": Preset("http://localhost:1234/v1", None, None),
    "openai": Preset("https://api.openai.com/v1", "gpt-4o-mini", "OPENAI_API_KEY"),
    "custom": Preset(None, None, None),
    CLAUDE: Preset(None, CLAUDE_MODEL, "ANTHROPIC_API_KEY"),
}
"""Every provider name accepted in ``CONTINUUM_LLM_PROVIDER``."""


def _is_local(url: str) -> bool:
    return urlsplit(url).hostname in {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True, slots=True)
class LlmSettings:
    """Which model answers, and how to reach it.

    ``api_key`` is excluded from ``repr`` so it cannot end up in a log line.
    A key is only ever sent to ``base_url`` (or Anthropic's API), and only
    over HTTPS unless the server runs on this machine.

    Raises:
        ValueError: on construction, for an unknown provider, a missing
            model, base URL or key, or a key that would go over plain HTTP.
    """

    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.provider not in PRESETS:
            raise ValueError(
                f"CONTINUUM_LLM_PROVIDER must be one of {', '.join(PRESETS)}, got {self.provider!r}"
            )
        if not self.model:
            raise ValueError(f"CONTINUUM_LLM_MODEL must be set for provider {self.provider!r}")
        preset = PRESETS[self.provider]
        if self.provider == CLAUDE:
            return
        if not self.base_url or urlsplit(self.base_url).scheme not in {"http", "https"}:
            raise ValueError(f"CONTINUUM_LLM_BASE_URL must be an http(s) URL for {self.provider!r}")
        if preset.key_variable and not self.api_key:
            raise ValueError(
                f"{preset.key_variable} (or CONTINUUM_LLM_API_KEY) must be set to use {self.provider!r}"
            )
        if self.api_key and self.base_url.startswith("http://") and not _is_local(self.base_url):
            raise ValueError("An API key may only be sent over https (or to this machine)")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "LlmSettings | None":
        """Read ``CONTINUUM_LLM_PROVIDER`` and friends; ``None`` when no provider is set.

        Variables: ``CONTINUUM_LLM_PROVIDER``, ``CONTINUUM_LLM_MODEL`` and
        ``CONTINUUM_LLM_BASE_URL`` (override the preset), and the key: the
        provider's own variable (``GROQ_API_KEY``, ``GEMINI_API_KEY``, ...)
        or ``CONTINUUM_LLM_API_KEY``.

        Raises:
            ValueError: as for construction.
        """
        provider = env.get("CONTINUUM_LLM_PROVIDER", "").strip().lower()
        if not provider:
            return None
        preset = PRESETS.get(provider, Preset(None, None, None))
        key = env.get("CONTINUUM_LLM_API_KEY") or (
            env.get(preset.key_variable) if preset.key_variable else None
        )
        return cls(
            provider=provider,
            model=env.get("CONTINUUM_LLM_MODEL") or preset.model or "",
            base_url=(env.get("CONTINUUM_LLM_BASE_URL") or preset.base_url or "").rstrip("/") or None,
            api_key=key or None,
        )


def json_object(reply: str) -> dict[str, Any] | None:
    """The first JSON object in a model's reply (bare, fenced or amid prose), or ``None``.

    Small local models sometimes close the object too early and carry on with
    more keys (``...]}, "sections": {...}}``); those keys are read too.
    """
    decoder = json.JSONDecoder()
    for start in (index for index, char in enumerate(reply) if char == "{"):
        try:
            data, end = decoder.raw_decode(reply, start)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        rest = reply[end:].lstrip()
        if rest.startswith(","):
            try:
                more, _ = decoder.raw_decode("{" + rest[1:].lstrip())
            except json.JSONDecodeError:
                more = None
            if isinstance(more, dict):
                data = {**more, **data}
        return data
    return None


class Llm(Protocol):
    """Anything that can turn a system prompt and a user message into text."""

    def complete(self, system: str, user: str) -> str:
        """Return the model's reply.

        Raises:
            RuntimeError: if the provider cannot be reached or refuses.
        """
        ...


class OpenAiCompatible:
    """A ``/chat/completions`` endpoint: Groq, Gemini, OpenRouter, Ollama, ..."""

    def __init__(self, settings: LlmSettings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client or net.client(_TIMEOUT_S)

    def complete(self, system: str, user: str) -> str:
        """Return the first choice's text. See :meth:`Llm.complete`."""
        settings = self._settings
        headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
        body = {
            "model": settings.model,
            "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            response = self._client.post(
                f"{settings.base_url}/chat/completions", headers=headers, json=body
            )
        except httpx.HTTPError as error:
            raise RuntimeError(
                f"{settings.provider} could not be reached ({type(error).__name__})"
            ) from None
        if response.status_code != 200:
            raise RuntimeError(
                f"{settings.provider} refused the request (HTTP {response.status_code}): "
                f"{_error_text(response)}"
            )
        try:
            text = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError(f"{settings.provider} returned an unreadable reply") from None
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(f"{settings.provider} returned an empty reply")
        return text


def _error_text(response: httpx.Response) -> str:
    try:
        data: Any = response.json()
    except ValueError:
        return response.text[:200] or "no details given"
    error = data[0] if isinstance(data, list) and data else data
    if isinstance(error, dict) and isinstance(error.get("error"), dict):
        return str(error["error"].get("message", ""))[:300] or "no details given"
    if isinstance(error, dict) and "error" in error:
        return str(error["error"])[:300]
    return str(data)[:200]


class Claude:
    """Claude through the official Anthropic SDK (``pip install continuum[claude]``)."""

    def __init__(self, settings: LlmSettings, client: Any = None) -> None:
        """``client`` is an ``anthropic.Anthropic``; one is created when omitted.

        Raises:
            RuntimeError: if the ``anthropic`` package is not installed.
        """
        self._settings = settings
        try:
            import anthropic
        except ImportError:
            if client is None:
                raise RuntimeError(
                    "Claude needs the Anthropic SDK: run `uv sync --extra claude`"
                ) from None
            # An injected client without the SDK installed: no SDK errors to translate.
            self._unreachable: tuple[type[Exception], ...] = ()
            self._refused: tuple[type[Exception], ...] = ()
        else:
            self._unreachable = (anthropic.APIConnectionError,)
            self._refused = (anthropic.APIStatusError,)
            if client is None:
                # Without an explicit key the SDK uses ANTHROPIC_API_KEY or an `ant auth login` profile.
                client = anthropic.Anthropic(api_key=settings.api_key, timeout=_TIMEOUT_S)
        self._client = client

    def complete(self, system: str, user: str) -> str:
        """Return Claude's text reply. See :meth:`Llm.complete`."""
        model = self._settings.model
        extra: dict[str, Any] = {}
        if model in _CLAUDE_FALLBACK_MODELS:
            # A request declined by a safety classifier is re-run on Anthropic's
            # recommended fallback model instead of failing.
            extra = {
                "betas": ["server-side-fallback-2026-07-01"],
                "fallbacks": "default",
                "output_config": {"effort": "medium"},
            }
        try:
            response = self._client.beta.messages.create(
                model=model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                **extra,
            )
        except self._unreachable:
            raise RuntimeError("Claude could not be reached") from None
        except self._refused as error:
            status = getattr(error, "status_code", "?")
            raise RuntimeError(
                f"Claude refused the request (HTTP {status}): {getattr(error, 'message', error)}"
            ) from None
        if response.stop_reason == "refusal":
            raise RuntimeError("Claude declined to answer this request")
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text.strip():
            raise RuntimeError("Claude returned an empty reply")
        return text


def connect(settings: LlmSettings) -> Llm:
    """Return a client for the configured provider, writing in ``CONTINUUM_LANGUAGE``.

    Raises:
        RuntimeError: if Claude is chosen but the SDK is not installed.
    """
    from continuum.language import InLanguage  # imports this module

    return InLanguage(Claude(settings) if settings.provider == CLAUDE else OpenAiCompatible(settings))
