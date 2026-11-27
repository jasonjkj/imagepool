from imagepool.craft import translate

SRC = ("【合规】虚构\n【风格】时尚\n【身材】东亚女性身形\n【穿着】白衬衫\n"
       "【身体特征】东亚女性\n【主体】一名女性\n【画面】构图\n")


def test_backend_translates_and_keeps_titles():
    def backend(text, system):
        return "【合规】fiction\n【风格】fashion\n【身材】East Asian woman figure\n" \
               "【穿着】white shirt\n【身体特征】女性的\n【主体】a woman\n【画面】composition\n"
    en, note = translate.translate_craft_en(SRC, backend=backend)
    assert "【合规】" in en and "fiction" in en


def test_no_backend_returns_none():
    en, note = translate.translate_craft_en(SRC, backend=None)
    assert en is None and note


def test_backend_failure_returns_none():
    en, note = translate.translate_craft_en(SRC, backend=lambda t, s: None)
    assert en is None


def test_female_anchor_injected_when_missing():
    def backend(text, system):
        return "【合规】x\n【身材】slim\n【穿着】shirt\n【身体特征】fair\n【主体】a figure\n"
    en, _ = translate.translate_craft_en(SRC, backend=backend)
    assert "女性" in en


SCENE_SRC = "【合规】虚构\n【规格】竖屏\n【风格】写实\n【背景】山谷\n【画面】构图\n"


def test_scene_mode_no_female_anchor():
    def backend(text, system):
        assert "女性" not in system
        return "【合规】fiction\n【规格】portrait\n【风格】real\n【背景】valley\n【画面】comp\n"
    en, _ = translate.translate_craft_en(SCENE_SRC, backend=backend, mode="none")
    assert en is not None
    assert "女性" not in en


def test_person_mode_unchanged():
    def backend(text, system):
        return "【合规】x\n【身材】slim\n【穿着】shirt\n【身体特征】fair\n【主体】a figure\n"
    en, _ = translate.translate_craft_en(SRC, backend=backend)
    assert "女性" in en
