"""Ark-style entrance (Seedance): POST .../contents/generations/tasks with a `content` array."""
from .base import Call, Poll, fmt_error

# /v1 is routed to the gateway everywhere (it is the OpenAI-compatible prefix); /api/v3 is the vendor-style alias
# the docs use and may be missing from a front proxy, so the built-in default is the one that always works.
CREATE_PATH = "/v1/contents/generations/tasks"


class ArkAdapter:
    family = "ark"
    create_path = CREATE_PATH
    poll_template = CREATE_PATH + "/{task_id}"

    def create(self, req):
        content = [{"type": "text", "text": req.prompt}]
        if req.first_frame:
            content.append({"type": "image_url", "image_url": {"url": req.first_frame}, "role": "first_frame"})
        if req.last_frame:
            content.append({"type": "image_url", "image_url": {"url": req.last_frame}, "role": "last_frame"})
        body = {
            "model": req.model,
            "content": content,
            "resolution": req.resolution.lower(),
            "ratio": req.ratio,
            "duration": req.duration,
            "generate_audio": req.generate_audio,
            "watermark": req.watermark,
        }
        if req.seed >= 0:
            body["seed"] = req.seed
        return Call("POST", self.create_path, body)

    def task_id(self, resp):
        tid = resp.get("id") if isinstance(resp, dict) else None
        if not tid:
            raise ValueError(f"create response has no task id: {resp!r}")
        return str(tid)

    def poll_call(self, task_id, template=None):
        return Call("GET", (template or self.poll_template).replace("{task_id}", task_id))

    def parse_poll(self, resp):
        status = str(resp.get("status", "")).lower()
        if status == "succeeded":
            url = (resp.get("content") or {}).get("video_url")
            return Poll("succeeded", url=url, usage=resp.get("usage"))
        if status in ("failed", "expired", "cancelled", "canceled"):
            err = resp.get("error") or {}
            return Poll("failed", error=fmt_error(err.get("code"), err.get("message")) if err else f"task {status}")
        if status in ("running",):
            return Poll("running")
        return Poll("pending")
