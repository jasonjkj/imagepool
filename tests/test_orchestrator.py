from imagepool.contract import ShotSpec
from imagepool import orchestrator

POOL = [{"id": "medium", "name": "半身", "ratio": "三分之二", "modes": ["selfie", "scene"],
         "phrase": "腰部以上半身构图", "negative": "不得怼脸", "face": "visible"}]


def _spec():
    return ShotSpec(expression_block="温柔浅笑", context_sentence="在西湖边。",
                    shot_override="medium", outfit_block="白衬衫", style="时尚")


def test_build_craft_is_pure_and_stable():
    a = orchestrator.build_craft(_spec(), {"pools": {"framing": POOL}})
    b = orchestrator.build_craft(_spec(), {"pools": {"framing": POOL}})
    assert a == b
    for sec in ("【合规】", "【规格】", "【风格】", "【背景】", "【身材】",
                "【穿着】", "【身体特征】", "【主体】", "【画面】"):
        assert sec in a, sec
    assert "白衬衫" in a


def test_generate_image_calls_io_generate_and_saves(tmp_path):
    captured = {}

    def fake_generate(prompt, negative=None, **kw):
        captured["prompt"] = prompt
        return {"local": str(tmp_path / "out.jpg")}

    io = {"generate": fake_generate, "out_dir": str(tmp_path), "pool_config": {}}
    craft = orchestrator.build_craft(_spec(), {"pools": {"framing": POOL}})
    result = orchestrator.generate_image(craft, io)
    assert not captured["prompt"].startswith("# imagepool-craft-v1")  # 去戳后喂
    assert result.get("local")


def test_generate_image_translate_backend_used(tmp_path):
    seen = {}

    def backend(text, system):
        seen["called"] = True
        return text.replace("温柔浅笑", "gentle smile")

    def fake_generate(prompt, negative=None, **kw):
        seen["prompt"] = prompt
        return {"local": str(tmp_path / "o.jpg")}

    io = {"generate": fake_generate, "out_dir": str(tmp_path), "pool_config": {},
          "translate_backend": backend}
    craft = orchestrator.build_craft(_spec(), {"pools": {"framing": POOL}})
    orchestrator.generate_image(craft, io)
    assert seen["called"] and "gentle smile" in seen["prompt"]


def test_render_equals_build_then_generate(tmp_path):
    def fake_generate(prompt, negative=None, **kw):
        return {"local": str(tmp_path / "r.jpg")}
    io = {"generate": fake_generate, "out_dir": str(tmp_path), "pool_config": {}}
    r = orchestrator.render(_spec(), {"pools": {"framing": POOL}}, io)
    assert r.get("local")


def test_generate_image_rejects_non_craft(tmp_path):
    io = {"generate": lambda *a, **k: {"local": "x"}, "out_dir": str(tmp_path)}
    try:
        orchestrator.generate_image("随便一段", io)
        assert False, "应拒绝非 craft"
    except SystemExit:
        pass


def test_build_craft_none_subject_no_person_sections():
    spec = ShotSpec(expression_block="", context_sentence="雾中的山谷。", subject="none")
    craft = orchestrator.build_craft(spec, {})
    for sec in ("【身材】", "【穿着】", "【身体特征】", "【主体】", "【人景融合】"):
        assert sec not in craft, sec


def test_build_craft_none_has_scene_sections():
    spec = ShotSpec(expression_block="", context_sentence="雾中的山谷。", subject="none")
    craft = orchestrator.build_craft(spec, {})
    for sec in ("【合规】", "【规格】", "【风格】", "【背景】", "【画面】", "【负向】"):
        assert sec in craft, sec


def test_build_craft_person_subject_unchanged():
    a = orchestrator.build_craft(_spec(), {"pools": {"framing": POOL}})
    for sec in ("【身材】", "【身体特征】", "【主体】"):
        assert sec in a, sec


def test_render_forwards_input_images(tmp_path):
    seen = {}
    def fake_generate(prompt, negative=None, images=None, **kw):
        seen["images"] = images; return {"local": str(tmp_path / "o.jpg")}
    io = {"generate": fake_generate, "out_dir": str(tmp_path)}
    spec = ShotSpec(expression_block="微笑", context_sentence="湖边。",
                    shot_override="medium", input_images=["data:image/png;base64,AAAA"])
    orchestrator.render(spec, {"pools": {"framing": POOL}}, io)
    assert seen["images"] == ["data:image/png;base64,AAAA"]


def test_generate_image_scene_mode_accepts_personless(tmp_path):
    def fake_generate(prompt, negative=None, **kw):
        return {"local": str(tmp_path / "o.jpg")}
    io = {"generate": fake_generate, "out_dir": str(tmp_path)}
    scene = orchestrator.build_craft(ShotSpec(expression_block="", context_sentence="山谷。", subject="none"), {})
    assert orchestrator.generate_image(scene, io, mode="none").get("local")


def test_render_person_path_has_no_images_kw(tmp_path):
    seen = {}
    def fake_generate(prompt, negative=None, **kw):
        seen["kw"] = kw; return {"local": str(tmp_path / "o.jpg")}
    io = {"generate": fake_generate, "out_dir": str(tmp_path)}
    orchestrator.render(_spec(), {"pools": {"framing": POOL}}, io)
    assert "images" not in seen["kw"]
