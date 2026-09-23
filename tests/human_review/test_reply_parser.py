"""Reply parser tests."""

from app.human_review.reply_parser import extract_short_code, parse_reply_content


def test_extract_short_code() -> None:
    assert extract_short_code("确认是误报 #EVT-a1b2c3d4 谢谢") == "a1b2c3d4"


def test_extract_short_code_missing() -> None:
    assert extract_short_code("没有标签的回复") is None


def test_parse_reply_content_strips_tag() -> None:
    short, body = parse_reply_content("用户出差中 #EVT-deadbeef")
    assert short == "deadbeef"
    assert "deadbeef" not in body
    assert "出差" in body
