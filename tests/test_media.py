import pytest

torch = pytest.importorskip("torch")

from modelsite import media  # noqa: E402


def test_tensor_to_data_url_roundtrip_and_downscale():
    t = torch.rand(1, 3000, 1500, 3)
    url = media.tensor_to_data_url(t)
    assert url.startswith("data:image/png;base64,")
    import base64
    from io import BytesIO
    from PIL import Image
    img = Image.open(BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert max(img.size) <= 2048


def test_bytes_to_tensor_batch_resizes_to_first():
    from io import BytesIO
    from PIL import Image
    def png(size):
        b = BytesIO(); Image.new("RGB", size, (1, 2, 3)).save(b, "PNG"); return b.getvalue()
    t = media.bytes_to_tensor([png((64, 32)), png((10, 10))])
    assert tuple(t.shape) == (2, 32, 64, 3) and t.dtype == torch.float32
