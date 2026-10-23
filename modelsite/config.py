"""Shared runtime configuration.

Every node reads the base URL and API key *at execution time* through the
functions below. Never import these values by value (``from x import baseurl``):
a value copied at import time can no longer follow a later change, which is
exactly how another community pack's "custom address" option silently stopped
working.

Sources, highest priority first: runtime override (set from the Settings UI
route) > environment variable > config file in the ComfyUI user directory.
The API key is never a node widget, because widget values are saved into
workflow JSON and embedded in generated media metadata.
"""
import json
import os
import re
import threading

DEFAULT_BASE_URL = "https://api.modelsite.ai"
_KEY_RE = re.compile(r"sk-ms-[A-Za-z0-9_\-]{8,}")
_lock = threading.Lock()
_runtime = {"base_url": None, "api_key": None}


class MissingApiKey(RuntimeError):
    pass


def reset_runtime():
    with _lock:
        _runtime["base_url"] = None
        _runtime["api_key"] = None


def set_runtime(base_url=None, api_key=None):
    with _lock:
        if base_url is not None:
            _runtime["base_url"] = base_url
        if api_key is not None:
            _runtime["api_key"] = api_key


def config_dir():
    env = os.environ.get("MODELSITE_CONFIG_DIR")
    if env:
        return env
    try:  # inside ComfyUI
        import folder_paths

        return os.path.join(folder_paths.get_user_directory(), "modelsite")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".config", "comfyui-modelsite")


def _config_path():
    return os.path.join(config_dir(), "config.json")


def _read_file():
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _norm_url(url):
    return (url or "").strip().rstrip("/")


def get_base_url():
    with _lock:
        v = _runtime["base_url"]
    for cand in (v, os.environ.get("MODELSITE_BASE_URL"), _read_file().get("base_url")):
        if cand and cand.strip():
            return _norm_url(cand)
    return DEFAULT_BASE_URL


def get_api_key():
    with _lock:
        v = _runtime["api_key"]
    for cand in (v, os.environ.get("MODELSITE_API_KEY"), _read_file().get("api_key")):
        if cand and cand.strip():
            return cand.strip()
    return None


def require_api_key():
    key = get_api_key()
    if not key:
        raise MissingApiKey(
            "Modelsite API key is not set. Open ComfyUI Settings -> Modelsite and paste your key, "
            "or set the MODELSITE_API_KEY environment variable before starting ComfyUI."
        )
    return key


def save(api_key=None, base_url=None):
    """Persist to the config file with 0600 permissions (and update the runtime values)."""
    data = _read_file()
    if api_key:
        data["api_key"] = api_key.strip()
    if base_url:
        data["base_url"] = _norm_url(base_url)
    d = config_dir()
    os.makedirs(d, mode=0o700, exist_ok=True)
    path = _config_path()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.chmod(path, 0o600)
    set_runtime(base_url=_norm_url(base_url) if base_url else None, api_key=api_key.strip() if api_key else None)


def mask(key):
    if not key:
        return ""
    return key[:6] + "…" + ("*" * 4)


def redact(text):
    """Remove anything key-shaped, plus the currently configured key, from a string."""
    out = _KEY_RE.sub("sk-ms-…", str(text))
    key = get_api_key()
    if key and key in out:
        out = out.replace(key, "sk-ms-…")
    return out


def status():
    key = get_api_key()
    return {"base_url": get_base_url(), "key_set": bool(key), "key_hint": mask(key)}
