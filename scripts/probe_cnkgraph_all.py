"""Run every request defined by the local CNKGraph Postman collections."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COLLECTION_DIR = PROJECT_ROOT / "docs/cnkgraph/postman"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data/generated/cnkgraph_all_probe.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data/generated/cnkgraph_api_test_report.md"
MAX_RESPONSE_CHARS = 20_000

# Postman environment was not included in the repository. Collection-level
# variables override these fallbacks when the collection provides an example.
VARIABLES = {
    "host": "api.cnkgraph.com",
    "regionId": "CN3301",
    "regionName": "杭州",
    "dynasty": "宋",
    "authorName": "杜甫",
    "authorId": "17270",
    "writingType": "Poem",
    "pageNo": "0",
    "writingId": "10000",
    "coupletWords": "天地,古今",
    "key": "31190",
}

COLLECTION_VARIABLE_OVERRIDES = {
    "人物": {"dynasty": "唐"},
    "年历": {"dynasty": "宋"},
    "诗文库": {"dynasty": "唐", "writingType": "Poem"},
}

COLLECTION_ASSESSMENTS = {
    "词汇、典故": ("近期", "直接支持词句释义、典故候选与阅读注释，是首版赏析的核心外部数据。"),
    "词谱": ("近期", "可校验词牌、检索同调作品并匹配平仄片段，直接补足结构化词作的格律维度。"),
    "地理": ("中期", "可为地名、景观和作品关联提供背景，但需先解决文本实体与行政区划 ID 的消歧。"),
    "工具": ("近期", "出处与化用分析可直接支持阅读辅助；繁简转换与短信息查询属于配套能力，自动笺注本轮不可用。"),
    "古籍库": ("中期", "可提供原典、出处和上下文证据，适合在基本注释稳定后构建可追溯引用。"),
    "类书": ("中期", "适合扩展名物、地域和典故背景，但条目层级复杂，首版不宜直接耦合。"),
    "年历": ("中期", "可把年号、干支和具体日期标准化，用于作者生平与创作背景时间线。"),
    "曲谱": ("远期", "清商当前聚焦宋词，曲谱主要用于跨文体比较和后续元曲扩展。"),
    "人物": ("中期", "可补作者、相关人物、籍贯和谥号信息，适合人物关系与生平背景模块。"),
    "诗文库": ("近期", "作品详情、平仄和出处能与本地 poems 数据直接对照，是集成优先级最高的一组；自动笺注本轮不可用。"),
    "韵典": ("近期", "可解释韵目、韵字和单字归韵，能支撑押韵展示与格律分析。"),
    "字典": ("近期", "单字释义是逐字阅读的基础能力，接口简单，适合作为按需查询工具。"),
}

PHASE_OVERRIDES = {
    ("词谱", "查询历代使用指定词谱的作品"): "中期",
    ("地理", "查询某一景观的详细信息"): "中期",
    ("地理", "查询某一行政区划下有哪些景观"): "中期",
    ("地理", "查询与某一行政区划相关的链接"): "远期",
    ("地理", "查询某一景观的相关链接"): "远期",
    ("工具", "简体转繁体"): "中期",
    ("工具", "繁体转简体"): "中期",
    ("工具", "短信息查询"): "中期",
    ("工具", "自动笺注"): "暂缓",
    ("古籍库", "获取古籍库总览"): "远期",
    ("古籍库", "获取某一分类下详细书目"): "远期",
    ("类书", "获取类书列表"): "远期",
    ("类书", "获取某一本类书的目录结构"): "远期",
    ("年历", "总览"): "远期",
    ("年历", "按朝代浏览"): "远期",
    ("年历", "查历代某一干支年"): "远期",
    ("年历", "查询与某一时间相关的链接"): "远期",
    ("人物", "人物总览"): "远期",
    ("人物", "按朝代浏览"): "远期",
    ("诗文库", "总览"): "远期",
    ("诗文库", "按朝代浏览"): "远期",
    ("诗文库", "按作家浏览"): "中期",
    ("诗文库", "获取含特定对仗词汇组的律句"): "中期",
    ("诗文库", "组合搜索"): "中期",
    ("诗文库", "获取作品库中有相似句子的作品"): "中期",
    ("诗文库", "获取作品库中与指定作品所押韵脚相同的作品"): "中期",
    ("诗文库", "查询符合某一平仄句式的律句"): "中期",
    ("诗文库", "自动笺注"): "暂缓",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection-dir", type=Path, default=COLLECTION_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--delay", type=float, default=0.1)
    return parser.parse_args()


def iter_requests(items: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Yield request items, including requests nested in Postman folders."""
    for item in items:
        if "request" in item:
            yield item
        if "item" in item:
            yield from iter_requests(item["item"])


def replace_variables(value: str, variables: dict[str, str]) -> str:
    """Replace ``{{name}}`` placeholders with the representative test values."""
    return re.sub(
        r"{{([^{}]+)}}",
        lambda match: variables.get(match.group(1), match.group(0)),
        value,
    )


def load_probes(collection_dir: Path) -> list[dict[str, Any]]:
    """Convert all Postman request items into a small HTTP-client-neutral form."""
    probes = []
    for path in sorted(collection_dir.glob("*.postman_collection.json")):
        collection = json.loads(path.read_text(encoding="utf-8-sig"))
        collection_name = collection["info"]["name"]
        collection_variables = {
            item["key"]: str(item.get("value", ""))
            for item in collection.get("variable", [])
        }
        variables = {
            **VARIABLES,
            **COLLECTION_VARIABLE_OVERRIDES.get(collection_name, {}),
            **collection_variables,
        }
        for item in iter_requests(collection.get("item", [])):
            request = item["request"]
            raw_url = request["url"]["raw"]
            headers = {
                header["key"]: replace_variables(header["value"], variables)
                for header in request.get("header", [])
                if not header.get("disabled")
            }
            body = request.get("body", {})
            raw_body = body.get("raw") if body.get("mode") == "raw" else None
            probes.append(
                {
                    "collection": collection_name,
                    "name": item["name"],
                    "method": request["method"].upper(),
                    "source_file": str(path.relative_to(PROJECT_ROOT)),
                    "source_url": raw_url,
                    "url": replace_variables(raw_url, variables),
                    "headers": headers,
                    "json": json.loads(raw_body) if raw_body else None,
                }
            )
    return probes


def describe_body(body: Any) -> dict[str, Any]:
    """Record response shape without assuming a stable CNKGraph schema."""
    if isinstance(body, dict):
        return {"type": "object", "keys": list(body)[:30], "key_count": len(body)}
    if isinstance(body, list):
        return {"type": "array", "length": len(body)}
    return {"type": type(body).__name__}


def run_probe(client: httpx.Client, probe: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    kwargs: dict[str, Any] = {"headers": probe["headers"]}
    if probe["json"] is not None:
        kwargs["json"] = probe["json"]

    try:
        response = client.request(probe["method"], probe["url"], **kwargs)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        try:
            body = response.json()
            body_format = "json"
            serialized = json.dumps(body, ensure_ascii=False)
        except ValueError:
            body = response.text
            body_format = "text"
            serialized = body

        truncated = len(serialized) > MAX_RESPONSE_CHARS
        return {
            **probe,
            "request_url": str(response.request.url),
            "status_code": response.status_code,
            "ok": response.is_success,
            "elapsed_ms": elapsed_ms,
            "response_content_type": response.headers.get("content-type"),
            "response_body_format": body_format,
            "response_shape": describe_body(body),
            "response_chars": len(serialized),
            "response_body_truncated": truncated,
            "response_body": serialized[:MAX_RESPONSE_CHARS] if truncated else body,
        }
    except httpx.RequestError as exc:
        return {
            **probe,
            "request_url": str(exc.request.url),
            "status_code": None,
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def endpoint_phase(result: dict[str, Any]) -> str:
    return PHASE_OVERRIDES.get(
        (result["collection"], result["name"]),
        COLLECTION_ASSESSMENTS[result["collection"]][0],
    )


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def build_report(report: dict[str, Any]) -> str:
    """Create the human-readable evidence and project-fit assessment."""
    results = report["results"]
    by_collection: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_collection[result["collection"]].append(result)

    lines = [
        "# CNKGraph 全接口实测与清商适用性报告",
        "",
        f"> 测试时间：`{report['generated_at']}`  ",
        f"> 数据来源：`docs/cnkgraph/postman/` 内 {report['summary']['collections']} 份 Postman 集合  ",
        f"> 测试范围：{report['summary']['total']} 个集合请求，逐项真实访问 `https://api.cnkgraph.com`",
        "",
        "## 1. 结论摘要",
        "",
        f"- HTTP 成功：**{report['summary']['successful']}/{report['summary']['total']}**；失败：**{report['summary']['failed']}**。",
        "- 本报告证明的是测试时点的可访问性和响应形态，不等同于 SLA、长期稳定性、授权许可或字段契约保证。",
        "- 近期最值得接入：诗文库的作品详情/平仄/出处、词汇典故、词谱、韵典、字典，以及工具中的出处与化用分析。",
        "- 中期适合补充：人物、地理、年历、古籍与类书，用于可追溯的作者生平、创作时空和原典上下文。",
        "- 远期再考虑：全库总览、跨库链接、曲谱和大范围目录遍历；它们价值存在，但不应拖慢 poems 阅读主链路。",
        "",
        "## 2. 测试方法与边界",
        "",
        "- 请求定义直接读取仓库中的 Postman collection，不手工改写接口路径或请求体。",
        "- 仓库没有 Postman environment；优先使用 collection 自带变量，其余占位符使用脚本中的明确回退值。诗文样例沿用 collection 的杜甫（作者 `17270`、作品 `10000`）。",
        "- 所有请求按顺序执行，默认超时 90 秒、间隔 0.1 秒；没有并发压测，也没有故意发送破坏性或异常输入。",
        "- 原始结果保存在 `data/generated/cnkgraph_all_probe.json`；超过 20,000 字符的响应只保留前段样本，但记录完整响应字符数和结构摘要。",
        "- 只要 HTTP 为 2xx 即计为本轮成功；正式集成仍需为目标字段增加契约测试和空结果检查。",
        "",
        "## 3. 分组结果与阶段建议",
        "",
        "| 接口组 | 通过 | 建议阶段 | 清商中的用途与判断 |",
        "|---|---:|---|---|",
    ]
    for collection, collection_results in by_collection.items():
        phase, reason = COLLECTION_ASSESSMENTS[collection]
        passed = sum(item["ok"] for item in collection_results)
        lines.append(
            f"| {collection} | {passed}/{len(collection_results)} | {phase} | {reason} |"
        )

    lines.extend(
        [
            "",
            "## 4. 逐接口实测结果",
            "",
            "| 接口组 | 请求 | Method | Path | 状态 | 耗时(ms) | 响应形态 | 建议阶段 |",
            "|---|---|---|---|---:|---:|---|---|",
        ]
    )
    for result in results:
        shape = result.get("response_shape", {}).get("type", "error")
        if shape == "array":
            shape += f"[{result['response_shape']['length']}]"
        elif shape == "object":
            shape += f"({result['response_shape']['key_count']} keys)"
        path = re.sub(r"^https://api\.cnkgraph\.com", "", result["request_url"])
        lines.append(
            "| "
            + " | ".join(
                markdown_cell(value)
                for value in (
                    result["collection"],
                    result["name"],
                    result["method"],
                    path,
                    result.get("status_code", "连接失败"),
                    result["elapsed_ms"],
                    shape,
                    endpoint_phase(result),
                )
            )
            + " |"
        )

    failures = [result for result in results if not result["ok"]]
    lines.extend(["", "## 5. 失败与异常观察", ""])
    if failures:
        for result in failures:
            detail = result.get("error") or result.get("response_body")
            lines.append(
                f"- `{result['method']} {result['request_url']}`："
                f"状态 `{result.get('status_code')}`；`{markdown_cell(str(detail)[:300])}`"
            )
    else:
        lines.append("- 本轮没有 HTTP 失败；仍需通过重复运行、异常参数和限流测试评估稳定性。")

    lines.extend(
        [
            "",
            "## 6. 面向清商草案的落地论证",
            "",
            "### 近期：增强单首词阅读闭环",
            "",
            "近期目标应只围绕本地 `poems -> sections -> lines` 数据增加按需辅助信息。诗文详情可用于外部对照，平仄、词谱和韵典可形成可解释的格律层；词汇、典故、字典和出处分析可形成逐句阅读层。它们均能以 `poem_id` 或句子为入口，不要求先改变数据库结构。两个自动笺注接口本轮均返回 404，不应进入近期依赖清单。",
            "",
            "建议先做独立 CNKGraph 客户端和 Tool Layer，不把第三方完整响应直接作为清商 API 契约。首批只保留稳定内部字段，例如候选词、释义、出处、置信来源、韵目和平仄字符串；设置超时、缓存和失败降级，确保 CNKGraph 不可用时本地词作仍能阅读。",
            "",
            "### 中期：构建可追溯的知识背景",
            "",
            "人物、地理、年历、古籍和类书适合用于作者页、创作时间线、地点卡片和出处证据链。它们的共同难点不是请求接口，而是实体消歧：同名人物、古今地名、模糊年号、不同版本书目都不能仅凭字符串自动绑定。中期应先保存外部实体 ID、来源和人工确认状态，再考虑关系图或批量回填。",
            "",
            "诗文库的相似句、同韵、组合搜索和按作者浏览也属于中期：它们可支持延伸阅读与横向比较，但需要排序、去重和解释推荐原因，不能只把搜索结果原样展示。",
            "",
            "### 远期：跨文体检索与知识图谱",
            "",
            "曲谱、全库总览、目录树和跨库 links 更适合远期的跨文体研究与知识图谱。此类接口返回规模大、层级深，并可能随服务端数据更新而变化。远期若使用，应采用离线同步或受控缓存，而不是在用户请求中遍历远端全库。",
            "",
            "## 7. 风险与尚未证明的事项",
            "",
            "- Postman 文件没有声明认证、配额、限流、版本号、SLA 和授权条款；公开可访问不代表可在产品中无限制使用或再分发。",
            "- 本轮是单次顺序冒烟测试，未测并发、峰值延迟、重复运行稳定性、错误码语义和服务端变更频率。",
            "- 接口响应没有被官方 schema 约束；字段缺失、`null`、繁简转换和同名实体仍需逐接口契约测试。",
            "- 部分搜索样例返回的是候选集合，不能视作已经完成文本实体识别或学术判断。",
            "- `POST /api/tool/labelize` 与 `GET /api/writing/{writingId}/labelize` 按 Postman 原始定义测试均返回 404，暂不能用于产品设计。",
            "- 不建议把 CNKGraph ID 直接写入现有 poem/section/line 核心表；当前数据库结构不应为本轮测试修改。",
            "",
            "## 8. 下一步建议",
            "",
            "1. 先确认 CNKGraph 的使用许可、调用频率和可接受的缓存策略。",
            "2. 为近期接口建立一个只读客户端，优先接入作品平仄、词谱、韵典、字典、词汇典故和出处分析。",
            "3. 定义清商自己的窄响应模型，并用保存的样本增加契约测试；第三方字段变化不能直接穿透到 `/api/poems`。",
            "4. 增加缓存、超时、有限重试和熔断降级；外部失败时返回本地 poems 数据，而不是让整页失败。",
            "5. 中期设计外部实体映射表与人工确认流程，再接人物、地理、年历、古籍和类书。",
            "6. 在不同日期重复运行本脚本并比较响应结构，确认稳定性后再做生产集成。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    probes = load_probes(args.collection_dir)
    results = []

    with httpx.Client(
        timeout=args.timeout,
        headers={"Accept": "application/json", "User-Agent": "qingshang-cnkgraph-probe/0.2"},
        follow_redirects=True,
    ) as client:
        for index, probe in enumerate(probes, start=1):
            print(f"[{index:02d}/{len(probes)}] {probe['collection']} / {probe['name']}")
            result = run_probe(client, probe)
            results.append(result)
            print(f"  -> {result.get('status_code')} in {result['elapsed_ms']} ms")
            if index < len(probes):
                time.sleep(args.delay)

    successful = sum(result["ok"] for result in results)
    phase_counts = Counter(endpoint_phase(result) for result in results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(args.collection_dir.relative_to(PROJECT_ROOT)),
        "variables": VARIABLES,
        "summary": {
            "collections": len({result["collection"] for result in results}),
            "total": len(results),
            "successful": successful,
            "failed": len(results) - successful,
            "phase_counts": dict(phase_counts),
        },
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(report), encoding="utf-8")

    print(f"Saved raw results to: {args.output}")
    print(f"Saved Markdown report to: {args.report}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if successful == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
