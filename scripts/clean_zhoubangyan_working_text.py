from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.poem import PoemCore

INPUT_PATH = Path("data/working/zhoubangyan.txt")
OUTPUT_JSON_PATH = Path("data/generated/zhoubangyan_poems.json")
OUTPUT_REVIEW_PATH = Path("data/generated/zhoubangyan_review.md")

AUTHOR = "周邦彦"
AUTHOR_SLUG = "zhoubangyan"
DYNASTY = "宋"
SOURCE = "国学典籍网《全宋词·周邦彦》工作整理文本"


KNOWN_TUNE_NAMES = {
    "瑞龙吟",
    "锁窗寒",
    "风流子",
    "渡江云",
    "应天长",
    "荔枝香近",
    "还京乐",
    "扫地花",
    "解连环",
    "玲珑四犯",
    "丹凤吟",
    "满江红",
    "瑞鹤仙",
    "西平乐",
    "浪涛沙",
    "浪淘沙",
    "忆旧游",
    "蓦山溪",
    "少年游",
    "秋蕊香",
    "渔家傲",
    "南乡子",
    "望江南",
    "浣沙溪",
    "浣溪沙慢",
    "迎春乐",
    "点绛唇",
    "一落索",
    "垂丝钓",
    "满庭芳",
    "隔浦莲",
    "法曲献仙音",
    "过秦楼",
    "侧犯",
    "塞翁吟",
    "苏幕遮",
    "诉衷情",
    "伤情怨",
    "红林檎近",
    "满路花",
    "解语花",
    "六么令",
    "倒犯",
    "大酺",
    "玉烛新",
    "花犯",
    "丑奴儿",
    "水龙吟",
    "六丑",
    "虞美人",
    "兰陵王",
    "蝶恋花",
    "西河",
    "归去难",
    "三部乐",
    "菩萨蛮",
    "品令",
    "玉楼春",
    "木兰花",
    "木兰花令",
    "黄鹂绕碧树",
    "绮寮怨",
    "拜星月",
    "尉迟杯",
    "绕佛阁",
    "一寸金",
    "如梦令",
    "月中行",
    "意难忘",
    "定风波",
    "红罗袄",
    "夜游宫",
    "夜飞鹊",
    "早梅芳",
    "凤来朝",
    "芳草渡",
    "感皇恩",
    "玉团儿",
    "粉蝶儿慢",
    "红窗迥",
    "念奴娇",
    "燕归梁",
    "南浦",
    "醉落魄",
    "留客住",
    "长相思",
    "看花回",
    "月下笛",
    "无闷",
    "琴调相思引",
    "青房并蒂莲",
    "青玉案",
    "一剪梅",
    "鹊桥仙令",
    "花心动",
    "双头莲",
    "大有",
    "减字木兰花",
    "南柯子",
    "关河令",
    "万里春",
    "鹤冲天",
    "烛影摇红",
    "失调名",
    "十六字令",
    "华胥引",
    "宴清都",
    "四园竹",
    "齐天乐",
    "霜叶飞",
    "蕙兰芳引",
    "塞垣春",
    "丁香结",
    "氐州第一",
    "解蹀躞",
    "庆春宫",
    "醉桃源",
}

KNOWN_MODES = [
    "仙吕调",
    "中吕宫",
    "黄钟宫",
    "般涉调",
    "仙吕",
    "中吕",
    "正宫",
    "黄钟",
    "大石",
    "小石",
    "商调",
    "越调",
    "歇指",
    "双调",
    "高平",
    "般涉",
    "正平",
    "高调",
    "林钟",
    "道宫",
]

SERIES_MARKERS = {
    "第一",
    "第二",
    "第三",
    "第四",
    "第五",
    "第六",
    "第七",
    "第八",
    "第九",
    "第十",
    "其一",
    "其二",
    "其三",
    "其四",
    "其五",
    "其六",
    "其七",
    "其八",
    "其九",
    "其十",
}

# 断句只切这些：逗号、句号、问号、叹号
# 不切顿号、分号
LINE_SPLIT_PUNCS = "，。！？"
BODY_PUNCS = set(LINE_SPLIT_PUNCS)
TERMINAL_PUNCS = set(LINE_SPLIT_PUNCS)

SERIES_TOTAL_RE = re.compile(r"^([一二三四五六七八九十]+)首(.*)$")


def clean_line(line: str) -> str:
    return line.strip().replace("\ufeff", "")


def has_body_punc(line: str) -> bool:
    return any(ch in line for ch in BODY_PUNCS)


def is_preface_line(line: str) -> bool:
    return line.startswith("【序】")


def is_again_marker(line: str) -> bool:
    return line == "又"


def is_series_marker(line: str) -> bool:
    if line in SERIES_MARKERS:
        return True

    if re.fullmatch(r"第[一二三四五六七八九十]+", line):
        return True

    if re.fullmatch(r"其[一二三四五六七八九十]+", line):
        return True

    return False


def is_tune_name(line: str) -> bool:
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
    series_label: str | None = None
    musical_mode: str | None = None
    title: str | None = None

    rest = line.strip()

    series_match = SERIES_TOTAL_RE.fullmatch(rest)
    if series_match:
        rest = series_match.group(2).strip()
        series_label = "第一"

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
    return f"{AUTHOR_SLUG}-{author_order:04d}"


def make_current_poem(
    tune_name: str,
    musical_mode: str | None = None,
    title: str | None = None,
    series_label: str | None = None,
) -> dict[str, Any]:
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
    return {
        "tune_name": current["tune_name"],
        "musical_mode": current["musical_mode"],
        "title": current["title"],
    }


def add_body_paragraph(current: dict[str, Any], line: str) -> None:
    body: list[str] = current["body_paragraphs"]

    # 如果上一段最后没有 ，。！？，认为是正文意外换行，直接拼回去。
    if body and body[-1] and body[-1][-1] not in TERMINAL_PUNCS:
        body[-1] += line
    else:
        body.append(line)


def split_lines(
    section_text: str, global_start_no: int
) -> tuple[list[dict[str, Any]], int]:
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
    if total_sections == 1:
        return None

    if total_sections == 2:
        return "上片" if section_no == 1 else "下片"

    names = ["第一叠", "第二叠", "第三叠", "第四叠", "第五叠"]
    if section_no <= len(names):
        return names[section_no - 1]

    return None


def build_sections(body_paragraphs: list[str]) -> list[dict[str, Any]]:
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
    poems: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []

    current: dict[str, Any] | None = None
    last_context: dict[str, str | None] | None = None

    def flush_current() -> None:
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
            f"序号={item.get('author_order')} | "
            f"词牌={item.get('tune_name')} | "
            f"宫调={item.get('musical_mode')} | "
            f"题名={item.get('title')} | "
            f"套词={item.get('series_label')} | "
            f"片数={item.get('section_count')} | "
            f"解释单位数={item.get('line_count')}"
        )

    OUTPUT_REVIEW_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"找不到输入文件：{INPUT_PATH}")

    raw_lines = INPUT_PATH.read_text(encoding="utf-8").splitlines()

    poems, review_items = parse_working_text(raw_lines)

    validated_poems = [
        PoemCore.model_validate(poem).model_dump(mode="json") for poem in poems
    ]

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_JSON_PATH.write_text(
        json.dumps(validated_poems, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    write_review(review_items, validated_poems)

    print(f"清洗词作数：{len(validated_poems)}")
    print(f"输出 JSON：{OUTPUT_JSON_PATH}")
    print(f"输出 review：{OUTPUT_REVIEW_PATH}")


if __name__ == "__main__":
    main()
