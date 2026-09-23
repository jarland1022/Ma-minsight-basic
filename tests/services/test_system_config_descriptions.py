from app.services.system_config_descriptions import description_zh


def test_description_zh_known_key() -> None:
    text = description_zh("investigation.batch_size")
    assert text is not None
    assert "调查" in text


def test_description_zh_fallback() -> None:
    assert description_zh("unknown.key", "备用说明") == "备用说明"
