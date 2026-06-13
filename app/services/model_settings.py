"""Central model registry — single source of truth for which Claude model is active."""

MODELS: dict[str, tuple[str, str]] = {
    "haiku":  ("claude-haiku-4-5",  "Haiku 4.5 — fastest"),
    "sonnet": ("claude-sonnet-4-6", "Sonnet 4.6 — balanced"),
    "opus":   ("claude-opus-4-8",   "Opus 4.8 — smartest"),
}

_current_key = "sonnet"


def get_model() -> str:
    return MODELS.get(_current_key, MODELS["sonnet"])[0]


def get_model_key() -> str:
    return _current_key


def set_model_key(key: str) -> bool:
    global _current_key
    if key in MODELS:
        _current_key = key
        return True
    return False
