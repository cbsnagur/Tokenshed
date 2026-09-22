"""Shared OpenAI-compatible chat-completion helper.

Stdlib only (urllib, json) — this is the single place either worker
script talks to the network. Never logs, prints, or raises the API key
in any message.
"""
import json
import os
import urllib.error
import urllib.request


class ApiError(Exception):
    """A user-facing, already-sanitized error message."""


class Config:
    def __init__(self, model, api_base, api_key, timeout, temperature):
        self.model = model
        self.api_base = api_base
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature


def _parse_int(raw, default):
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_temperature(raw):
    if raw is None or not raw.strip():
        return 0.2
    if raw.strip().lower() == "none":
        return None
    try:
        return float(raw)
    except ValueError:
        return 0.2


def get_config() -> Config:
    model = os.environ.get("TOKENSHED_MODEL", "").strip()
    if not model:
        raise ApiError(
            "TOKENSHED_MODEL is not set. Set it to a model name your "
            "TOKENSHED_API_BASE provider serves, e.g. "
            "export TOKENSHED_MODEL=gemini-2.5-flash"
        )
    api_base = os.environ.get("TOKENSHED_API_BASE", "https://api.openai.com/v1").rstrip("/")
    api_key = os.environ.get("TOKENSHED_API_KEY", "").strip()
    timeout = _parse_int(os.environ.get("TOKENSHED_TIMEOUT"), 180)
    temperature = _parse_temperature(os.environ.get("TOKENSHED_TEMPERATURE"))
    return Config(model, api_base, api_key, timeout, temperature)


def chat_completion(system_prompt: str, user_prompt: str, config: Config = None) -> tuple:
    """POST a single chat completion request. Returns (content, usage),
    where usage is the response's "usage" dict (empty dict if absent).
    Raises ApiError with a short, sanitized message on any failure —
    never the raw exception, never the API key."""
    config = config or get_config()

    body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if config.temperature is not None:
        body["temperature"] = config.temperature

    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{config.api_base}/chat/completions",
        data=data,
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    if config.api_key:
        request.add_header("Authorization", f"Bearer {config.api_key}")

    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ApiError(
                "authentication failed (check TOKENSHED_API_KEY)"
            ) from None
        raise ApiError(
            f"worker API at {config.api_base} returned HTTP {exc.code}"
        ) from None
    except urllib.error.URLError as exc:
        raise ApiError(f"could not reach {config.api_base}: {exc.reason}") from None
    except TimeoutError:
        raise ApiError(
            f"worker API at {config.api_base} timed out after {config.timeout}s"
        ) from None

    try:
        payload = json.loads(raw)
        content = payload["choices"][0]["message"]["content"]
        return content, (payload.get("usage") or {})
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise ApiError(
            f"worker API at {config.api_base} returned an unexpected response shape"
        ) from None
