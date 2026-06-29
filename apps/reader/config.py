"""Reader 的稳定配置、中文标签和样式常量。

这个模块不发网络请求，也不渲染页面。它只集中保存 Reader 各层都会用到的
常量，避免这些配置散落在主页面脚本里。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HERO_IMAGE = PROJECT_ROOT / "apps/assets/reader-landscape.webp"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
API_TIMEOUT_SECONDS = 45.0
REVIEW_TIMEOUT_SECONDS = float(os.getenv("QINGSHANG_REVIEW_TIMEOUT_SECONDS", "180"))
DIRECTORY_PAGE_SIZE = 24
TRAILING_PAUSE_PATTERN = re.compile(r"[，。！？；、：]+$")
SOFT_STOPS = {"，", "、"}
HARD_STOPS = {"。", "！", "？", "；", "："}
BREATHING_STOPS = SOFT_STOPS | HARD_STOPS
CLOSING_MARKS = {"”", "’", "」", "』", "》", "）", "】"}
FULL_WIDTH_INDENT = "　　"
READING_MODES = ("通读", "慢读", "转轮", "领读")
SPEED_SECONDS = {"快": 2.5, "中": 4.0, "慢": 6.0}
EVIDENCE_EXCERPT_LIMIT = 160

TOOL_LABELS = {
    "allusion": "典故候选",
    "reference": "出处与化用",
    "char": "字词释义",
    "rhyme": "韵部",
    "ci_tune": "词谱 / 平仄",
}

EVIDENCE_SOURCE_LABELS = {
    "cnkgraph_allusion": "CNKGraph 典故候选",
    "cnkgraph_reference": "CNKGraph 出处与化用",
}
EVIDENCE_STATUS_LABELS = {
    "hit": "命中候选证据",
    "no_result": "无结果",
    "error": "查询错误",
}
OVERALL_STATUS_LABELS = {
    "hit": "查到候选证据",
    "no_result": "未查到候选证据",
    "partial_error": "候选证据部分查询失败",
    "error": "候选证据查询失败",
}
CANDIDATE_TYPE_LABELS = {
    "allusion": "典故",
    "literary_reference": "文献化用",
    "historical_place": "历史地名",
    "cultural_institution": "礼俗制度",
    "conventional_motif": "惯用母题",
    "uncertain": "待查",
}
EVIDENCE_CONTEXT_LABELS = {
    "prior_source": "前代来源候选",
    "current_poem": "当前作品命中",
    "later_usage": "后代用例",
}
REVIEW_STATUS_LABELS = {
    "reviewed": "已生成审阅短注",
    "insufficient_evidence": "证据不足",
    "ambiguous": "证据有歧义",
    "error": "审阅失败",
}
REVIEW_ROLE_LABELS = {
    "prior_source": "前代来源",
    "current_work_self_hit": "当前作品自命中",
    "later_reuse": "后代沿用",
    "weak_related": "弱相关",
    "irrelevant": "无关或误命中",
    "unknown": "关系不明",
}

THEME_PALETTES = {
    "浅色": {
        "app_bg": "#f5f4f0",
        "sidebar_bg": "#e8ebe7",
        "surface": "#fbfbf8",
        "surface_muted": "#eeefeb",
        "text": "#27302c",
        "text_muted": "#69716c",
        "border": "#c9cfca",
        "border_soft": "#dde1dd",
        "accent": "#85554a",
        "accent_hover": "#72483f",
        "accent_soft": "#eaded9",
        "green": "#526d62",
        "hero_tint": "#f5f4f0",
        "hero_blend": "normal",
    },
    "深色": {
        "app_bg": "#1d2421",
        "sidebar_bg": "#242c28",
        "surface": "#29312d",
        "surface_muted": "#313934",
        "text": "#e7e4dc",
        "text_muted": "#aab1ac",
        "border": "#4b5650",
        "border_soft": "#3a443f",
        "accent": "#bd8b7e",
        "accent_hover": "#c99a8d",
        "accent_soft": "#493a35",
        "green": "#8ca99d",
        "hero_tint": "#354039",
        "hero_blend": "multiply",
    },
}
