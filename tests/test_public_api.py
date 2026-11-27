import imagepool



def test_orchestrator_exports():
    assert callable(imagepool.build_craft)
    assert callable(imagepool.generate_image)
    assert callable(imagepool.render)


def test_contract_export():
    from imagepool.contract import ShotSpec
    assert ShotSpec


def test_pool_api_unchanged():
    for name in ("load_config", "save_config", "generate", "save_image"):
        assert hasattr(imagepool, name), name
