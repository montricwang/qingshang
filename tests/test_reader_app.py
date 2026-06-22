"""覆盖 Reader 中不依赖浏览器的展示整理逻辑。"""

from apps.reader_app import (
    _all_candidates_have_no_evidence,
    _candidate_selection_payload,
    _candidate_type_label,
    _card_html,
    _evidence_preview_html,
    _evidence_count_text,
    _evidence_status_text,
    _group_tool_errors,
    _long_evidence_entries,
    _poem_label,
    _strip_trailing_pause,
    _truncate_evidence_text,
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


def test_candidate_evidence_preview_escapes_external_text() -> None:
    preview = _evidence_preview_html(
        {
            "source": "cnkgraph_allusion",
            "query_used": "<燕台句>",
            "status": "hit",
            "hit_count": 1,
            "displayed_count": 1,
            "truncated": False,
            "items": [
                {
                    "title": "<燕台诗>",
                    "claim": "候选<script>",
                    "evidence_text": "引文",
                    "source_ref": "来源",
                }
            ],
        }
    )

    assert "&lt;燕台句&gt;" in preview
    assert "&lt;燕台诗&gt;" in preview
    assert "<script>" not in preview


def test_candidate_evidence_status_copy_is_explicit() -> None:
    assert _evidence_status_text("hit") == "命中候选证据"
    assert _evidence_status_text("no_result") == "无结果"
    assert _evidence_status_text("error") == "查询错误"
    assert _evidence_status_text("partial_error", overall=True) == "候选证据部分查询失败"
    assert _all_candidates_have_no_evidence(
        [{"overall_status": "no_result"}, {"overall_status": "no_result"}]
    )


def test_candidate_type_uses_chinese_display_labels() -> None:
    assert _candidate_type_label("allusion") == "典故"
    assert _candidate_type_label("literary_reference") == "文献化用"
    assert _candidate_type_label("historical_place") == "历史地名"
    assert _candidate_type_label("cultural_institution") == "礼俗制度"
    assert _candidate_type_label("conventional_motif") == "惯用母题"
    assert _candidate_type_label("uncertain") == "待查"


def test_evidence_count_does_not_call_zero_display_truncated() -> None:
    assert _evidence_count_text(
        {"hit_count": 1, "displayed_count": 0, "truncated": True}
    ) == "命中 1 · 暂无可展示条目"
    assert _evidence_count_text(
        {"hit_count": 9, "displayed_count": 0, "truncated": True}
    ) == "命中 9 · 暂无可展示条目"
    assert _evidence_count_text(
        {"hit_count": 9, "displayed_count": 3, "truncated": True}
    ) == "命中 9 · 展示 3 · 已截断"


def test_long_evidence_is_shortened_but_full_text_remains_foldable() -> None:
    short_preview, short_full = _truncate_evidence_text("短引文", limit=10)
    long_text = "长" * 200
    long_preview, long_full = _truncate_evidence_text(long_text, limit=10)

    assert (short_preview, short_full) == ("短引文", None)
    assert long_preview == "长" * 10 + "…"
    assert long_full == long_text
    assert _long_evidence_entries(
        {"items": [{"title": "长引文", "evidence_text": long_text}]}
    ) == [("长引文", long_text)]


def test_evidence_preview_marks_current_poem_and_hides_long_full_text() -> None:
    long_text = "原文" * 100
    preview = _evidence_preview_html(
        {
            "source": "cnkgraph_reference",
            "query_used": "南都石黛",
            "status": "hit",
            "hit_count": 1,
            "displayed_count": 1,
            "truncated": False,
            "items": [
                {
                    "title": "少年游",
                    "context_relation": "current_poem",
                    "evidence_text": long_text,
                    "source_ref": "宋 周邦彦 《少年游》",
                }
            ],
        }
    )

    assert "当前作品命中" in preview
    assert "长引文已折叠" in preview
    assert long_text not in preview


def test_candidate_selection_uses_anchor_not_query_variants() -> None:
    payload = _candidate_selection_payload(
        {
            "line_no": 12,
            "anchor_text": "燕台句",
            "query_variants": ["燕台句", "燕台诗", "李商隐 燕台诗"],
        }
    )

    assert payload == (12, "燕台句")


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
