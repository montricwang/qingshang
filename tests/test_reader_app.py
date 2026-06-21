"""覆盖 Reader 中不依赖浏览器的展示整理逻辑。"""

from apps.reader_app import (
    _card_html,
    _group_tool_errors,
    _poem_label,
    _strip_trailing_pause,
    bounded_line_index,
    build_breathing_fragments,
    flatten_poem_lines,
)


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


def test_strip_trailing_pause_only_removes_terminal_pause_marks() -> None:
    assert _strip_trailing_pause("还见褪粉梅梢，。") == "还见褪粉梅梢"
    assert _strip_trailing_pause("知谁伴、名园露饮，") == "知谁伴、名园露饮"
    assert _strip_trailing_pause("《章台路》。") == "《章台路》"
    assert _strip_trailing_pause("“章台路。”") == "“章台路。”"


def test_breathing_fragments_carry_indent_across_source_lines() -> None:
    sections = [
        {
            "lines": [
                {"global_line_no": 1, "text": "侵晨浅约宫黄，"},
                {"global_line_no": 2, "text": "障风映袖，"},
                {"global_line_no": 3, "text": "盈盈笑语。"},
                {"global_line_no": 4, "text": "归来旧处。"},
            ]
        }
    ]

    fragments = build_breathing_fragments(sections)[0]

    assert [item["display_text"] for item in fragments] == [
        "侵晨浅约宫黄，",
        "　　障风映袖，",
        "　　　　盈盈笑语。",
        "归来旧处。",
    ]


def test_breathing_fragments_split_multiple_commas_without_dirtying_text() -> None:
    sections = [
        {
            "lines": [
                {
                    "global_line_no": 4,
                    "text": "跳脱添金双腕重，琵琶破拨四弦悲。",
                }
            ]
        }
    ]

    fragments = build_breathing_fragments(sections)[0]

    assert [item["text"] for item in fragments] == [
        "跳脱添金双腕重，",
        "琵琶破拨四弦悲。",
    ]
    assert [item["display_text"] for item in fragments] == [
        "跳脱添金双腕重，",
        "　　琵琶破拨四弦悲。",
    ]
    assert all(item["line_no"] == 4 for item in fragments)


def test_breathing_fragments_reset_indent_for_each_section() -> None:
    sections = [
        {"lines": [{"global_line_no": 1, "text": "前一片，"}]},
        {"lines": [{"global_line_no": 2, "text": "后一片起句，"}]},
    ]

    fragments = build_breathing_fragments(sections)

    assert fragments[0][0]["indent_level"] == 0
    assert fragments[1][0]["indent_level"] == 0


def test_breathing_fragments_keep_closing_marks_with_the_pause() -> None:
    sections = [
        {
            "lines": [
                {"global_line_no": 1, "text": "「前句，」后句。」"},
            ]
        }
    ]

    fragments = build_breathing_fragments(sections)[0]

    assert [item["text"] for item in fragments] == ["「前句，」", "后句。」"]
    assert fragments[1]["indent_level"] == 1


def test_flatten_poem_lines_preserves_section_order() -> None:
    sections = [
        {"lines": [{"global_line_no": 1, "text": "上片。"}]},
        {"lines": [{"global_line_no": 2, "text": "下片。"}]},
    ]

    assert [line["global_line_no"] for line in flatten_poem_lines(sections)] == [1, 2]


def test_bounded_line_index_stops_at_poem_edges() -> None:
    assert bounded_line_index(0, -1, 3) == 0
    assert bounded_line_index(0, 1, 3) == 1
    assert bounded_line_index(2, 1, 3) == 2
    assert bounded_line_index(0, 1, 0) == 0
