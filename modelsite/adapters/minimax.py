"""MiniMax-style entrance (/v2)."""
from .base import Call, Poll, fmt_error

MODEL_NAMES = {"minimax-h3": "MiniMax-H3", "minimax-h3-max": "MiniMax-H3-Max"}


class MiniMaxAdapter:
    family = "minimax"
    create_path = "/v2/video_generation"
    poll_template = "/v2/query/video_generation/{task_id}"

    def create(self, req):
        content = [{"type": "text", "text": req.prompt}]
        if req.first_frame:
            content.append({"type": "image_url", "image_url": {"url": req.first_frame}, "role": "first_frame"})
        if req.last_frame:
            content.append({"type": "image_url", "image_url": {"url": req.last_frame}, "role": "last_frame"})
        body = {
            "model": MODEL_NAMES.get(req.model, req.model),
            "content": content,
            "resolution": req.resolution.upper(),
            "duration": req.duration,
            # text-to-video needs a concrete ratio; image-to-video always follows the input image
            "ratio": "adaptive" if req.first_frame or req.last_frame else req.ratio,
        }
        return Call("POST", self.create_path, body)

    def task_id(self, resp):
        tid = resp.get("task_id") if isinstance(resp, dict) else None
        if not tid:
            raise ValueError(f"create response has no task id: {resp!r}")
        return str(tid)

    def poll_call(self, task_id, template=None):
        return Call("GET", (template or self.poll_template).replace("{task_id}", task_id))

    def parse_poll(self, resp):
        task = resp.get("task") or {}
        status = str(task.get("status", "")).lower()
        if status == "succeeded":
            # everything is nested inside `task` (content.url, usage)
            return Poll("succeeded", url=(task.get("content") or {}).get("url"), usage=task.get("usage"))
        if status in ("failed", "cancelled", "canceled"):
            return Poll("failed", error=fmt_error(task.get("error_code"), task.get("error_message")) if (task.get("error_code") or task.get("error_message")) else f"task {status}")
        if status == "running":
            return Poll("running")
        return Poll("pending")
