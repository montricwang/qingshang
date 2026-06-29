"""Reader 的诗句展示整理函数。

这里的函数都是纯展示逻辑：不访问数据库、不请求后端，也不修改原文数据。
输入是 sections/lines 的 dict 结构，输出是特定阅读模式所需的排版数据。
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
    fragment_no: int           # 在当前句中是第几个分片
    text: str                  # 干净的原文（点击时回填到右侧查询框）
    display_text: str          # 带缩进的显示文本（用于渲染）
    indent_level: int          # 缩进级数（每级两个全角空格）
    source_line_text: str      # 原始完整句子文本（用于定位）


# ========================================================================
# 起句尾标点清理
# ========================================================================

def strip_trailing_pause(text: str) -> str:
    """只移除起句末尾连续出现的中文停顿标点。

    例如 "河桥送人处。" → "河桥送人处"
    """
    return TRAILING_PAUSE_PATTERN.sub("", text)


# ========================================================================
# 慢读分片
# ========================================================================

def _should_end_fragment(
    char: str,
    next_char: str | None,
    pending_stop: str | None,
) -> bool:
    """判断当前字符是否是一个分片的结尾。

    分片结束的条件：
    ① 前面遇到了一个句读标点（pending_stop 不为空）
    ② 当前字符是一个句读标点且下一个字符不是句读或闭合符号
       → 例如"晴山。"中的"。"，下一字为空，分片结束
    ③ 当前字符是闭合符号且下一个字符不是闭合符号
       → 例如"玉台新咏序》"中的"》"，下一字非》"，分片结束
       （如果下一个字还是闭合符号，说明是嵌套闭合，不在此结束）
    """
    if pending_stop is None:
        return False

    # 情况②：当前是句读标点，下一字不是句读或闭合符号
    is_stop_pause_end = (
        char in BREATHING_STOPS
        and (next_char is None or next_char not in (BREATHING_STOPS | CLOSING_MARKS))
    )

    # 情况③：当前是闭合符号，下一字不是闭合符号
    is_closing_mark_end = (
        char in CLOSING_MARKS
        and (next_char is None or next_char not in CLOSING_MARKS)
    )

    return is_stop_pause_end or is_closing_mark_end


def _make_breathing_fragment(
    *,
    line_no: int,
    fragment_no: int,
    text: str,
    indent_level: int,
    source_line_text: str,
) -> BreathingFragment:
    """把一段原文包装成慢读模式需要的展示结构。"""
    return BreathingFragment(
        line_no=line_no,
        fragment_no=fragment_no,
        text=text,
        display_text=f"{FULL_WIDTH_INDENT * indent_level}{text}",
        indent_level=indent_level,
        source_line_text=source_line_text,
    )


def _next_indent_level(current: int, stop_mark: str | None) -> int:
    """根据刚结束的句读标点，计算下一分片的缩进级别。"""
    return current + 1 if stop_mark in SOFT_STOPS else 0


def _split_line_into_breathing_fragments(
    *,
    line_no: int,
    source_line_text: str,
    initial_indent_level: int,
) -> tuple[list[BreathingFragment], int]:
    """把一条 poem_line 按句读切成慢读分片，并返回新的缩进级别。"""
    fragments: list[BreathingFragment] = []
    buffer = ""
    fragment_no = 0
    indent_level = initial_indent_level
    pending_stop: str | None = None

    for char_index, char in enumerate(source_line_text):
        buffer += char
        if char in BREATHING_STOPS:
            pending_stop = char

        next_char = (
            source_line_text[char_index + 1]
            if char_index + 1 < len(source_line_text)
            else None
        )
        if not _should_end_fragment(char, next_char, pending_stop):
            continue

        fragment_no += 1
        fragments.append(_make_breathing_fragment(
            line_no=line_no,
            fragment_no=fragment_no,
            text=buffer,
            indent_level=indent_level,
            source_line_text=source_line_text,
        ))
        buffer = ""
        indent_level = _next_indent_level(indent_level, pending_stop)
        pending_stop = None

    if buffer:
        fragment_no += 1
        fragments.append(_make_breathing_fragment(
            line_no=line_no,
            fragment_no=fragment_no,
            text=buffer,
            indent_level=indent_level,
            source_line_text=source_line_text,
        ))

    return fragments, indent_level


def build_breathing_fragments(
    sections: list[dict[str, Any]],
) -> list[list[BreathingFragment]]:
    """按句读拆出慢读分片，并在每个 section 内维护视觉缩进。

    缩进规则：
    - 每个 section 从 0 级缩进开始
    - 遇到逗号（软停顿）后缩进加一级
    - 遇到句号（硬停顿）后缩进归零
    - 每个分片前追加 indent_level × 两个全角空格

    例如 "南都石黛扫晴山。" → 一个分片，缩进 0
      "细草愁烟，幽花怯露，凭栏总是销魂处。"
        → 三个分片："细草愁烟，"（缩进 0）
                    "　　幽花怯露，"（缩进 1）
                    "凭栏总是销魂处。"（缩进 0）
    """
    section_fragments: list[list[BreathingFragment]] = []

    for section in sections:
        indent_level = 0
        fragments: list[BreathingFragment] = []

        for line in section.get("lines", []):
            line_fragments, indent_level = _split_line_into_breathing_fragments(
                line_no=line["global_line_no"],
                source_line_text=line["text"],
                initial_indent_level=indent_level,
            )
            fragments.extend(line_fragments)

        section_fragments.append(fragments)

    return section_fragments


# ========================================================================
# 转轮 / 领读 辅助
# ========================================================================

def flatten_poem_lines(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 section 与句序展开所有 poem_line，供转轮和领读逐句定位。"""
    return [line for section in sections for line in section.get("lines", [])]


def bounded_line_index(current: int, delta: int, line_count: int) -> int:
    """在 0 到 line_count-1 范围内安全移动当前句号索引。

    例如：current=0, delta=1, line_count=3 → 1
          current=2, delta=1, line_count=3 → 2（不越界）
    """
    if line_count <= 0:
        return 0
    return min(max(current + delta, 0), line_count - 1)
