"""把 CNKGraph 原始响应适配为清商的窄证据模型。"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.cnkgraph import AllusionCandidate, EvidenceItem
from app.services.cnkgraph_client import CNKGraphClient


def _as_items(raw: Any, key: str | None = None) -> list[dict[str, Any]]:
    if key and isinstance(raw, dict):
        raw = raw.get(key)
    if isinstance(raw, dict):
        return [raw] if raw else []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _decode_nested_json(raw: Any) -> Any:
    """韵典当前可能把对象再次编码成 JSON 字符串。"""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


async def build_allusion_candidates(
    key: str,
    client: CNKGraphClient | None = None,
) -> list[AllusionCandidate]:
    """查询典故，并保留“候选”语义。"""
    raw = await (client or CNKGraphClient()).find_allusions(key)
    candidates = []
    for item in _as_items(raw):
        explains = _as_items(item.get("Explains"))
        quotes = _as_items(item.get("Quotes"))
        keys = item.get("Keys") if isinstance(item.get("Keys"), list) else []
        explanation = explains[0] if explains else {}
        quote_item = quotes[0] if quotes else {}
        candidates.append(
            AllusionCandidate(
                keyword=key,
                title=explanation.get("Key") or (keys[0] if keys else None),
                explanation=explanation.get("Explain"),
                source_text=quote_item.get("Content"),
                source_ref=quote_item.get("Book"),
                raw=item,
            )
        )
    return candidates


async def build_reference_evidences(
    content: str,
    client: CNKGraphClient | None = None,
) -> list[EvidenceItem]:
    """把相似句和化用结果展开为逐条证据。"""
    raw = await (client or CNKGraphClient()).analyze_reference(content)
    evidences = []
    for sentence in _as_items(raw, "Sentences"):
        for reference in _as_items(sentence.get("References")):
            source_ref = " ".join(
                str(value)
                for value in (
                    reference.get("Dynasty"),
                    reference.get("Author"),
                    f"《{reference['Title']}》" if reference.get("Title") else None,
                )
                if value
            )
            evidences.append(
                EvidenceItem(
                    tool_name="reference",
                    anchor_text=sentence.get("Clause"),
                    title=reference.get("Title"),
                    claim="检测到出处或化用候选",
                    evidence_text=reference.get("Clause"),
                    source_ref=source_ref or None,
                    raw=reference,
                )
            )
    return evidences


async def build_char_evidence(
    char: str,
    client: CNKGraphClient | None = None,
) -> list[EvidenceItem]:
    """提取字典响应中的第一条简明释义。"""
    raw = await (client or CNKGraphClient()).get_char(char)
    claim = None
    evidence_text = None
    dictionaries = _as_items(raw, "ModernDictionary")
    if dictionaries:
        advance = dictionaries[0].get("Advance") or {}
        usages = _as_items(advance.get("Usages"))
        if usages:
            usage_explains = _as_items(usages[0].get("UsageExplains"))
            if usage_explains:
                explains = _as_items(usage_explains[0].get("Explains"))
                if explains:
                    claim = explains[0].get("Explain")
                evidence_text = usage_explains[0].get("WordClass")

    return [
        EvidenceItem(
            tool_name="char",
            anchor_text=char,
            title=char,
            claim=claim,
            evidence_text=evidence_text,
            source_ref="CNKGraph 字典",
            match_status="exact",
            raw=raw,
        )
    ] if raw else []


async def build_ci_tune_evidence(
    tune_name: str,
    client: CNKGraphClient | None = None,
) -> list[EvidenceItem]:
    """把词牌搜索结果转换为词谱候选。"""
    raw = await (client or CNKGraphClient()).find_ci_tunes(tune_name)
    return [
        EvidenceItem(
            tool_name="ci_tune",
            anchor_text=tune_name,
            title=item.get("Name"),
            claim=item.get("Desc"),
            source_ref=(f"cnkgraph:ci-tune:{item['Id']}" if item.get("Id") else None),
            match_status="exact" if item.get("Name") == tune_name else "candidate",
            raw=item,
        )
        for item in _as_items(raw)
    ]


async def build_rhyme_evidence(
    chars: list[str],
    client: CNKGraphClient | None = None,
    book: str = "平水韵",
) -> list[EvidenceItem]:
    """逐字查询韵书信息，并返回可独立降级的证据列表。"""
    cnkgraph = client or CNKGraphClient()
    evidences = []
    for char in chars:
        raw = _decode_nested_json(await cnkgraph.find_rhyme(char, book))
        if not isinstance(raw, dict) or not raw:
            continue
        spellings = raw.get("Spellings")
        evidences.append(
            EvidenceItem(
                tool_name="rhyme",
                anchor_text=char,
                title=f"{char} · {book}",
                claim=raw.get("Comment"),
                evidence_text=(
                    "、".join(spellings) if isinstance(spellings, list) else None
                ),
                source_ref=book,
                match_status="exact",
                raw=raw,
            )
        )
    return evidences
