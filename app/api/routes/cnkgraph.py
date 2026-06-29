"""提供 CNKGraph 直接工具接口和单首词阅读辅助聚合接口。"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.poem import get_poem_by_poem_id
from app.db.session import get_db
from app.models.poem import PoemModel
from app.schemas.cnkgraph import (
    AllusionCandidate,
    EvidenceItem,
    ProsodyAid,
    ReadingAidRequest,
    ReadingAidResponse,
    ReferenceRequest,
    RhymeRequest,
)
from app.services.cnkgraph_client import CNKGraphClientError
from app.services.cnkgraph_tools import (
    build_allusion_candidates,
    build_char_evidence,
    build_ci_tune_evidence,
    build_reference_evidences,
    build_rhyme_evidence,
)

router = APIRouter(tags=["cnkgraph"])
T = TypeVar("T")


def _upstream_http_error(exc: CNKGraphClientError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


def _unique_lookup_chars(text: str, limit: int = 30) -> list[str]:
    """保留不重复的文字字符，限制一次聚合请求的外部调用数量。"""
    return list(dict.fromkeys(char for char in text if char.isalpha()))[:limit]


async def _collect_or_error(
    tool_name: str,
    operation: Awaitable[T],
    errors: list[str],
    fallback: T,
) -> T:
    """只降级当前外部工具，不影响同一阅读请求中的其他结果。"""
    try:
        return await operation
    except CNKGraphClientError as exc:
        errors.append(f"{tool_name}: {exc}")
        return fallback


def _find_line_by_no(
    poem: PoemModel,
    line_no: int,
    poem_id: str,
) -> PoemModel | None:
    """在词作 sections 中按 global_line_no 定位词句，找不到时返回 None。"""
    for section in poem.sections:
        for line in section.lines:
            if line.global_line_no == line_no:
                return line
    return None


async def _query_reading_tools(
    poem: PoemModel,
    selected_text: str,
    included: set[str],
    errors: list[str],
) -> tuple[list[EvidenceItem], list[AllusionCandidate], list[EvidenceItem]]:
    """按 include 逐一查询外部工具，返回 (evidences, allusions, rhyme_info)。"""
    evidences: list[EvidenceItem] = []
    allusions: list[AllusionCandidate] = []
    rhyme_info: list[EvidenceItem] = []

    if "allusion" in included:
        allusions = await _collect_or_error(
            "allusion",
            build_allusion_candidates(selected_text),
            errors,
            [],
        )
    if "reference" in included:
        evidences.extend(
            await _collect_or_error(
                "reference",
                build_reference_evidences(selected_text),
                errors,
                [],
            )
        )
    if "char" in included:
        for char in _unique_lookup_chars(selected_text):
            evidences.extend(
                await _collect_or_error(
                    f"char[{char}]",
                    build_char_evidence(char),
                    errors,
                    [],
                )
            )
    if "ci_tune" in included:
        evidences.extend(
            await _collect_or_error(
                "ci_tune",
                build_ci_tune_evidence(poem.tune_name),
                errors,
                [],
            )
        )
    if "rhyme" in included:
        rhyme_info = await _collect_or_error(
            "rhyme",
            build_rhyme_evidence(_unique_lookup_chars(selected_text)),
            errors,
            [],
        )

    return evidences, allusions, rhyme_info


# ---------------------------------------------------------------------------
# 直接工具接口：每个接口对一个 CNKGraph 查询能力
# ---------------------------------------------------------------------------

@router.get("/api/cnkgraph/char/{char}", response_model=list[EvidenceItem])
async def read_char_evidence(
    char: str = Path(..., min_length=1, max_length=1),
) -> list[EvidenceItem]:
    """查询一个字的简明字典证据。"""
    try:
        return await build_char_evidence(char)
    except CNKGraphClientError as exc:
        raise _upstream_http_error(exc) from exc


@router.get("/api/cnkgraph/allusions", response_model=list[AllusionCandidate])
async def read_allusion_candidates(
    key: str = Query(..., min_length=1),
) -> list[AllusionCandidate]:
    """按关键词返回典故候选，不作确定性语境判断。"""
    try:
        return await build_allusion_candidates(key)
    except CNKGraphClientError as exc:
        raise _upstream_http_error(exc) from exc


@router.post("/api/cnkgraph/reference", response_model=list[EvidenceItem])
async def read_reference_evidences(request: ReferenceRequest) -> list[EvidenceItem]:
    """返回文本中可能的出处与化用证据。"""
    try:
        return await build_reference_evidences(request.content)
    except CNKGraphClientError as exc:
        raise _upstream_http_error(exc) from exc


@router.get("/api/cnkgraph/ci-tunes", response_model=list[EvidenceItem])
async def read_ci_tune_evidences(
    key: str = Query(..., min_length=1),
) -> list[EvidenceItem]:
    """按词牌关键词返回词谱候选。"""
    try:
        return await build_ci_tune_evidence(key)
    except CNKGraphClientError as exc:
        raise _upstream_http_error(exc) from exc


@router.post("/api/cnkgraph/rhyme", response_model=list[EvidenceItem])
async def read_rhyme_evidences(request: RhymeRequest) -> list[EvidenceItem]:
    """按韵书查询一个或多个字的韵典信息。"""
    chars = list(dict.fromkeys(request.chars))
    try:
        return await build_rhyme_evidence(chars, book=request.book)
    except CNKGraphClientError as exc:
        raise _upstream_http_error(exc) from exc


# ---------------------------------------------------------------------------
# 阅读辅助聚合接口：一次请求聚合多工具结果
# ---------------------------------------------------------------------------

@router.post(
    "/api/poems/{poem_id}/reading-aids",
    response_model=ReadingAidResponse,
)
async def build_poem_reading_aids(
    poem_id: str,
    request: ReadingAidRequest,
    db: AsyncSession = Depends(get_db),
) -> ReadingAidResponse:
    """读取本地词作，并按需聚合可降级的外部阅读证据。"""
    poem = await get_poem_by_poem_id(db=db, poem_id=poem_id)
    if poem is None:
        raise HTTPException(status_code=404, detail=f"找不到词作：{poem_id}")

    selected_line = None
    if request.line_no is not None:
        selected_line = _find_line_by_no(poem, request.line_no, poem_id)
        if selected_line is None:
            raise HTTPException(
                status_code=400,
                detail=f"词作 {poem_id} 中不存在第 {request.line_no} 句",
            )

    selected_text = (
        request.selected_text.strip()
        if request.selected_text is not None
        else (selected_line.text if selected_line is not None else None)
    )
    if not selected_text:
        raise HTTPException(status_code=400, detail="selected_text 和 line_no 至少提供一个")

    errors: list[str] = []
    evidences, allusions, rhyme_info = await _query_reading_tools(
        poem, selected_text, set(request.include), errors,
    )

    prosody = None
    if "ci_tune" in request.include or "rhyme" in request.include:
        prosody = ProsodyAid(
            tune_name=poem.tune_name,
            rhyme_info=rhyme_info,
        )

    return ReadingAidResponse(
        poem_id=poem_id,
        selected_text=selected_text,
        line_no=request.line_no,
        evidences=evidences,
        allusions=allusions,
        prosody=prosody,
        errors=errors,
    )
