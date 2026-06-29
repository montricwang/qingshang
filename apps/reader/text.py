"""Reader 的诗句展示整理函数。

这里的函数都是纯展示逻辑：不访问数据库、不请求后端，也不修改原文数据。
"""

from __future__ import annotations

from typing import Any, TypedDict

from apps.reader.config import (
    BREATHING_STOPS,
    CLOSING_MARKS,
    FULL_WIDTH_INDENT,
    SOFT_STOPS,
    TRAILING_PAUSE_PATTERN,
)


class BreathingFragment(TypedDict):
    """一段可点击的慢读文本及其原始词句定位。"""

    line_no: int
    fragment_no: int
    text: str
    display_text: str
    indent_level: int
    source_line_text: str


def strip_trailing_pause(text: str) -> str:
    """只移除起句末尾连续出现的中文停顿标点。"""
    return TRAILING_PAUSE_PATTERN.sub("", text)


def build_breathing_fragments(
    sections: list[dict[str, Any]],
) -> list[list[BreathingFragment]]:
    """按句读拆出慢读分片，并在每个 section 内维护视觉缩进。"""
    section_fragments: list[list[BreathingFragment]] = []

    for section in sections:
        indent_level = 0
        fragments: list[BreathingFragment] = []

        for line in section.get("lines", []):
            line_no = line["global_line_no"]
            source_line_text = line["text"]
            buffer = ""
            fragment_no = 0
            pending_stop: str | None = None

            for char_index, char in enumerate(source_line_text):
                buffer += char
                next_char = (
                    source_line_text[char_index + 1]
                    if char_index + 1 < len(source_line_text)
                    else None
                )
                if char in BREATHING_STOPS:
                    pending_stop = char
                is_fragment_end = bool(
                    pending_stop
                    and (
                        char in BREATHING_STOPS
                        and next_char not in BREATHING_STOPS | CLOSING_MARKS
                        or char in CLOSING_MARKS
                        and next_char not in CLOSING_MARKS
                    )
                )
                if not is_fragment_end:
                    continue

                fragment_no += 1
                fragments.append(
                    BreathingFragment(
                        line_no=line_no,
                        fragment_no=fragment_no,
                        text=buffer,
                        display_text=f"{FULL_WIDTH_INDENT * indent_level}{buffer}",
                        indent_level=indent_level,
                        source_line_text=source_line_text,
                    )
                )
                buffer = ""
                indent_level = indent_level + 1 if pending_stop in SOFT_STOPS else 0
                pending_stop = None

            if buffer:
                fragment_no += 1
                fragments.append(
                    BreathingFragment(
                        line_no=line_no,
                        fragment_no=fragment_no,
                        text=buffer,
                        display_text=f"{FULL_WIDTH_INDENT * indent_level}{buffer}",
                        indent_level=indent_level,
                        source_line_text=source_line_text,
                    )
                )

        section_fragments.append(fragments)

    return section_fragments


def flatten_poem_lines(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 section 与句序展开原始 poem_line，供转轮和领读定位。"""
    return [line for section in sections for line in section.get("lines", [])]


def bounded_line_index(current: int, delta: int, line_count: int) -> int:
    """在词作句子范围内移动当前索引。"""
    if line_count <= 0:
        return 0
    return min(max(current + delta, 0), line_count - 1)

