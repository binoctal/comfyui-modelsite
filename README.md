# Modelsite for ComfyUI

Video and image generation nodes for ComfyUI, backed by the [Modelsite](https://modelsite.ai) model catalog.

- **One API key.** No comfy.org account, no credits, no sign-in gate.
- **The model list updates itself.** New models appear in the dropdown when you reload the page; no waiting for a ComfyUI release.
- **Plain nodes.** Text to Video, Image to Video, Text to Image, Image to Image. Output goes straight into the standard `Save Video` / `Save Image` nodes.

## Install

Through ComfyUI Manager, search for **Modelsite**. Or by hand:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/binoctal/comfyui-modelsite
```

Restart ComfyUI. The pack has no extra Python dependencies.

## Set your API key

Get a key from your Modelsite dashboard (`sk-ms-...`), then either:

1. Open **Settings → Modelsite → Connection** in ComfyUI and paste it into **API key**. It is stored on your machine only and is **never saved into workflows or into generated files**; or
2. Set the `MODELSITE_API_KEY` environment variable before starting ComfyUI.

The default API address is `https://api.modelsite.ai`. Change it under the same Settings page, or with `MODELSITE_BASE_URL`, only if you were given another address.

## Nodes

All nodes live under **Modelsite/Video** and **Modelsite/Image** (double-click the canvas and search "Modelsite").

| Node | What it does |
|---|---|
| Modelsite Text to Video | Prompt → video |
| Modelsite Image to Video | First frame (and optional last frame) → video |
| Modelsite Text to Image | Prompt → image |
| Modelsite Image to Image | 1–3 reference images + prompt → image |

Video nodes output `video`, `task_id` and `usage` (the usage numbers the API returned; the pack never computes prices). Image nodes output `image` and `usage`.

### Models

The `model` dropdown is filled from the live catalog when the page loads. Families the pack knows how to call:

| Family | Video | Image |
|---|---|---|
| Seedance 2.0 / 2.0 mini | text, first frame, first+last frame | — |
| Wan 2.7 | text, first frame, first+last frame | — |
| HappyHorse 1.0 / 1.1 | text, first frame | — |
| MiniMax H3 / H3 Max | text, first frame, first+last frame | — |
| Seedream 4.0 / 4.5 / 5.0 lite | — | text, reference images |

A model added to the catalog after you loaded the page can be used right away: type its id into **custom_model** (it overrides the dropdown), or reload the page.

### Parameters worth knowing

- **resolution** — Wan and HappyHorse accept `720p` / `1080p` only. Seedance `480p` / `720p` / `1080p`. MiniMax H3 `768p` (H3 Max also `480p`). An unsupported value is refused before anything is sent.
- **duration** — Seedance 4–15 s, Wan 2–15 s, HappyHorse 3–15 s, MiniMax H3 4–15 s (H3 Max 5–15 s).
- **seed** — `-1` lets the model choose. The default `control after generate = randomize` also makes every run different, which is what you want for a paid API node (ComfyUI would otherwise reuse the cached result).
- **generate_audio** — Seedance only. **negative_prompt** — Wan and HappyHorse only. Other models ignore them.
- **HappyHorse image-to-video** takes a first frame only; connecting a last frame is an error.
- Reference **videos and audio** are not supported yet (they need an upload step).

## Safety behaviour

- **A task is created exactly once.** If the request fails after it was sent, or the wait times out, or you cancel, the pack does **not** create it again — a second creation could be billed twice. The error message includes the task id so you can look it up in your usage log.
- Waiting uses backoff polling and can be interrupted with ComfyUI's cancel button.
- Error messages from the API are shown as they are. Your key is removed from every error message and log line.
- Result links are time-limited signed URLs; the pack downloads the file immediately and never sends your key to those hosts.

## Configuration reference

| Setting | Settings page | Environment | File |
|---|---|---|---|
| API key | Modelsite → API key | `MODELSITE_API_KEY` | `user/modelsite/config.json` (mode 600) |
| API address | Modelsite → API base URL | `MODELSITE_BASE_URL` | same file |
| Config folder | — | `MODELSITE_CONFIG_DIR` | — |

Priority: value set in the Settings page this session > environment > file.

## Examples

`examples/` has four ready workflows (drag a file onto the canvas). Image workflows use `example.png` from ComfyUI's input folder; replace it with your own image.

## Development

```bash
pip install pytest pytest-asyncio aiohttp pillow numpy
pytest          # runs against a local fake of the API; set PYTHONPATH to a ComfyUI checkout to include the node-schema tests
```

## License

MIT
