"""Settings routes used by the Settings dialog extension (web/modelsite.js).

The key is accepted over POST only, written to a 0600 file, and never returned.
"""
from urllib.parse import urlparse

from aiohttp import web

from . import config


def _same_origin(request):
    origin = request.headers.get("Origin")
    if not origin:
        return True  # non-browser client
    return urlparse(origin).netloc == request.headers.get("Host", "")


def register(routes):
    @routes.get("/modelsite/config")
    async def get_config(request):
        return web.json_response(config.status())

    @routes.post("/modelsite/config")
    async def post_config(request):
        if not _same_origin(request):
            return web.json_response({"error": "cross-origin request refused"}, status=403)
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON"}, status=400)
        key = body.get("api_key")
        base = body.get("base_url")
        if key is not None and (not isinstance(key, str) or not key.strip()):
            return web.json_response({"error": "api_key must be a non-empty string"}, status=400)
        if base is not None and not (isinstance(base, str) and base.strip().lower().startswith(("http://", "https://"))):
            return web.json_response({"error": "base_url must start with http:// or https://"}, status=400)
        config.save(api_key=key, base_url=base)
        return web.json_response(config.status())
