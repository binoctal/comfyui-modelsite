"""ComfyUI nodes (V3 schema). Imports ComfyUI, so keep pure logic in the other modules.

Deliberately NOT marked `is_api_node` and declaring no `Hidden.*comfy_org`
inputs: those flags make ComfyUI's frontend demand a comfy.org login, which is
exactly what this pack exists to avoid. The API key is never a widget (widget
values are written into workflow JSON and media metadata); it comes from the
Settings dialog, an environment variable, or the config file.
"""
import json
from io import BytesIO

from typing_extensions import override

from comfy_api.latest import ComfyExtension, IO, InputImpl

from . import catalog, engine, media
from .adapters.base import ImageRequest, VideoRequest
from .config import MissingApiKey

RESOLUTIONS = ["480p", "720p", "768p", "1080p"]
RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]
IMAGE_SIZES = ["2K", "1K", "2048x2048", "1024x1024", "2304x1728", "1728x2304", "2560x1440", "1440x2560"]
CATEGORY_VIDEO = "Modelsite/Video"
CATEGORY_IMAGE = "Modelsite/Image"


def _model_input(task):
    ids = [m.id for m in catalog.models_for_sync(task)]
    return IO.Combo.Input(
        "model",
        options=ids,
        default=ids[0] if ids else None,
        tooltip="Models are fetched from the Modelsite catalog when ComfyUI loads this page. Refresh the page to update the list.",
    )


def _custom_model_input():
    return IO.String.Input(
        "custom_model",
        default="",
        optional=True,
        tooltip="Optional. A model id that is not in the list yet (for example a model added after you loaded this page). Overrides 'model'.",
    )


def _progress(cls):
    try:
        from server import PromptServer

        node_id = cls.hidden.unique_id

        def cb(state, i):
            try:
                PromptServer.instance.send_progress_text(f"Modelsite: {state} (poll {i + 1})", node_id)
            except Exception:
                pass

        return cb
    except Exception:
        return None


def _interrupted():
    try:
        from comfy.model_management import processing_interrupted

        return processing_interrupted()
    except Exception:
        return False


def _usage_text(usage):
    return json.dumps(usage, ensure_ascii=False) if usage else ""


def _fail(e):
    """Turn package errors into the exception ComfyUI should show; keep the real message."""
    if isinstance(e, engine.Interrupted):
        from comfy.model_management import InterruptProcessingException

        raise InterruptProcessingException() from e
    raise RuntimeError(str(e.args[0]) if e.args else repr(e)) from e


async def _run_video(cls, **kw):
    first = kw.pop("first_frame", None)
    last = kw.pop("last_frame", None)
    timeout_minutes = kw.pop("timeout_minutes", 15)
    model = (kw.pop("custom_model", "") or "").strip() or kw.pop("model")
    kw.pop("model", None)
    req = VideoRequest(
        model=model,
        first_frame=media.tensor_to_data_url(first) if first is not None else None,
        last_frame=media.tensor_to_data_url(last) if last is not None else None,
        **kw,
    )
    try:
        res = await engine.generate_video(req, progress=_progress(cls), is_interrupted=_interrupted,
                                          timeout_s=int(timeout_minutes) * 60)
    except (engine.ModelsiteError, MissingApiKey, ValueError, KeyError) as e:
        _fail(e)
    return IO.NodeOutput(InputImpl.VideoFromFile(BytesIO(res.video_bytes)), res.task_id, _usage_text(res.usage))


def _video_inputs(task):
    ins = [
        _model_input(task),
        IO.String.Input("prompt", multiline=True, default="", tooltip="What the video should show. English or Chinese."),
        IO.Combo.Input("resolution", options=RESOLUTIONS, default="720p",
                       tooltip="Wan and HappyHorse accept 720p or 1080p only; Seedance 480p/720p/1080p; MiniMax H3 768p (H3 Max also 480p)."),
        IO.Combo.Input("ratio", options=RATIOS, default="16:9"),
        IO.Int.Input("duration", default=5, min=2, max=15, tooltip="Seconds. Seedance 4-15, Wan 2-15, HappyHorse 3-15, MiniMax per model."),
        IO.Int.Input("seed", default=-1, min=-1, max=2147483647, tooltip="-1 lets the model choose."),
        IO.Boolean.Input("generate_audio", default=True, tooltip="Seedance only; other models ignore it."),
        IO.Boolean.Input("watermark", default=False),
    ]
    return ins


def _video_optional():
    return [
        IO.String.Input("negative_prompt", multiline=True, default="", optional=True,
                        tooltip="Wan and HappyHorse only; other models ignore it."),
        IO.Int.Input("timeout_minutes", default=15, min=1, max=60, optional=True,
                     tooltip="How long to wait before giving up. A task that times out is NOT re-created and may still be billed."),
        _custom_model_input(),
    ]


_VIDEO_OUTPUTS = [
    IO.Video.Output(display_name="video"),
    IO.String.Output(display_name="task_id"),
    IO.String.Output(display_name="usage"),
]


class ModelsiteTextToVideo(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="ModelsiteTextToVideo",
            display_name="Modelsite Text to Video",
            category=CATEGORY_VIDEO,
            description="Generate a video from a text prompt with a model from the Modelsite catalog.",
            inputs=_video_inputs("t2v") + _video_optional(),
            outputs=_VIDEO_OUTPUTS,
            hidden=[IO.Hidden.unique_id],
        )

    @classmethod
    async def execute(cls, model, prompt, resolution, ratio, duration, seed, generate_audio, watermark,
                      negative_prompt="", timeout_minutes=15, custom_model=""):
        return await _run_video(cls, model=model, prompt=prompt, resolution=resolution, ratio=ratio, duration=duration,
                                seed=seed, generate_audio=generate_audio, watermark=watermark,
                                negative_prompt=negative_prompt, timeout_minutes=timeout_minutes, custom_model=custom_model)


class ModelsiteImageToVideo(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="ModelsiteImageToVideo",
            display_name="Modelsite Image to Video",
            category=CATEGORY_VIDEO,
            description="Animate a first frame (optionally ending on a last frame) with a model from the Modelsite catalog.",
            inputs=[IO.Image.Input("first_frame", tooltip="The first frame.")] + _video_inputs("i2v")
            + [IO.Image.Input("last_frame", optional=True, tooltip="Optional end frame (not supported by HappyHorse).")]
            + _video_optional(),
            outputs=_VIDEO_OUTPUTS,
            hidden=[IO.Hidden.unique_id],
        )

    @classmethod
    async def execute(cls, first_frame, model, prompt, resolution, ratio, duration, seed, generate_audio, watermark,
                      last_frame=None, negative_prompt="", timeout_minutes=15, custom_model=""):
        return await _run_video(cls, model=model, prompt=prompt, resolution=resolution, ratio=ratio, duration=duration,
                                seed=seed, generate_audio=generate_audio, watermark=watermark,
                                negative_prompt=negative_prompt, timeout_minutes=timeout_minutes, custom_model=custom_model,
                                first_frame=first_frame, last_frame=last_frame)


async def _run_image(cls, model, custom_model, prompt, size, watermark, images=()):
    model = (custom_model or "").strip() or model
    req = ImageRequest(model=model, prompt=prompt, size=size, watermark=watermark,
                       images=[media.tensor_to_data_url(i) for i in images if i is not None])
    try:
        res = await engine.generate_images(req)
    except (engine.ModelsiteError, MissingApiKey, ValueError, KeyError) as e:
        _fail(e)
    return IO.NodeOutput(media.bytes_to_tensor(res.images), _usage_text(res.usage))


_IMAGE_OUTPUTS = [IO.Image.Output(display_name="image"), IO.String.Output(display_name="usage")]


class ModelsiteTextToImage(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="ModelsiteTextToImage",
            display_name="Modelsite Text to Image",
            category=CATEGORY_IMAGE,
            description="Generate an image from a text prompt with a model from the Modelsite catalog.",
            inputs=[
                _model_input("t2i"),
                IO.String.Input("prompt", multiline=True, default=""),
                IO.Combo.Input("size", options=IMAGE_SIZES, default="2K"),
                IO.Boolean.Input("watermark", default=False),
                _custom_model_input(),
            ],
            outputs=_IMAGE_OUTPUTS,
            hidden=[IO.Hidden.unique_id],
        )

    @classmethod
    async def execute(cls, model, prompt, size, watermark, custom_model=""):
        return await _run_image(cls, model, custom_model, prompt, size, watermark)


class ModelsiteImageToImage(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id="ModelsiteImageToImage",
            display_name="Modelsite Image to Image",
            category=CATEGORY_IMAGE,
            description="Edit or restyle one to three reference images with a model from the Modelsite catalog.",
            inputs=[
                IO.Image.Input("image", tooltip="Reference image."),
                _model_input("i2i"),
                IO.String.Input("prompt", multiline=True, default=""),
                IO.Combo.Input("size", options=IMAGE_SIZES, default="2K"),
                IO.Boolean.Input("watermark", default=False),
                IO.Image.Input("image_2", optional=True),
                IO.Image.Input("image_3", optional=True),
                _custom_model_input(),
            ],
            outputs=_IMAGE_OUTPUTS,
            hidden=[IO.Hidden.unique_id],
        )

    @classmethod
    async def execute(cls, image, model, prompt, size, watermark, image_2=None, image_3=None, custom_model=""):
        return await _run_image(cls, model, custom_model, prompt, size, watermark, images=(image, image_2, image_3))


class ModelsiteExtension(ComfyExtension):
    @override
    async def get_node_list(self):
        return [ModelsiteTextToVideo, ModelsiteImageToVideo, ModelsiteTextToImage, ModelsiteImageToImage]
