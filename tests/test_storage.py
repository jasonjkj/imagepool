"""落盘层 save_image（迁移自旧 save_image，298-334 行，仅 CACHE → out_dir 参数化）。
"""
from imagepool import _net
from imagepool.storage import save_image


def _mock_get_bytes(monkeypatch, content):
    def fake(url, timeout=30):
        return content
    monkeypatch.setattr(_net, "_get_bytes", fake)


def test_data_uri_png_written(tmp_path):
    p = save_image("data:image/png;base64,QUJD", "sensenova", out_dir=str(tmp_path))
    assert p is not None and p.endswith(".png")
    assert tmp_path.joinpath(p.rsplit("/", 1)[-1]).read_bytes() == b"ABC"


def test_data_uri_jpeg_uses_jpg_ext(tmp_path):
    p = save_image("data:image/jpeg;base64,QUJD", "sensenova", out_dir=str(tmp_path))
    assert p is not None and p.endswith(".jpg")


def test_url_download_saved(tmp_path, monkeypatch):
    _mock_get_bytes(monkeypatch, b"BLOB")
    p = save_image("https://i.test/x.png?auth=1", "qwen", out_dir=str(tmp_path))
    assert p is not None
    assert tmp_path.joinpath(p.rsplit("/", 1)[-1]).read_bytes() == b"BLOB"


def test_url_download_fail_returns_none(tmp_path, monkeypatch):
    _mock_get_bytes(monkeypatch, None)
    assert save_image("https://i.test/x.png", "qwen", out_dir=str(tmp_path)) is None


def test_to_data_uri_local_file(tmp_path):
    from imagepool.storage import to_data_uri
    p = tmp_path / "a.png"; p.write_bytes(b"\x89PNG\r\n")
    assert to_data_uri(str(p)).startswith("data:image/png;base64,")


def test_to_data_uri_passthrough():
    from imagepool.storage import to_data_uri
    assert to_data_uri("data:image/jpeg;base64,AAAA").startswith("data:image/jpeg")
    assert to_data_uri("https://x.test/a.jpg") == "https://x.test/a.jpg"


def test_to_data_uri_missing_raises():
    import pytest
    from imagepool.storage import to_data_uri
    with pytest.raises(OSError):
        to_data_uri("/no/such/file.png")


def test_to_data_uri_non_string_raises():
    import pytest
    from imagepool.storage import to_data_uri
    with pytest.raises(OSError):
        to_data_uri(None)