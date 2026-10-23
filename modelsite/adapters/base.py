from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoRequest:
    model: str
    prompt: str
    resolution: str = "720p"
    ratio: str = "16:9"
    duration: int = 5
    seed: int = -1  # -1 = let the model pick (not sent)
    generate_audio: bool = True
    watermark: bool = False
    negative_prompt: str = ""
    first_frame: str | None = None  # data URL
    last_frame: str | None = None


@dataclass
class ImageRequest:
    model: str
    prompt: str
    size: str = "2K"
    watermark: bool = False
    images: list = field(default_factory=list)  # data URLs for image-to-image


@dataclass
class Call:
    method: str
    path: str
    json: Any = None
    headers: dict = field(default_factory=dict)


@dataclass
class Poll:
    state: str  # pending | running | succeeded | failed
    url: str | None = None
    error: str | None = None
    usage: dict | None = None


def fmt_error(code, message):
    parts = [p for p in (code, message) if p]
    return ": ".join(str(p) for p in parts) if parts else "unknown error"
