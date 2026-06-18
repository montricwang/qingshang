"""把周邦彦原始整理文本解析成项目统一的结构化 JSON。

这是一个普通的命令行脚本，不受 FastAPI 控制。直接运行本文件时，最下方的
``if __name__ == "__main__"`` 会调用 main，流程依次为：读取文本、解析、Pydantic
校验、写 JSON、写人工复核报告。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# 直接运行 scripts/xxx.py 时，Python 默认只把 scripts 目录加入模块搜索路径。
# 手动加入项目根目录后，脚本才能导入 app 和 scripts 包中的模块。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.poem import PoemCore
from scripts.zhoubangyan_rules import (
    BODY_PUNCS,
    KNOWN_MODES,
    KNOWN_TUNE_NAMES,
    LINE_SPLIT_PUNCS,
    SERIES_MARKERS,
    SERIES_TOTAL_RE,
    TERMINAL_PUNCS,
)

INPUT_PATH = Path("data/working/zhoubangyan.txt")
OUTPUT_JSON_PATH = Path("data/generated/zhoubangyan_poems.json")
OUTPUT_REVIEW_PATH = Path("data/generated/zhoubangyan_review.md")

AUTHOR = "周邦彦"
AUTHOR_SLUG = "zhoubangyan"
DYNASTY = "宋"
SOURCE = "国学典籍网《全宋词·周邦彦》工作整理文本"


def clean_line(line: str) -> str:
    """去掉一行首尾空白和可能存在的 UTF-8 BOM 字符。"""
    return line.strip().replace("\ufeff", "")


def has_body_punc(line: str) -> bool:
    """判断文本中是否含有正文标点，用于区分元数据与词的正文。"""
    return any(ch in line for ch in BODY_PUNCS)


def is_preface_line(line: str) -> bool:
    """判断当前行是否是以【序】标记的题序。"""
    return line.startswith("【序】")


def is_again_marker(line: str) -> bool:
    """判断是否为“又”，该标记表示沿用上一首的词牌。"""
    return line == "又"


def is_series_marker(line: str) -> bool:
    """判断是否为“第一”“其二”等套词序号。"""
    if line in SERIES_MARKERS:
        return True

    if re.fullmatch(r"第[一二三四五六七八九十]+", line):
        return True

    if re.fullmatch(r"其[一二三四五六七八九十]+", line):
        return True

    return False


def is_tune_name(line: str) -> bool:
    """通过已知词牌集合判断一行是否是词牌名。"""
    return line in KNOWN_TUNE_NAMES


def parse_meta_line(line: str) -> dict[str, str | None]:
    """
    解析词牌下一行的宫调 / 题名 / 宫调+题名 / 二首别恨。
    例如：
    大石 -> musical_mode=大石
    大石秋怨 -> musical_mode=大石, title=秋怨
    二首别恨 -> title=别恨, series_label=第一
    三首正宫 -> musical_mode=正宫, series_label=第一
    """
    # 第一阶段：准备三个可能解析出的字段。
    series_label: str | None = None
    musical_mode: str | None = None
    title: str | None = None

    rest = line.strip()

    # 第二阶段：先移除“二首”“三首”等套词总数前缀。
    series_match = SERIES_TOTAL_RE.fullmatch(rest)
    if series_match:
        rest = series_match.group(2).strip()
        series_label = "第一"

    # 第三阶段：优先匹配较长宫调名，避免短名称抢先匹配。
    for mode in sorted(KNOWN_MODES, key=len, reverse=True):
        if rest == mode:
            musical_mode = mode
            rest = ""
            break

        if rest.startswith(mode):
            musical_mode = mode
            rest = rest[len(mode) :].strip()
            break

    if rest:
        title = rest

    return {
        "musical_mode": musical_mode,
        "title": title,
        "series_label": series_label,
    }


def make_poem_id(author_order: int) -> str:
    """根据作者内序号生成稳定 ID，例如 zhoubangyan-0001。"""
    return f"{AUTHOR_SLUG}-{author_order:04d}"


def make_current_poem(
    tune_name: str,
    musical_mode: str | None = None,
    title: str | None = None,
    series_label: str | None = None,
) -> dict[str, Any]:
    """创建解析中的临时诗词字典，后续逐行向其中补充内容。"""
    return {
        "tune_name": tune_name,
        "musical_mode": musical_mode,
        "title": title,
        "series_label": series_label,
        "preface": None,
        "body_paragraphs": [],
        "issues": [],
    }


def current_context(current: dict[str, Any]) -> dict[str, str | None]:
    """提取下一首套词可能继承的词牌、宫调和题名。"""
    return {
        "tune_name": current["tune_name"],
        "musical_mode": current["musical_mode"],
        "title": current["title"],
    }


def add_body_paragraph(current: dict[str, Any], line: str) -> None:
    """把正文行加入当前词；遇到意外换行时自动拼回上一段。"""
    body: list[str] = current["body_paragraphs"]

    # 如果上一段最后没有 ，。！？，认为是正文意外换行，直接拼回去。
    if body and body[-1] and body[-1][-1] not in TERMINAL_PUNCS:
        body[-1] += line
    else:
        body.append(line)


def split_lines(
    section_text: str, global_start_no: int
) -> tuple[list[dict[str, Any]], int]:
    """按正文标点切成词句，并返回词句列表和下一个全局编号。"""
    pieces = re.findall(
        rf"[^{LINE_SPLIT_PUNCS}]+[{LINE_SPLIT_PUNCS}]?",
        section_text,
    )

    lines: list[dict[str, Any]] = []
    global_line_no = global_start_no
    section_line_no = 1

    for piece in pieces:
        text = piece.strip()
        if not text:
            continue

        lines.append(
            {
                "global_line_no": global_line_no,
                "section_line_no": section_line_no,
                "text": text,
            }
        )
        global_line_no += 1
        section_line_no += 1

    return lines, global_line_no


def section_name_for(section_no: int, total_sections: int) -> str | None:
    """根据总片数和当前序号生成“上片”“第二叠”等显示名称。"""
    if total_sections == 1:
        return None

    if total_sections == 2:
        return "上片" if section_no == 1 else "下片"

    names = ["第一叠", "第二叠", "第三叠", "第四叠", "第五叠"]
    if section_no <= len(names):
        return names[section_no - 1]

    return None


def build_sections(body_paragraphs: list[str]) -> list[dict[str, Any]]:
    """把正文段落转换成带片内编号和全词编号的 sections 结构。"""
    sections: list[dict[str, Any]] = []
    global_line_no = 1
    total_sections = len(body_paragraphs)

    for index, section_text in enumerate(body_paragraphs, start=1):
        lines, global_line_no = split_lines(section_text, global_line_no)

        sections.append(
            {
                "section_no": index,
                "section_name": section_name_for(index, total_sections),
                "lines": lines,
            }
        )

    return sections


def find_suspicious(poem: dict[str, Any]) -> list[str]:
    """搜索已知的乱码或 OCR 异常，供人工复核报告使用。"""
    text = "\n".join(
        [
            poem.get("tune_name") or "",
            poem.get("musical_mode") or "",
            poem.get("title") or "",
            poem.get("series_label") or "",
            poem.get("preface") or "",
            poem.get("full_text") or "",
        ]
    )

    hits: list[str] = []

    if "□" in text:
        hits.append("存在缺字符号：□")

    if "�" in text:
        hits.append("存在乱码替换符：�")

    if "调节器" in text:
        hits.append("疑似 OCR 或录入错误：调节器")

    return hits


def parse_working_text(
    lines: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """逐行解析原始文本。

    输入：清洗前的文本行。
    输出：可写入 JSON 的诗词字典列表，以及供人工检查的报告项列表。
    ``current`` 表示当前正在组装、尚未提交到 poems 的一首词。
    """
    poems: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []

    current: dict[str, Any] | None = None
    last_context: dict[str, str | None] | None = None

    def flush_current() -> None:
        """结束当前词：构建 sections、生成 ID，并放入最终列表。"""
        nonlocal current, last_context

        if current is None:
            return

        if not current["body_paragraphs"]:
            review_items.append(
                {
                    "poem_id": None,
                    "author_order": len(poems) + 1,
                    "tune_name": current["tune_name"],
                    "issues": ["没有识别到正文"],
                }
            )
            last_context = current_context(current)
            current = None
            return

        author_order = len(poems) + 1
        sections = build_sections(current["body_paragraphs"])
        full_text = "\n".join(current["body_paragraphs"])

        poem = {
            "poem_id": make_poem_id(author_order),
            "author_order": author_order,
            "author": AUTHOR,
            "dynasty": DYNASTY,
            "tune_name": current["tune_name"],
            "musical_mode": current["musical_mode"],
            "title": current["title"],
            "series_label": current["series_label"],
            "preface": current["preface"],
            "full_text": full_text,
            "sections": sections,
            "source": SOURCE,
        }

        suspicious = find_suspicious(poem)
        issues = list(dict.fromkeys(current["issues"]))

        if suspicious:
            issues.append("正文中存在可疑字符")

        review_items.append(
            {
                "poem_id": poem["poem_id"],
                "author_order": author_order,
                "tune_name": poem["tune_name"],
                "musical_mode": poem["musical_mode"],
                "title": poem["title"],
                "series_label": poem["series_label"],
                "section_count": len(sections),
                "line_count": sum(len(section["lines"]) for section in sections),
                "issues": issues,
                "suspicious": suspicious,
            }
        )

        poems.append(poem)
        last_context = current_context(current)
        current = None

    # 主状态机：每次读取一行，根据当前是否已有正文决定它的含义。
    for raw_line in lines:
        line = clean_line(raw_line)

        if not line:
            continue

        if current is None:
            if not is_tune_name(line):
                review_items.append(
                    {
                        "poem_id": None,
                        "author_order": len(poems) + 1,
                        "tune_name": line,
                        "issues": ["起始行不是已知词牌，可能需要人工确认"],
                    }
                )

            current = make_current_poem(tune_name=line)
            continue

        body_started = bool(current["body_paragraphs"])

        if is_preface_line(line):
            current["preface"] = line.removeprefix("【序】").strip()
            continue

        if body_started and is_series_marker(line):
            if current.get("series_label") is None:
                current["series_label"] = "第一"

            inherited = current_context(current)
            flush_current()

            current = make_current_poem(
                tune_name=inherited["tune_name"] or "",
                musical_mode=inherited["musical_mode"],
                title=inherited["title"],
                series_label=line,
            )
            continue

        if body_started and is_again_marker(line):
            inherited = current_context(current)
            flush_current()

            current = make_current_poem(
                tune_name=inherited["tune_name"] or "",
                musical_mode=inherited["musical_mode"],
                title=None,
                series_label=None,
            )
            continue

        if body_started and not has_body_punc(line):
            if is_tune_name(line):
                flush_current()
                current = make_current_poem(tune_name=line)
            else:
                add_body_paragraph(current, line)
                current["issues"].append(f"疑似正文意外换行，已自动拼接：{line}")
            continue

        if not body_started and not has_body_punc(line):
            if is_series_marker(line):
                if last_context is None:
                    current["issues"].append(f"套词标记缺少可继承的上一首：{line}")
                    current["series_label"] = line
                else:
                    current["tune_name"] = (
                        last_context["tune_name"] or current["tune_name"]
                    )
                    current["musical_mode"] = last_context["musical_mode"]
                    current["title"] = last_context["title"]
                    current["series_label"] = line
                continue

            if is_again_marker(line):
                if last_context is None:
                    current["issues"].append("“又”缺少可继承的上一首")
                else:
                    current["tune_name"] = (
                        last_context["tune_name"] or current["tune_name"]
                    )
                    current["musical_mode"] = last_context["musical_mode"]
                    current["title"] = None
                continue

            meta = parse_meta_line(line)

            if meta["musical_mode"] is not None:
                current["musical_mode"] = meta["musical_mode"]

            if meta["title"] is not None:
                current["title"] = meta["title"]

            if meta["series_label"] is not None:
                current["series_label"] = meta["series_label"]

            continue

        add_body_paragraph(current, line)

    flush_current()

    return poems, review_items


def write_review(
    review_items: list[dict[str, Any]], poems: list[dict[str, Any]]
) -> None:
    """把解析统计和可疑项写成人工可读的 Markdown 报告。"""
    issue_items = [
        item for item in review_items if item.get("issues") or item.get("suspicious")
    ]

    lines: list[str] = []
    lines.append("# 周邦彦 working text 清洗报告")
    lines.append("")
    lines.append(f"- 清洗词作数：{len(poems)}")
    lines.append(f"- 需要人工确认：{len(issue_items)}")
    lines.append("")

    lines.append("## 需要人工确认")
    lines.append("")

    if not issue_items:
        lines.append("暂无。")
    else:
        for item in issue_items:
            lines.append(f"### {item.get('poem_id') or '未生成 poem_id'}")
            lines.append("")
            lines.append(f"- author_order: {item.get('author_order')}")
            lines.append(f"- 词牌: {item.get('tune_name')}")
            lines.append(f"- 宫调: {item.get('musical_mode')}")
            lines.append(f"- 题名: {item.get('title')}")
            lines.append(f"- 套词标签: {item.get('series_label')}")
            lines.append(f"- 问题: {'；'.join(item.get('issues') or [])}")
            lines.append(f"- 可疑字符: {'；'.join(item.get('suspicious') or [])}")
            lines.append("")

    lines.append("## 全部词作概览")
    lines.append("")

    for item in review_items:
        if item.get("poem_id") is None:
            continue

        lines.append(
            f"- {item['poem_id']} | "
            + f"序号={item.get('author_order')} | "
            + f"词牌={item.get('tune_name')} | "
            + f"宫调={item.get('musical_mode')} | "
            + f"题名={item.get('title')} | "
            + f"套词={item.get('series_label')} | "
            + f"片数={item.get('section_count')} | "
            + f"解释单位数={item.get('line_count')}"
        )

    _ = OUTPUT_REVIEW_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """命令行脚本入口：读取、解析、验证并写出结果文件。"""
    # 第一阶段：读取输入文件。
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"找不到输入文件：{INPUT_PATH}")

    raw_lines = INPUT_PATH.read_text(encoding="utf-8").splitlines()

    # 第二阶段：把非结构化文本解析成 Python 字典。
    poems, review_items = parse_working_text(raw_lines)

    # 第三阶段：Pydantic 逐首验证。任一结构不合规则立即报错并停止写文件。
    validated_poems = [
        PoemCore.model_validate(poem).model_dump(mode="json") for poem in poems
    ]

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 第四阶段：验证全部成功后，再写结构化 JSON 和复核报告。
    _ = OUTPUT_JSON_PATH.write_text(
        json.dumps(validated_poems, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    write_review(review_items, validated_poems)

    print(f"清洗词作数：{len(validated_poems)}")
    print(f"输出 JSON：{OUTPUT_JSON_PATH}")
    print(f"输出 review：{OUTPUT_REVIEW_PATH}")


if __name__ == "__main__":
    main()
