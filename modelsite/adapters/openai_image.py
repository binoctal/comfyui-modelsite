"""OpenAI-style image entrance (Seedream): synchronous POST /v1/images/generations."""
from .base import Call


class OpenAIImageAdapter:
    family = "openai_image"
    create_path = "/v1/images/generations"

    def create_image(self, req):
        body = {
            "model": req.model,
            "prompt": req.prompt,
            "size": req.size,
            "watermark": req.watermark,
            "response_format": "url",
            "n": 1,
        }
        if req.images:
            body["image"] = req.images[0] if len(req.images) == 1 else list(req.images)
        return Call("POST", self.create_path, body)

    def parse_images(self, resp):
        out = []
        for item in (resp or {}).get("data") or []:
            if item.get("url"):
                out.append(("url", item["url"]))
            elif item.get("b64_json"):
                out.append(("b64", item["b64_json"]))
        return out
