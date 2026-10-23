import json

from modelsite import catalog


async def test_lists_only_video_and_image_models_and_never_exposes_provider(api):
    models = await catalog.get_models()
    ids = {m.id for m in models}
    assert "deepseek-v4" not in ids  # chat is out of scope
    assert "dreamina-seedance-2-0" in ids and "doubao-seedream-4.5" in ids
    blob = json.dumps([m.__dict__ for m in models])
    assert "SUPPLIER" not in blob, "the provider field must never reach the package's data model"
    assert not any(hasattr(m, "provider") for m in models)


async def test_task_filtering_by_family_and_mode(api):
    t2v = {m.id for m in await catalog.models_for("t2v")}
    i2v = {m.id for m in await catalog.models_for("i2v")}
    t2i = {m.id for m in await catalog.models_for("t2i")}
    assert "dreamina-seedance-2-0" in t2v and "wan2.7-t2v" in t2v and "happyhorse-1.1-t2v" in t2v
    assert "wan2.7-i2v" not in t2v and "wan2.7-t2v" not in i2v
    assert "dreamina-seedance-2-0" in i2v and "wan2.7-i2v" in i2v and "happyhorse-1.1-i2v" in i2v and "minimax-h3" in i2v
    assert t2i == {"doubao-seedream-4.5"}  # only families we know how to call


async def test_falls_back_to_bundled_list_when_server_is_down(api):
    api.models_status = 500
    catalog.clear_cache()
    models = await catalog.get_models()
    assert models, "offline fallback must not be empty"
    assert any(m.id == "dreamina-seedance-2-0" for m in models)


async def test_cache_avoids_refetch_within_ttl(api):
    await catalog.get_models()
    n = sum(1 for r in api.requests if r[1] == "/api/models")
    await catalog.get_models()
    assert sum(1 for r in api.requests if r[1] == "/api/models") == n


def test_family_classification():
    assert catalog.family_of("dreamina-seedance-2-0-mini") == "ark"
    assert catalog.family_of("wan2.7-t2v") == "dashscope"
    assert catalog.family_of("happyhorse-1.0-i2v-20260618") == "dashscope"
    assert catalog.family_of("minimax-h3-max") == "minimax"
    assert catalog.family_of("doubao-seedream-5.0-lite") == "openai_image"
    assert catalog.family_of("something-new") is None


def test_bundled_fallback_has_no_supplier_fields():
    data = json.loads(open(catalog.FALLBACK_PATH).read())
    assert data and all(set(m) <= {"id", "name", "category"} for m in data)
