"""覆盖 Reader 中不依赖浏览器的展示整理逻辑。"""

from apps.reader_app import _card_html, _group_tool_errors, _poem_label


def test_group_tool_errors_keeps_each_error_in_its_tool() -> None:
    grouped = _group_tool_errors(
        [
            "reference: CNKGraph 返回 HTTP 404",
            "allusion: CNKGraph 请求超时",
            "char[章]: CNKGraph 返回 HTTP 404",
        ]
    )

    assert grouped == {
        "reference": ["CNKGraph 返回 HTTP 404"],
        "allusion": ["CNKGraph 请求超时"],
        "char": ["CNKGraph 返回 HTTP 404"],
    }


def test_poem_label_uses_series_label_to_distinguish_repeated_tunes() -> None:
    label = _poem_label(
        {
            "tune_name": "少年游",
            "title": None,
            "series_label": "其二",
        }
    )

    assert label == "少年游 · 其二"


def test_evidence_card_escapes_external_text() -> None:
    card = _card_html(
        anchor_text="<章台>",
        title="候选",
        body="正文",
        detail=None,
        source_ref=None,
    )

    assert "&lt;章台&gt;" in card
    assert "<章台>" not in card
