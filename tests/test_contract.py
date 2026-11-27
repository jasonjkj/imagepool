from imagepool.contract import ShotSpec


def test_required_fields():
    spec = ShotSpec(expression_block="温柔浅笑", context_sentence="在西湖边。")
    assert spec.expression_block == "温柔浅笑"
    assert spec.pose_block is None and spec.shot_override is None


def test_business_blocks_default_none():
    spec = ShotSpec(expression_block="x", context_sentence="y。")
    assert spec.outfit_block is None and spec.kink_block is None and spec.style is None


def test_size_default_portrait():
    assert ShotSpec(expression_block="x", context_sentence="y。").size == "portrait"


def test_subject_defaults_to_person():
    assert ShotSpec(expression_block="x", context_sentence="y。").subject == "person"


def test_input_images_default_none():
    assert ShotSpec(expression_block="x", context_sentence="y。").input_images is None
    assert ShotSpec(expression_block="x", context_sentence="y。", input_images=["a"]).input_images == ["a"]
