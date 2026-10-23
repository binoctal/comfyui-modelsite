"""Schema-level checks that need ComfyUI importable (PYTHONPATH must contain the ComfyUI root)."""
import json

import pytest

pytest.importorskip("comfy_api")

from modelsite import comfy_nodes  # noqa: E402

NODES = [comfy_nodes.ModelsiteTextToVideo, comfy_nodes.ModelsiteImageToVideo,
         comfy_nodes.ModelsiteTextToImage, comfy_nodes.ModelsiteImageToImage]


@pytest.mark.parametrize("node", NODES)
def test_schema_is_valid_and_not_a_partner_node(node, api):
    schema = node.GET_SCHEMA()
    assert schema.is_api_node is False, "partner-node flag would trigger the comfy.org login gate"
    info = json.dumps(schema.get_v1_info(node).__dict__, default=str)
    assert "comfy_org" not in info
    names = {i.id for i in schema.inputs}
    assert "api_key" not in names and "apikey" not in names, "the key must never be a widget"
    assert "model" in names and "custom_model" in names


@pytest.mark.parametrize("node,expected,absent", [
    (comfy_nodes.ModelsiteTextToVideo, "wan2.7-t2v", "wan2.7-i2v"),
    (comfy_nodes.ModelsiteImageToVideo, "wan2.7-i2v", "wan2.7-t2v"),
    (comfy_nodes.ModelsiteTextToImage, "doubao-seedream-4.5", "qwen-image-2.0-pro"),
])
def test_model_options_come_from_the_catalog(node, expected, absent, api):
    schema = node.GET_SCHEMA()
    model = next(i for i in schema.inputs if i.id == "model")
    assert expected in model.options and absent not in model.options
    assert not any("SUPPLIER" in str(o) for o in model.options)


async def test_text_to_image_runs_through_a_node(api):
    out = await comfy_nodes.ModelsiteTextToImage.execute(model="doubao-seedream-4.5", prompt="p", size="2K", watermark=False)
    image = out.args[0]
    assert tuple(image.shape) == (1, 64, 64, 3)
    assert out.args[1] and "generated_images" in out.args[1]


async def test_missing_key_message_reaches_the_user(api, monkeypatch):
    monkeypatch.delenv("MODELSITE_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as e:
        await comfy_nodes.ModelsiteTextToImage.execute(model="doubao-seedream-4.5", prompt="p", size="2K", watermark=False)
    assert "MODELSITE_API_KEY" in str(e.value)
