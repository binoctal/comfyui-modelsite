import json
import os
import stat

import pytest

from modelsite import config
from tests.conftest import KEY


def test_key_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MODELSITE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("MODELSITE_API_KEY", KEY)
    config.reset_runtime()
    assert config.get_api_key() == KEY


def test_missing_key_gives_actionable_error(monkeypatch, tmp_path):
    monkeypatch.setenv("MODELSITE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("MODELSITE_API_KEY", raising=False)
    config.reset_runtime()
    with pytest.raises(config.MissingApiKey) as e:
        config.require_api_key()
    msg = str(e.value)
    assert "MODELSITE_API_KEY" in msg and "Settings" in msg


def test_runtime_value_is_read_on_every_call_not_cached_by_value(monkeypatch, tmp_path):
    """Regression for the Comfly bug: `from x import baseurl` froze the value at import time."""
    monkeypatch.setenv("MODELSITE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("MODELSITE_BASE_URL", raising=False)
    config.reset_runtime()
    assert config.get_base_url() == "https://api.modelsite.ai"
    config.set_runtime(base_url="http://127.0.0.1:9999/")
    assert config.get_base_url() == "http://127.0.0.1:9999"  # trailing slash stripped
    config.set_runtime(base_url="http://127.0.0.1:1111")
    assert config.get_base_url() == "http://127.0.0.1:1111"


def test_save_writes_600_file_and_is_picked_up(monkeypatch, tmp_path):
    monkeypatch.setenv("MODELSITE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("MODELSITE_API_KEY", raising=False)
    monkeypatch.delenv("MODELSITE_BASE_URL", raising=False)
    config.reset_runtime()
    config.save(api_key=KEY, base_url="https://example.test")
    path = tmp_path / "config.json"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert json.loads(path.read_text())["api_key"] == KEY
    config.reset_runtime()
    assert config.get_api_key() == KEY
    assert config.get_base_url() == "https://example.test"


def test_env_beats_file(monkeypatch, tmp_path):
    monkeypatch.setenv("MODELSITE_CONFIG_DIR", str(tmp_path))
    config.reset_runtime()
    config.save(api_key="sk-ms-file")
    monkeypatch.setenv("MODELSITE_API_KEY", KEY)
    config.reset_runtime()
    assert config.get_api_key() == KEY


def test_redact_hides_key_everywhere():
    text = f"Authorization: Bearer {KEY} failed for {KEY}"
    out = config.redact(text)
    assert KEY not in out and "sk-ms-" in out
    assert config.mask(KEY).startswith("sk-ms-") and KEY not in config.mask(KEY)
    assert config.redact("no secrets here") == "no secrets here"


def test_status_never_contains_the_key(monkeypatch, tmp_path):
    monkeypatch.setenv("MODELSITE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("MODELSITE_API_KEY", KEY)
    config.reset_runtime()
    st = config.status()
    assert st["key_set"] is True and KEY not in json.dumps(st)
