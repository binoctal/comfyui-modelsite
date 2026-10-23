import pytest

from modelsite.adapters import get_adapter
from modelsite.adapters.base import ImageRequest, VideoRequest


def vreq(model, **kw):
    base = dict(model=model, prompt="a cat", resolution="720p", ratio="16:9", duration=5, seed=-1,
                generate_audio=True, watermark=False)
    base.update(kw)
    return VideoRequest(**base)


def test_ark_text_to_video_body():
    a = get_adapter("dreamina-seedance-2-0")
    call = a.create(vreq("dreamina-seedance-2-0", resolution="480P", duration=4))
    assert call.method == "POST" and call.path == "/v1/contents/generations/tasks"
    b = call.json
    assert b["model"] == "dreamina-seedance-2-0"
    assert b["content"] == [{"type": "text", "text": "a cat"}]
    assert b["resolution"] == "480p"  # lowercased for Ark
    assert b["ratio"] == "16:9" and b["duration"] == 4
    assert b["generate_audio"] is True and b["watermark"] is False
    assert "seed" not in b  # -1 means random: do not send


def test_ark_seed_sent_when_set():
    b = get_adapter("dreamina-seedance-2-0").create(vreq("dreamina-seedance-2-0", seed=42)).json
    assert b["seed"] == 42


def test_ark_first_and_last_frame_roles():
    a = get_adapter("dreamina-seedance-2-0")
    b = a.create(vreq("dreamina-seedance-2-0", first_frame="data:image/png;base64,AAA", last_frame="data:image/png;base64,BBB")).json
    assert b["content"][0] == {"type": "text", "text": "a cat"}
    assert b["content"][1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}, "role": "first_frame"}
    assert b["content"][2] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,BBB"}, "role": "last_frame"}


def test_ark_task_id_and_poll_parsing():
    a = get_adapter("dreamina-seedance-2-0")
    assert a.task_id({"id": "cgt-1"}) == "cgt-1"
    assert a.poll_call("cgt-1").path == "/v1/contents/generations/tasks/cgt-1"
    assert a.parse_poll({"status": "queued"}).state == "pending"
    assert a.parse_poll({"status": "running"}).state == "running"
    ok = a.parse_poll({"status": "succeeded", "content": {"video_url": "http://x/v.mp4"}, "usage": {"completion_tokens": 7}})
    assert ok.state == "succeeded" and ok.url == "http://x/v.mp4" and ok.usage == {"completion_tokens": 7}
    bad = a.parse_poll({"status": "failed", "error": {"code": "SensitiveContent", "message": "refused"}})
    assert bad.state == "failed" and "SensitiveContent" in bad.error and "refused" in bad.error
    assert a.parse_poll({"status": "expired"}).state == "failed"


def test_dashscope_text_to_video_body_and_header():
    a = get_adapter("wan2.7-t2v")
    call = a.create(vreq("wan2.7-t2v", resolution="720p", negative_prompt="blur"))
    assert call.path == "/api/v1/services/aigc/video-generation/video-synthesis"
    assert call.headers == {"X-DashScope-Async": "enable"}
    b = call.json
    assert b["model"] == "wan2.7-t2v"
    assert b["input"] == {"prompt": "a cat", "negative_prompt": "blur"}
    assert b["parameters"]["resolution"] == "720P"  # uppercased for DashScope
    assert b["parameters"]["ratio"] == "16:9" and b["parameters"]["duration"] == 5
    assert b["parameters"]["watermark"] is False
    assert "generate_audio" not in b["parameters"]  # not a DashScope parameter on these models


def test_dashscope_rejects_480p_before_any_request():
    with pytest.raises(ValueError) as e:
        get_adapter("wan2.7-t2v").create(vreq("wan2.7-t2v", resolution="480p"))
    assert "720P" in str(e.value) and "1080P" in str(e.value)


def test_dashscope_image_to_video_media_roles():
    a = get_adapter("wan2.7-i2v")
    b = a.create(vreq("wan2.7-i2v", first_frame="data:image/png;base64,AAA", last_frame="data:image/png;base64,BBB")).json
    assert b["input"]["media"] == [{"type": "first_frame", "url": "data:image/png;base64,AAA"},
                                    {"type": "last_frame", "url": "data:image/png;base64,BBB"}]


def test_happyhorse_accepts_only_first_frame():
    a = get_adapter("happyhorse-1.1-i2v")
    ok = a.create(vreq("happyhorse-1.1-i2v", first_frame="data:image/png;base64,AAA")).json
    assert ok["input"]["media"] == [{"type": "first_frame", "url": "data:image/png;base64,AAA"}]
    with pytest.raises(ValueError):
        a.create(vreq("happyhorse-1.1-i2v", first_frame="data:image/png;base64,AAA", last_frame="data:image/png;base64,BBB"))


def test_image_to_video_requires_first_frame():
    with pytest.raises(ValueError):
        get_adapter("wan2.7-i2v").create(vreq("wan2.7-i2v"))


def test_dashscope_parse():
    a = get_adapter("wan2.7-t2v")
    assert a.task_id({"output": {"task_id": "video_9", "task_status": "PENDING"}}) == "video_9"
    assert a.poll_call("video_9").path == "/api/v1/tasks/video_9"
    assert a.parse_poll({"output": {"task_status": "PENDING"}}).state == "pending"
    assert a.parse_poll({"output": {"task_status": "RUNNING"}}).state == "running"
    ok = a.parse_poll({"output": {"task_status": "SUCCEEDED", "video_url": "http://x/v.mp4"}, "usage": {"duration": 5}})
    assert ok.state == "succeeded" and ok.url == "http://x/v.mp4" and ok.usage == {"duration": 5}
    bad = a.parse_poll({"output": {"task_status": "FAILED", "code": "DataInspectionFailed", "message": "blocked"}})
    assert bad.state == "failed" and "DataInspectionFailed" in bad.error and "blocked" in bad.error
    assert a.parse_poll({"output": {"task_status": "UNKNOWN"}}).state == "failed"


def test_minimax_body_and_parse():
    a = get_adapter("minimax-h3")
    call = a.create(vreq("minimax-h3", resolution="768p", duration=4))
    assert call.path == "/v2/video_generation"
    assert call.json["model"] == "MiniMax-H3" and call.json["resolution"] == "768P"
    assert call.json["duration"] == 4 and call.json["content"] == [{"type": "text", "text": "a cat"}]
    assert call.json["ratio"] == "16:9", "MiniMax requires a concrete ratio for text-to-video"
    assert get_adapter("minimax-h3-max").create(vreq("minimax-h3-max", resolution="480p", duration=5)).json["model"] == "MiniMax-H3-Max"
    assert a.task_id({"task_id": "mm-1"}) == "mm-1"
    assert a.poll_call("mm-1").path == "/v2/query/video_generation/mm-1"
    assert a.parse_poll({"task": {"status": "Running"}}).state == "running"
    ok = a.parse_poll({"task": {"status": "succeeded", "content": {"url": "http://x/v.mp4"}, "usage": {"total_seconds": 4}}})
    assert ok.state == "succeeded" and ok.url == "http://x/v.mp4" and ok.usage == {"total_seconds": 4}
    assert a.parse_poll({"task": {"status": "Failed"}}).state == "failed"


def test_openai_image_body_variants():
    a = get_adapter("doubao-seedream-4.5")
    call = a.create_image(ImageRequest(model="doubao-seedream-4.5", prompt="p", size="2K", watermark=False))
    assert call.path == "/v1/images/generations"
    assert call.json == {"model": "doubao-seedream-4.5", "prompt": "p", "size": "2K", "watermark": False,
                         "response_format": "url", "n": 1}
    i2i = a.create_image(ImageRequest(model="doubao-seedream-4.5", prompt="p", size="2K", watermark=True,
                                      images=["data:image/png;base64,AAA"]))
    assert i2i.json["image"] == "data:image/png;base64,AAA"
    multi = a.create_image(ImageRequest(model="doubao-seedream-4.5", prompt="p", size="2K", watermark=True,
                                        images=["data:image/png;base64,AAA", "data:image/png;base64,BBB"]))
    assert multi.json["image"] == ["data:image/png;base64,AAA", "data:image/png;base64,BBB"]
    assert a.parse_images({"data": [{"url": "http://x/1.png"}, {"b64_json": "QUJD"}]}) == [("url", "http://x/1.png"), ("b64", "QUJD")]


def test_unknown_family_is_a_clear_error():
    with pytest.raises(KeyError) as e:
        get_adapter("some-new-model")
    assert "some-new-model" in str(e.value)


def test_minimax_image_to_video_uses_adaptive_ratio_and_frame_roles():
    a = get_adapter("minimax-h3")
    b = a.create(vreq("minimax-h3", resolution="768p", duration=4, ratio="16:9",
                      first_frame="data:image/png;base64,AAA", last_frame="data:image/png;base64,BBB")).json
    assert b["ratio"] == "adaptive"  # follows the input image; a concrete value is ignored upstream
    assert b["content"][1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}, "role": "first_frame"}
    assert b["content"][2] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,BBB"}, "role": "last_frame"}
