import asyncio

import pytest

from modelsite import engine
from modelsite.adapters.base import ImageRequest, VideoRequest
from modelsite.config import MissingApiKey
from tests.conftest import KEY


async def nosleep(_s):
    return None


def vreq(model, **kw):
    base = dict(model=model, prompt="a cat", resolution="720p", ratio="16:9", duration=5, seed=-1,
                generate_audio=True, watermark=False)
    base.update(kw)
    return VideoRequest(**base)


def creates(api):
    return [r for r in api.requests if r[0] == "POST"]


async def test_ark_video_end_to_end(api):
    api.polls = 2
    res = await engine.generate_video(vreq("dreamina-seedance-2-0-mini", resolution="480p", duration=4), sleep=nosleep)
    assert res.task_id == "cgt-1" and res.video_bytes.startswith(b"\x00\x00\x00\x18ftyp")
    assert res.usage == {"completion_tokens": 40594, "total_tokens": 40594}
    posts = creates(api)
    assert len(posts) == 1, "creation must happen exactly once"
    assert posts[0][2]["Authorization"] == f"Bearer {KEY}"
    # the signed media URL is third-party: the key must not travel there
    media = [r for r in api.requests if r[1] == "/media/video.mp4"]
    assert media and all("Authorization" not in r[2] for r in media)


async def test_dashscope_video_end_to_end(api):
    res = await engine.generate_video(vreq("wan2.7-t2v"), sleep=nosleep)
    assert res.task_id == "video_1"
    post = creates(api)[0]
    assert post[2].get("X-DashScope-Async") == "enable"
    assert post[3]["parameters"]["resolution"] == "720P"


async def test_minimax_video_end_to_end(api):
    res = await engine.generate_video(vreq("minimax-h3", resolution="768p", duration=4), sleep=nosleep)
    assert res.task_id == "mm-1" and res.video_bytes


async def test_failed_task_surfaces_upstream_message_and_never_recreates(api):
    api.fail_poll = True
    with pytest.raises(engine.ModelsiteError) as e:
        await engine.generate_video(vreq("dreamina-seedance-2-0"), sleep=nosleep)
    assert "SensitiveContent" in str(e.value) and "refused by upstream" in str(e.value)
    assert len(creates(api)) == 1


async def test_create_error_is_shown_and_not_retried(api):
    api.create_status = 400
    with pytest.raises(engine.ModelsiteError) as e:
        await engine.generate_video(vreq("dreamina-seedance-2-0"), sleep=nosleep)
    assert "bad resolution" in str(e.value) and "400" in str(e.value)
    assert len(creates(api)) == 1


async def test_unauthorized_hint_without_leaking_the_key(api, monkeypatch):
    monkeypatch.setenv("MODELSITE_API_KEY", "sk-ms-" + "b" * 64)
    with pytest.raises(engine.ModelsiteError) as e:
        await engine.generate_video(vreq("dreamina-seedance-2-0"), sleep=nosleep)
    msg = str(e.value)
    assert "401" in msg and ("API Key" in msg or "api key" in msg.lower())
    assert "b" * 64 not in msg


async def test_missing_key_fails_before_any_request(api, monkeypatch):
    monkeypatch.delenv("MODELSITE_API_KEY", raising=False)
    with pytest.raises(MissingApiKey):
        await engine.generate_video(vreq("dreamina-seedance-2-0"), sleep=nosleep)
    assert not creates(api)


async def test_interrupt_stops_polling_without_recreating(api):
    api.polls = 100
    calls = {"n": 0}

    def interrupted():
        calls["n"] += 1
        return calls["n"] > 3

    with pytest.raises(engine.Interrupted):
        await engine.generate_video(vreq("dreamina-seedance-2-0"), sleep=nosleep, is_interrupted=interrupted)
    assert len(creates(api)) == 1


async def test_timeout_reports_task_id_so_charges_can_be_traced(api):
    api.polls = 10_000
    clock = {"t": 0.0}

    async def fake_sleep(s):
        clock["t"] += s

    with pytest.raises(engine.ModelsiteTimeout) as e:
        await engine.generate_video(vreq("dreamina-seedance-2-0"), sleep=fake_sleep, timeout_s=60, now=lambda: clock["t"])
    assert "cgt-1" in str(e.value)
    assert len(creates(api)) == 1


async def test_progress_callback_is_called(api):
    api.polls = 3
    seen = []
    await engine.generate_video(vreq("dreamina-seedance-2-0"), sleep=nosleep, progress=lambda s, i: seen.append(s))
    assert "running" in seen and seen[-1] == "succeeded"


async def test_quickstart_path_is_preferred_when_the_model_publishes_one(api):
    await engine.generate_video(vreq("dreamina-seedance-2-0"), sleep=nosleep)
    # the fake quickstart for seedance publishes /api/v3/contents/..., which must be used
    assert creates(api)[0][1] == "/api/v3/contents/generations/tasks"
    assert any(r[1].startswith("/api/v3/contents/generations/tasks/") for r in api.requests if r[0] == "GET")


async def test_falls_back_to_builtin_path_when_quickstart_missing(api):
    await engine.generate_video(vreq("dreamina-seedance-2-0-mini", resolution="480p"), sleep=nosleep)
    assert creates(api)[0][1] == "/v1/contents/generations/tasks"


async def test_images_end_to_end(api):
    res = await engine.generate_images(ImageRequest(model="doubao-seedream-4.5", prompt="p", size="2K", watermark=False))
    assert len(res.images) == 1 and res.images[0][:4] == b"\x89PNG"
    assert res.usage["generated_images"] == 1
    assert len(creates(api)) == 1


async def test_error_messages_never_contain_the_key(api):
    api.create_status = 400
    with pytest.raises(engine.ModelsiteError) as e:
        await engine.generate_video(vreq("dreamina-seedance-2-0"), sleep=nosleep)
    assert KEY not in str(e.value)


async def test_unrouted_quickstart_path_falls_back_without_double_creating(api):
    """A plain-text 404 means the prefix is not routed (the request never reached the handler),
    so retrying on the built-in path cannot create a second task."""
    api.hide_paths = {"/api/v3/contents/generations/tasks", "/api/v3/contents/generations/tasks/cgt-1"}
    res = await engine.generate_video(vreq("dreamina-seedance-2-0"), sleep=nosleep)
    assert res.task_id == "cgt-1"
    assert api.next_id == 1, "exactly one task must exist server-side"
    paths = [r[1] for r in creates(api)]
    assert paths == ["/api/v3/contents/generations/tasks", "/v1/contents/generations/tasks"]


async def test_a_json_404_is_a_real_answer_and_is_not_retried(api):
    api.create_status = 404
    with pytest.raises(engine.ModelsiteError):
        await engine.generate_video(vreq("dreamina-seedance-2-0-mini", resolution="480p"), sleep=nosleep)
    assert len(creates(api)) == 1


def test_error_hints_do_not_repeat_the_server_message():
    assert "Top up" in engine._hint(402)
    assert "API key" in engine._hint(401) and engine._hint(500) == ""
