"""Non-secret settings for API connections."""
from urllib.parse import urlparse
import re

API_PROVIDERS = ("openai_compatible", "claude", "grok", "muse", "glm", "selfhost")


def valid_provider_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value))


def is_api_provider(settings: dict, provider: str) -> bool:
    return provider in settings.get("api_connections", {}) or provider in API_PROVIDERS


def provider_label(settings: dict, provider: str) -> str:
    return settings.get("api_connections", {}).get(provider, {}).get("name") or {"codex": "Codex", "deepseek": "DeepSeek"}.get(provider, provider.replace("_", " "))


def validate_endpoint(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        return value
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        raise ValueError("Enter a valid API URL.") from None
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use an HTTP or HTTPS API URL with no password, query, or fragment.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use HTTPS for a remote API, or HTTP for a local endpoint.")
    return value


def selected_model(settings: dict, provider: str) -> str:
    if is_api_provider(settings, provider):
        return settings.get("api_connections", {}).get(provider, {}).get("model", "")
    return settings.get(provider + "_model", "")
