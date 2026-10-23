"""DashScope-style entrance (Wan, HappyHorse): `input` + `parameters`, async via header."""
from .base import Call, Poll, fmt_error

CREATE_PATH = "/api/v1/services/aigc/video-generation/video-synthesis"
POLL_TEMPLATE = "/api/v1/tasks/{task_id}"
ALLOWED_RESOLUTIONS = ("720P", "1080P")


class DashScopeAdapter:
    family = "dashscope"
    create_path = CREATE_PATH
    poll_template = POLL_TEMPLATE

    def create(self, req):
        res = req.resolution.upper()
        if res not in ALLOWED_RESOLUTIONS:
            raise ValueError(f"{req.model} supports resolution 720P or 1080P (got {req.resolution}).")
        inp = {"prompt": req.prompt}
        if req.negative_prompt:
            inp["negative_prompt"] = req.negative_prompt
        is_i2v = "i2v" in req.model
        if is_i2v:
            if not req.first_frame:
                raise ValueError(f"{req.model} is image-to-video: connect a first_frame image.")
            if req.last_frame and req.model.startswith("happyhorse"):
                raise ValueError("HappyHorse image-to-video accepts a first frame only; remove last_frame.")
            media = [{"type": "first_frame", "url": req.first_frame}]
            if req.last_frame:
                media.append({"type": "last_frame", "url": req.last_frame})
            inp["media"] = media
        params = {"resolution": res, "duration": req.duration, "watermark": req.watermark}
        if not is_i2v:
            # image-to-video follows the first frame; the upstream answers 400 to a `ratio`
            params["ratio"] = req.ratio
        if req.seed >= 0:
            params["seed"] = req.seed
        return Call("POST", self.create_path, {"model": req.model, "input": inp, "parameters": params},
                    {"X-DashScope-Async": "enable"})

    def task_id(self, resp):
        tid = ((resp or {}).get("output") or {}).get("task_id") if isinstance(resp, dict) else None
        if not tid:
            raise ValueError(f"create response has no task id: {resp!r}")
        return str(tid)

    def poll_call(self, task_id, template=None):
        return Call("GET", (template or self.poll_template).replace("{task_id}", task_id))

    def parse_poll(self, resp):
        out = resp.get("output") or {}
        status = str(out.get("task_status", "")).upper()
        if status == "SUCCEEDED":
            return Poll("succeeded", url=out.get("video_url"), usage=resp.get("usage"))
        if status in ("FAILED", "CANCELED", "CANCELLED", "UNKNOWN"):
            return Poll("failed", error=fmt_error(out.get("code"), out.get("message")) if (out.get("code") or out.get("message")) else f"task {status.lower()}")
        if status == "RUNNING":
            return Poll("running")
        return Poll("pending")
