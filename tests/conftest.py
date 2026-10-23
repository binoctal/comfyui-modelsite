"""Shared fixtures: a real local HTTP server that speaks our public API shapes.

No mocks of the code under test: the package talks to this server over real
HTTP, so request bodies, headers and polling are exercised end to end.
"""
import os
import sys

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

KEY = "sk-ms-" + "a" * 64

MODELS = [
    # `provider` carries a decoy value: the package must never read it
    {"id": "dreamina-seedance-2-0", "name": "Seedance 2.0", "category": ["video_generation"], "provider": "SUPPLIER-X"},
    {"id": "dreamina-seedance-2-0-mini", "name": "Seedance 2.0 mini", "category": ["video_generation"], "provider": "SUPPLIER-X"},
    {"id": "wan2.7-t2v", "name": "Wan 2.7 T2V", "category": ["video_generation"], "provider": "SUPPLIER-Y"},
    {"id": "wan2.7-i2v", "name": "Wan 2.7 I2V", "category": ["video_generation"], "provider": "SUPPLIER-Y"},
    {"id": "happyhorse-1.1-t2v", "name": "HappyHorse 1.1 T2V", "category": ["video_generation"], "provider": "SUPPLIER-Y"},
    {"id": "happyhorse-1.1-i2v", "name": "HappyHorse 1.1 I2V", "category": ["video_generation"], "provider": "SUPPLIER-Y"},
    {"id": "minimax-h3", "name": "MiniMax H3", "category": ["video_generation"], "provider": "SUPPLIER-Z"},
    {"id": "doubao-seedream-4.5", "name": "Seedream 4.5", "category": ["image_generation"], "provider": "SUPPLIER-X"},
    {"id": "qwen-image-2.0-pro", "name": "Qwen Image", "category": ["image_generation"], "provider": "SUPPLIER-Y"},
    {"id": "deepseek-v4", "name": "DeepSeek", "category": ["chat"], "provider": "SUPPLIER-Q"},
]


class FakeApi:
    """Scripted gateway. `polls` is the number of non-terminal polls before success."""

    def __init__(self):
        self.requests = []  # (method, path, headers, json)
        self.polls = 1
        self.poll_count = {}
        self.fail_poll = False
        self.models_status = 200
        self.create_status = 200
        self.next_id = 0
        self.hide_paths = set()  # paths that answer a plain-text 404 like an unrouted prefix

    def _auth_ok(self, request):
        return request.headers.get("Authorization") == f"Bearer {KEY}"

    async def _record(self, request):
        body = None
        if request.can_read_body and request.content_type == "application/json":
            body = await request.json()
        self.requests.append((request.method, request.path, dict(request.headers), body))
        return body

    def app(self):
        app = web.Application(client_max_size=64 * 1024 * 1024)
        r = app.router
        r.add_get("/api/models", self.models)
        r.add_get("/api/models/{mid}", self.model_detail)
        r.add_post("/v1/contents/generations/tasks", self.ark_create)
        r.add_post("/api/v3/contents/generations/tasks", self.ark_create)
        r.add_get("/api/v3/contents/generations/tasks/{tid}", self.ark_poll)
        r.add_get("/v1/contents/generations/tasks/{tid}", self.ark_poll)
        r.add_post("/api/v1/services/aigc/video-generation/video-synthesis", self.ds_create)
        r.add_get("/api/v1/tasks/{tid}", self.ds_poll)
        r.add_post("/v2/video_generation", self.mm_create)
        r.add_get("/v2/query/video_generation/{tid}", self.mm_poll)
        r.add_post("/v1/images/generations", self.images)
        r.add_get("/media/video.mp4", self.media_video)
        r.add_get("/media/img.png", self.media_png)
        return app

    async def models(self, request):
        await self._record(request)
        if self.models_status != 200:
            return web.json_response({"success": False}, status=self.models_status)
        return web.json_response({"success": True, "data": MODELS})

    async def model_detail(self, request):
        await self._record(request)
        mid = request.match_info["mid"]
        qs = {
            "dreamina-seedance-2-0": {"method": "POST", "path": "/api/v3/contents/generations/tasks",
                                       "poll": "GET /api/v3/contents/generations/tasks/{task_id}", "taskIdPath": "id"},
            "wan2.7-t2v": {"method": "POST", "path": "/api/v1/services/aigc/video-generation/video-synthesis",
                            "poll": "GET /api/v1/tasks/{task_id}", "taskIdPath": "output.task_id"},
        }
        return web.json_response({"success": True, "data": {"id": mid, "provider": "SUPPLIER", "quickstart": qs.get(mid)}})

    def _need_auth(self, request):
        if not self._auth_ok(request):
            return web.json_response({"error": {"message": "unauthorized"}}, status=401)

    # ---- Ark style
    def _unrouted(self, request):
        if request.path in self.hide_paths:
            return web.Response(text="404 page not found", status=404)

    async def ark_create(self, request):
        await self._record(request)
        if (e := self._unrouted(request)) is not None:
            return e
        if (e := self._need_auth(request)) is not None:
            return e
        if self.create_status != 200:
            return web.json_response({"error": {"code": "InvalidParameter", "message": "bad resolution"}}, status=self.create_status)
        self.next_id += 1
        return web.json_response({"id": f"cgt-{self.next_id}"})

    async def ark_poll(self, request):
        await self._record(request)
        if (e := self._unrouted(request)) is not None:
            return e
        tid = request.match_info["tid"]
        n = self.poll_count[tid] = self.poll_count.get(tid, 0) + 1
        if self.fail_poll:
            return web.json_response({"id": tid, "status": "failed", "error": {"code": "SensitiveContent", "message": "refused by upstream"}})
        if n <= self.polls:
            return web.json_response({"id": tid, "status": "running"})
        return web.json_response({"id": tid, "status": "succeeded",
                                  "content": {"video_url": str(request.url.with_path("/media/video.mp4"))},
                                  "usage": {"completion_tokens": 40594, "total_tokens": 40594}})

    # ---- DashScope style
    async def ds_create(self, request):
        await self._record(request)
        if (e := self._need_auth(request)) is not None:
            return e
        if self.create_status != 200:
            return web.json_response({"code": "InvalidParameter", "message": "bad duration"}, status=self.create_status)
        self.next_id += 1
        return web.json_response({"output": {"task_id": f"video_{self.next_id}", "task_status": "PENDING"}})

    async def ds_poll(self, request):
        await self._record(request)
        tid = request.match_info["tid"]
        n = self.poll_count[tid] = self.poll_count.get(tid, 0) + 1
        if self.fail_poll:
            return web.json_response({"output": {"task_id": tid, "task_status": "FAILED", "code": "DataInspectionFailed", "message": "blocked"}})
        if n <= self.polls:
            return web.json_response({"output": {"task_id": tid, "task_status": "RUNNING"}})
        return web.json_response({"output": {"task_id": tid, "task_status": "SUCCEEDED",
                                             "video_url": str(request.url.with_path("/media/video.mp4"))},
                                  "usage": {"duration": 5, "SR": 720}})

    # ---- MiniMax style
    async def mm_create(self, request):
        await self._record(request)
        if (e := self._need_auth(request)) is not None:
            return e
        self.next_id += 1
        return web.json_response({"task_id": f"mm-{self.next_id}"})

    async def mm_poll(self, request):
        await self._record(request)
        tid = request.match_info["tid"]
        n = self.poll_count[tid] = self.poll_count.get(tid, 0) + 1
        if n <= self.polls:
            return web.json_response({"task": {"status": "Running"}})
        # real shape: everything lives inside `task`, including content.url and usage
        return web.json_response({"task": {"status": "succeeded", "id": tid,
                                           "content": {"url": str(request.url.with_path("/media/video.mp4"))},
                                           "usage": {"total_seconds": 4, "total_tokens": 129046}}})

    # ---- images
    async def images(self, request):
        await self._record(request)
        if (e := self._need_auth(request)) is not None:
            return e
        return web.json_response({"model": "x", "data": [{"url": str(request.url.with_path("/media/img.png")), "size": "64x64"}],
                                  "usage": {"generated_images": 1, "output_tokens": 16}})

    async def media_video(self, request):
        self.requests.append(("GET", request.path, dict(request.headers), None))
        return web.Response(body=b"\x00\x00\x00\x18ftypmp42FAKEVIDEO", content_type="video/mp4")

    async def media_png(self, request):
        self.requests.append(("GET", request.path, dict(request.headers), None))
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (64, 64), (200, 80, 40)).save(buf, "PNG")
        return web.Response(body=buf.getvalue(), content_type="image/png")


@pytest.fixture
async def api(tmp_path, monkeypatch):
    fake = FakeApi()
    server = TestServer(fake.app())
    await server.start_server()
    monkeypatch.setenv("MODELSITE_BASE_URL", str(server.make_url("")).rstrip("/"))
    monkeypatch.setenv("MODELSITE_API_KEY", KEY)
    monkeypatch.setenv("MODELSITE_CONFIG_DIR", str(tmp_path / "cfg"))
    from modelsite import config, catalog
    config.reset_runtime()
    catalog.clear_cache()
    fake.base = str(server.make_url("")).rstrip("/")
    yield fake
    await server.close()
