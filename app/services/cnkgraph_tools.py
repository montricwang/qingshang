"""把 CNKGraph 原始响应适配为清商的窄证据模型。

这个文件是 CNKGraph 外部 API 和清商内部 EvidenceItem / AllusionCandidate 之间的翻译层。
每个 build_* 函数做三件事：① 发送 CNKGraph 查询 ② 拆开嵌套的原始 JSON
③ 只保留清商需要的窄字段，raw 存完整原始数据备用。
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.cnkgraph import AllusionCandidate, EvidenceItem
from app.services.cnkgraph_client import CNKGraphClient


# ---------------------------------------------------------------------------
# 通用 JSON 拆嵌套工具
# ---------------------------------------------------------------------------

def _as_items(raw: Any, key: str | None = None) -> list[dict[str, Any]]:
    """把 CNKGraph 响应中的杂格式统一转为 dict 列表。

    CNKGraph 接口的返回格式不统一：
    - 有的直接返回 dict，有的返回 list
    - 有的把列表包在一个 key 里（如 "Sentences"、"ModernDictionary"）
    这个函数处理这些情况，只保留 dict 条目。
    """
    if key and isinstance(raw, dict):
        raw = raw.get(key)
    if isinstance(raw, dict):
        return [raw] if raw else []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _decode_nested_json(raw: Any) -> Any:
    """韵典接口有时把对象再编码成 JSON 字符串，尝试递归解开一层。"""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


# ---------------------------------------------------------------------------
# 深层 JSON 安全取值
# ---------------------------------------------------------------------------

def _deep_get(data: Any, *path: str | int) -> Any:
    """沿着路径在嵌套 dict/list 中安全取值，中间任何一步不存在就返回 None。

    例如 _deep_get(raw, "ModernDictionary", 0, "Advance")
    等价于 raw["ModernDictionary"][0]["Advance"]，但不会因 KeyError 或 IndexError 崩溃。
    """
    current = data
    for key in path:
        if isinstance(current, dict) and isinstance(key, str):
            current = current.get(key)
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return None
    return current


# ============================================================================
# 典故候选查询
# ============================================================================

async def build_allusion_candidates(
    key: str,
    client: CNKGraphClient | None = None,
) -> list[AllusionCandidate]:
    """按关键词查询 CNKGraph 典故，保留"候选"语义。"""
    cnkgraph = client or CNKGraphClient()
    raw = await cnkgraph.find_allusions(key)

    candidates = []
    for item in _as_items(raw):
        explains = _as_items(item.get("Explains"))
        quotes = _as_items(item.get("Quotes"))
        keys = item.get("Keys") if isinstance(item.get("Keys"), list) else []

        explanation = explains[0] if explains else {}
        quote_item = quotes[0] if quotes else {}

        candidates.append(AllusionCandidate(
            keyword=key,
            title=explanation.get("Key") or (keys[0] if keys else None),
            explanation=explanation.get("Explain"),
            source_text=quote_item.get("Content"),
            source_ref=quote_item.get("Book"),
            raw=item,
        ))
    return candidates


# ============================================================================
# 出处与化用查询
# ============================================================================

async def build_reference_evidences(
    content: str,
    client: CNKGraphClient | None = None,
) -> list[EvidenceItem]:
    """把 CNKGraph 出处分析结果展开为逐条证据。"""
    cnkgraph = client or CNKGraphClient()
    raw = await cnkgraph.analyze_reference(content)

    evidences = []
    for sentence in _as_items(raw, "Sentences"):
        for reference in _as_items(sentence.get("References")):
            # 拼出朝代/作者/标题的格式来源字符串
            source_parts = [
                str(reference.get("Dynasty")),
                str(reference.get("Author")),
                f"《{reference['Title']}》" if reference.get("Title") else None,
            ]
            source_ref = " ".join(p for p in source_parts if p) or None

            evidences.append(EvidenceItem(
                tool_name="reference",
                anchor_text=sentence.get("Clause"),
                title=reference.get("Title"),
                claim="检测到出处或化用候选",
                evidence_text=reference.get("Clause"),
                source_ref=source_ref,
                raw=reference,
            ))
    return evidences


# ============================================================================
# 字词释义查询
# ============================================================================

def _extract_char_claim(raw: dict[str, Any]) -> str | None:
    """从 CNKGraph 字典响应的深层嵌套中提取第一条释义。

    原始 JSON 结构：
    raw → ModernDictionary → [0] → Advance → Usages → [0] → UsageExplains → [0] → Explains → [0] → Explain
    不是每个中间层都存在（CNKGraph 可能返回空或字段缺失），所以每一步都要安全取值。
    """
    advance = _deep_get(raw, "ModernDictionary", 0, "Advance")
    if not isinstance(advance, dict):
        return None

    usages = _as_items(advance.get("Usages"))
    if not usages:
        return None

    usage_explains = _as_items(usages[0].get("UsageExplains"))
    if not usage_explains:
        return None

    explains = _as_items(usage_explains[0].get("Explains"))
    if not explains:
        return None

    return explains[0].get("Explain")


async def build_char_evidence(
    char: str,
    client: CNKGraphClient | None = None,
) -> list[EvidenceItem]:
    """查询一个字的简明字典证据。"""
    cnkgraph = client or CNKGraphClient()
    raw = await cnkgraph.get_char(char)

    if not raw:
        return []

    claim = _extract_char_claim(raw)
    return [EvidenceItem(
        tool_name="char",
        anchor_text=char,
        title=char,
        claim=claim,
        source_ref="CNKGraph 字典",
        match_status="exact",
        raw=raw,
    )]


# ============================================================================
# 词谱查询
# ============================================================================

async def build_ci_tune_evidence(
    tune_name: str,
    client: CNKGraphClient | None = None,
) -> list[EvidenceItem]:
    """按词牌关键词返回词谱候选。"""
    cnkgraph = client or CNKGraphClient()
    raw = await cnkgraph.find_ci_tunes(tune_name)

    return [
        EvidenceItem(
            tool_name="ci_tune",
            anchor_text=tune_name,
            title=item.get("Name"),
            claim=item.get("Desc"),
            source_ref=(
                f"cnkgraph:ci-tune:{item['Id']}" if item.get("Id") else None
            ),
            match_status="exact" if item.get("Name") == tune_name else "candidate",
            raw=item,
        )
        for item in _as_items(raw)
    ]


# ============================================================================
# 韵部查询
# ============================================================================

async def build_rhyme_evidence(
    chars: list[str],
    client: CNKGraphClient | None = None,
    book: str = "平水韵",
) -> list[EvidenceItem]:
    """逐字查询韵书信息，一次最多 30 个字。"""
    cnkgraph = client or CNKGraphClient()
    evidences = []

    for char in chars:
        raw = _decode_nested_json(await cnkgraph.find_rhyme(char, book))
        if not isinstance(raw, dict) or not raw:
            continue

        spellings = raw.get("Spellings")
        evidences.append(EvidenceItem(
            tool_name="rhyme",
            anchor_text=char,
            title=f"{char} · {book}",
            claim=raw.get("Comment"),
            evidence_text="、".join(spellings) if isinstance(spellings, list) else None,
            source_ref=book,
            match_status="exact",
            raw=raw,
        ))
    return evidences
