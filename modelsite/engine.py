"""Create -> poll -> download, shared by every node.

Safety rules baked in:
* The create request is sent exactly once, never retried: a retried create can
  charge twice. If it fails after being sent, the error says so.
* Polling is idempotent and may retry transient errors.
* Signed media URLs are third-party: the API key is never sent to them.
* Every error string goes through ``config.redact``.
"""
import asyncio
import base64
import time
from dataclasses import dataclass

import aiohttp

from . import config
from .adapters import get_adapter
from .adapters.base import Call

POLL_SCHEDULE = (2, 3, 5, 8, 10)  # seconds; last value repeats
MAX_POLL_ERRORS = 5
DEFAULT_TIMEOUT_S = 15 * 60


class ModelsiteError(RuntimeError):
    pass


class RouteNotFound(ModelsiteError):
    """Plain-text 404 from the proxy or gateway router: the prefix is not routed, nothing was created."""


class Interrupted(ModelsiteError):
    pass


class ModelsiteTimeout(ModelsiteError):
    pass


@dataclass
class VideoResult:
    video_bytes: bytes
    task_id: str
    usage: dict | None
    url: str


@dataclass
class ImageResult:
    images: list
    usage: dict | None


def _hint(status):
    if status in (401, 403):
        return " Check your Modelsite API key (ComfyUI Settings -> Modelsite)."
    if status == 402:
        return " Top up your Modelsite balance and run again."
    if status == 429:
        return " Rate limited; wait a moment and retry."
    return ""


def _message(data):
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return " ".join(str(x) for x in (err.get("code"), err.get("message")) if x)
        if isinstance(err, str):
            return err
        for k in ("message", "msg"):
            if data.get(k):
                return " ".join(str(x) for x in (data.get("code"), data[k]) if x)
    return str(data)[:300]


async def _send(session, base, key, call: Call):
    headers = {"Authorization": f"Bearer {key}", **call.headers}
    async with session.request(call.method, base + call.path, json=call.json, headers=headers) as resp:
        try:
            data = await resp.json(content_type=None)
        except Exception:
            data = {"message": (await resp.text())[:300]}
        if resp.status == 404 and isinstance(data, dict) and list(data) == ["message"] and "not found" in str(data["message"]).lower():
            raise RouteNotFound(config.redact(f"HTTP 404: {_message(data)}"))
        if resp.status >= 400:
            raise ModelsiteError(config.redact(f"HTTP {resp.status}: {_message(data)}.{_hint(resp.status)}"))
        return data


async def _resolve_paths(session, base, adapter, model):
    """Prefer the paths the model publishes in its own quickstart; fall back to built-ins."""
    try:
        async with session.get(f"{base}/api/models/{model}", headers={"Accept": "application/json"},
                               timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status != 200:
                return None, None
            qs = ((await resp.json(content_type=None)).get("data") or {}).get("quickstart") or {}
    except Exception:
        return None, None
    path = qs.get("path")
    poll = qs.get("poll") or ""
    tmpl = poll.split(" ", 1)[1] if " " in poll else None
    if not (isinstance(path, str) and path.startswith("/") and tmpl and tmpl.startswith("/") and "{task_id}" in tmpl):
        return None, None
    return path, tmpl


async def _download(session, url, retries=3):
    last = None
    for attempt in range(retries):
        try:
            async with session.get(url) as resp:  # no Authorization: third-party signed URL
                if resp.status == 200:
                    return await resp.read()
                last = f"HTTP {resp.status}"
        except aiohttp.ClientError as e:
            last = str(e)
        await asyncio.sleep(1 + attempt)
    raise ModelsiteError(config.redact(f"Could not download the result ({last}). The link is time-limited; re-run if it expired."))


async def generate_video(req, *, progress=None, is_interrupted=None, sleep=None, timeout_s=DEFAULT_TIMEOUT_S, now=None):
    key = config.require_api_key()
    base = config.get_base_url()
    adapter = get_adapter(req.model)
    call = adapter.create(req)
    sleep = sleep or asyncio.sleep
    now = now or time.monotonic
    is_interrupted = is_interrupted or (lambda: False)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        path, tmpl = await _resolve_paths(session, base, adapter, req.model)
        if path:
            call.path = path
        try:
            try:
                created = await _send(session, base, key, call)
            except RouteNotFound:
                if call.path == adapter.create_path:
                    raise
                # The path the model advertised is not routed here; the request never reached a handler,
                # so trying the built-in path cannot create a second task.
                call.path, tmpl = adapter.create_path, None
                created = await _send(session, base, key, call)
        except ModelsiteError:
            raise
        except Exception as e:
            raise ModelsiteError(config.redact(
                f"Create request failed after being sent ({type(e).__name__}). It is NOT retried to avoid a duplicate charge; "
                "check your usage log before running again.")) from e
        try:
            task_id = adapter.task_id(created)
        except ValueError as e:
            raise ModelsiteError(config.redact(str(e))) from e
        start = now()
        errors = 0
        i = 0
        while True:
            if is_interrupted():
                raise Interrupted(f"Cancelled. Task {task_id} may still run upstream and be billed; it is not re-created.")
            if now() - start > timeout_s:
                raise ModelsiteTimeout(f"Timed out after {int(timeout_s)}s waiting for task {task_id}. "
                                       "It may still complete and be billed; check your usage log. It is not re-created.")
            try:
                resp = await _send(session, base, key, adapter.poll_call(task_id, tmpl))
                errors = 0
            except (aiohttp.ClientError, asyncio.TimeoutError, ModelsiteError) as e:
                if isinstance(e, ModelsiteError) and "HTTP 4" in str(e) and "HTTP 429" not in str(e):
                    raise
                errors += 1
                if errors >= MAX_POLL_ERRORS:
                    raise ModelsiteError(config.redact(f"Polling task {task_id} failed repeatedly: {e}")) from e
                await sleep(POLL_SCHEDULE[min(i, len(POLL_SCHEDULE) - 1)])
                i += 1
                continue
            poll = adapter.parse_poll(resp)
            if progress:
                progress(poll.state, i)
            if poll.state == "failed":
                raise ModelsiteError(config.redact(f"Task {task_id} failed: {poll.error}"))
            if poll.state == "succeeded":
                if not poll.url:
                    raise ModelsiteError(f"Task {task_id} succeeded but returned no video URL.")
                data = await _download(session, poll.url)
                return VideoResult(video_bytes=data, task_id=task_id, usage=poll.usage, url=poll.url)
            await sleep(POLL_SCHEDULE[min(i, len(POLL_SCHEDULE) - 1)])
            i += 1


async def generate_images(req):
    key = config.require_api_key()
    base = config.get_base_url()
    adapter = get_adapter(req.model)
    call = adapter.create_image(req)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
        try:
            resp = await _send(session, base, key, call)
        except ModelsiteError:
            raise
        except Exception as e:
            raise ModelsiteError(config.redact(
                f"Image request failed after being sent ({type(e).__name__}). It is NOT retried to avoid a duplicate charge; "
                "check your usage log before running again.")) from e
        items = adapter.parse_images(resp)
        if not items:
            raise ModelsiteError("The API returned no images.")
        images = []
        for kind, value in items:
            images.append(await _download(session, value) if kind == "url" else base64.b64decode(value))
        return ImageResult(images=images, usage=resp.get("usage"))
