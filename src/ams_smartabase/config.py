"""Configuration and credential helpers."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping, MutableMapping
from urllib.parse import urlparse, urlunparse


DEFAULT_USER_AGENT = "ams-python-smartabase-client"
SECRET_KEYS = {"password", "SMARTABASE_PASSWORD", "SB_PASS"}


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


def normalize_url(url: str) -> str:
    """Return a Smartabase base URL with an https scheme and no trailing slash."""

    if not url or not url.strip():
        raise ConfigurationError("Smartabase URL is required.")

    raw = url.strip()
    if "://" not in raw:
        raw = f"https://{raw}"

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ConfigurationError(f"Unsupported URL scheme: {parsed.scheme!r}.")
    if not parsed.netloc:
        raise ConfigurationError(f"Invalid Smartabase URL: {url!r}.")

    path = parsed.path.rstrip("/")
    normalized = parsed._replace(scheme="https", path=path, params="", query="", fragment="")
    return urlunparse(normalized).rstrip("/")


def _first_present(env: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return ""


@dataclass(frozen=True)
class SmartabaseCredentials:
    """Connection details loaded from environment or supplied by the caller."""

    url: str
    username: str
    password: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", normalize_url(self.url))
        if not self.username:
            raise ConfigurationError("Smartabase username is required.")
        if not self.password:
            raise ConfigurationError("Smartabase password is required.")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SmartabaseCredentials":
        return load_credentials(env)

    def redacted_dict(self) -> dict[str, str]:
        return {
            "url": self.url,
            "username": self.username,
            "password": "***",
        }


def load_credentials(env: Mapping[str, str] | None = None) -> SmartabaseCredentials:
    """Load credentials from the environment, falling back to a local .env file."""

    source = os.environ if env is None else env
    dotenv_values = load_dotenv()
    url = _first_present(source, "SMARTABASE_URL", "SB_URL")
    if not url:
        url = _first_present(dotenv_values, "SMARTABASE_URL", "SB_URL")
    username = _first_present(source, "SMARTABASE_USERNAME", "SB_USER")
    if not username:
        username = _first_present(dotenv_values, "SMARTABASE_USERNAME", "SB_USER")
    password = _first_present(source, "SMARTABASE_PASSWORD", "SB_PASS")
    if not password:
        password = _first_present(dotenv_values, "SMARTABASE_PASSWORD", "SB_PASS")
    return SmartabaseCredentials(url=url, username=username, password=password)


def load_dotenv(path: str | os.PathLike[str] = ".env") -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file if present."""

    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _strip_quotes(value.strip())
    return values


def redact_secrets(value):
    """Return a copy of nested values with password-like keys redacted."""

    if isinstance(value, Mapping):
        redacted: MutableMapping = {}
        for key, item in value.items():
            if str(key).lower() in {"password", "smartabase_password", "sb_pass"}:
                redacted[key] = "***"
            else:
                redacted[key] = redact_secrets(item)
        return dict(redacted)
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
