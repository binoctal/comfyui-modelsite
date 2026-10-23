"""IMAGE tensor <-> bytes helpers (ComfyUI IMAGE = float32 tensor [B, H, W, C] in 0..1)."""
import base64
from io import BytesIO

import numpy as np
from PIL import Image


def tensor_to_data_url(image, index=0, max_side=2048):
    """First (or `index`-th) image of a batch as a PNG data URL, downscaled so no side exceeds max_side."""
    arr = image[index] if getattr(image, "ndim", 3) == 4 else image
    arr = arr.detach().cpu().numpy() if hasattr(arr, "detach") else np.asarray(arr)
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    if arr.shape[-1] == 4:
        arr = arr[..., :3]
    img = Image.fromarray(arr, "RGB")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def bytes_to_tensor(batch):
    """List of encoded images -> one IMAGE batch tensor (later images are resized to the first one's size)."""
    import torch

    arrays = []
    size = None
    for raw in batch:
        img = Image.open(BytesIO(raw)).convert("RGB")
        if size is None:
            size = img.size
        elif img.size != size:
            img = img.resize(size, Image.LANCZOS)
        arrays.append(np.asarray(img).astype(np.float32) / 255.0)
    return torch.from_numpy(np.stack(arrays, axis=0))
