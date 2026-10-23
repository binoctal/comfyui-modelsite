"""Model list: fetched from the public catalog at runtime, with a bundled offline fallback.

Only `id`, `name` and `category` are read. Other fields are never copied into
this package's data model; in particular `provider` is ignored.
"""
import asyncio
import json
import os
import time
import urllib.request
from dataclasses import dataclass

from . import config

FALLBACK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fallback_models.json")
TTL_SECONDS = 300
FETCH_TIMEOUT = 4

_cache = {"at": 0.0, "base": None, "models": None}


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    category: str  # video_generation | image_generation


def clear_cache():
    _cache.update(at=0.0, base=None, models=None)


def family_of(model_id):
    m = model_id.lower()
    if m.startswith("dreamina-seedance-"):
        return "ark"
    if m.startswith("happyhorse-") or m.startswith("wan"):
        return "dashscope"
    if m.startswith("minimax-"):
        return "minimax"
    if m.startswith("doubao-seedream-"):
        return "openai_image"
    return None


def supports(model_id, task):
    fam = family_of(model_id)
    m = model_id.lower()
    if task == "t2v":
        return fam in ("ark", "minimax") or (fam == "dashscope" and "t2v" in m)
    if task == "i2v":
        return fam in ("ark", "minimax") or (fam == "dashscope" and "i2v" in m)
    if task in ("t2i", "i2i"):
        return fam == "openai_image"
    return False


def _parse(payload):
    data = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        data = data.get("items") or data.get("models") or []
    out = []
    for item in data or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        cats = item.get("category") or []
        cat = cats[0] if isinstance(cats, list) and cats else (cats if isinstance(cats, str) else "")
        if cat in ("video_generation", "image_generation"):
            out.append(ModelInfo(id=str(item["id"]), name=str(item.get("name") or item["id"]), category=cat))
    return out


def _fallback():
    with open(FALLBACK_PATH, "r", encoding="utf-8") as f:
        return [ModelInfo(**m) for m in json.load(f)]


def get_models_sync():
    base = config.get_base_url()
    now = time.monotonic()
    if _cache["models"] is not None and _cache["base"] == base and now - _cache["at"] < TTL_SECONDS:
        return _cache["models"]
    try:
        req = urllib.request.Request(base + "/api/models", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            models = _parse(json.load(resp))
        if not models:
            raise ValueError("empty model list")
    except Exception:
        models = _fallback()
        _cache.update(at=now - TTL_SECONDS + 30, base=base, models=models)  # retry soon, not on every schema build
        return models
    _cache.update(at=now, base=base, models=models)
    return models


def models_for_sync(task):
    return [m for m in get_models_sync() if supports(m.id, task)]


async def get_models():
    return await asyncio.to_thread(get_models_sync)


async def models_for(task):
    return await asyncio.to_thread(models_for_sync, task)
