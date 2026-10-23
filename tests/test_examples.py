"""The shipped example workflows must be valid for the adapters and must never carry a key."""
import json
import pathlib
import re

import pytest

from modelsite.adapters import get_adapter
from modelsite.adapters.base import ImageRequest, VideoRequest

EXAMPLES = sorted((pathlib.Path(__file__).resolve().parent.parent / "examples").glob("*.json"))
FRAME = "data:image/png;base64,AAAA"


def _nodes(path):
    return json.loads(path.read_text(encoding="utf-8"))["nodes"]


def test_examples_exist():
    names = {p.name for p in EXAMPLES}
    for required in ("image-to-video-wan27.json", "image-to-video-happyhorse11.json",
                     "image-to-video-minimax-h3.json", "text-to-video-minimax-h3.json"):
        assert required in names


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_has_no_secret(path):
    text = path.read_text(encoding="utf-8")
    assert not re.search(r"sk-ms-|Bearer |api[_-]?key|@[a-z0-9.-]+\.(com|ai|dev)", text, re.I)
    # no absolute local path either
    assert not re.search(r"(?:^|[\s\"'])/(?:home|Users|root)/", text)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_builds_a_valid_request(path):
    for n in _nodes(path):
        w = n.get("widgets_values") or []
        if n["type"] in ("ModelsiteTextToVideo", "ModelsiteImageToVideo"):
            model, prompt, resolution, ratio, duration = w[0], w[1], w[2], w[3], w[4]
            req = VideoRequest(model=model, prompt=prompt, resolution=resolution, ratio=ratio, duration=duration,
                               first_frame=FRAME if n["type"] == "ModelsiteImageToVideo" else None)
            call = get_adapter(model).create(req)  # raises on an unsupported combination
            assert call.json["model"] or call.json.get("model") is None
        elif n["type"] in ("ModelsiteTextToImage", "ModelsiteImageToImage"):
            model, prompt, size = w[0], w[1], w[2]
            call = get_adapter(model).create_image(ImageRequest(
                model=model, prompt=prompt, size=size,
                images=[FRAME] if n["type"] == "ModelsiteImageToImage" else []))
            assert call.json["model"] == model
