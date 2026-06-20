"""Probe CNKGraph labelize endpoints with a small, rate-limited matrix."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data/generated"
PRIMARY_HOST = "https://api.cnkgraph.com"
ALTERNATE_HOST = "https://open.cnkgraph.com"
MIN_DELAY_SECONDS = 0.5
MAX_REQUESTS = 80
MAX_RESPONSE_CHARS = 20_000

POSTMAN_HISTORY_TEXT = (
    "後主諱緯，字仁綱，武成皇帝之長子也。母曰胡皇后，夢於海上坐玉盆，日入裙下，遂有娠。"
    "天保七年五月五日，生帝於幷州邸。帝少美容儀，武成特所愛寵，拜王世子。"
    "及武成入纂大業，大寧二年正月丙戌，立為皇太子。河清四年，武成禪位於帝。"
)

AUTHOR_SEARCHES = (
    ("杜甫", "国破山河在"),
    ("苏轼", "明月几时有"),
    ("周邦彦", "叶上初阳干宿雨"),
    ("李白", "床前明月光"),
)


@dataclass(frozen=True)
class RequestSpec:
    name: str
    category: str
    method: str
    url: str
    json_body: Any = None
    form_body: dict[str, str] | None = None
    text_body: str | None = None
    headers: dict[str, str] | None = None
    expected_author: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--delay", type=float, default=MIN_DELAY_SECONDS)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def load_full_ci_text() -> str:
    """Use one local Zhou Bangyan ci when available, otherwise a stable excerpt."""
    source = PROJECT_ROOT / "data/generated/zhoubangyan_poems.json"
    if source.exists():
        poems = json.loads(source.read_text(encoding="utf-8"))
        for poem in poems:
            if poem.get("tune") in {"瑞龙吟", "夜飞鹊"} and poem.get("full_text"):
                return poem["full_text"]
    return "章台路。还见褪粉梅梢，试花桃树。愔愔坊陌人家，定巢燕子，归来旧处。"


def static_specs() -> list[RequestSpec]:
    """Build the bounded path, host, payload, and text-variation matrix."""
    canonical_body = {"content": POSTMAN_HISTORY_TEXT, "dynasty": "北齐"}
    short_text = "前度刘郎"
    line_text = "前度刘郎今又来"
    ci_text = load_full_ci_text()
    mixed_text = "今天读到‘前度刘郎今又来’，想知道其中是否包含典故。"

    specs = [
        RequestSpec("postman_original", "baseline", "POST", f"{PRIMARY_HOST}/api/tool/labelize", json_body=canonical_body),
        RequestSpec("post_case_full", "path", "POST", f"{PRIMARY_HOST}/Api/Tool/Labelize", json_body=canonical_body),
        RequestSpec("post_plural_tools", "path", "POST", f"{PRIMARY_HOST}/api/tools/labelize", json_body=canonical_body),
        RequestSpec("post_case_action", "path", "POST", f"{PRIMARY_HOST}/api/tool/Labelize", json_body=canonical_body),
        RequestSpec("writing_canonical", "path", "GET", f"{PRIMARY_HOST}/api/writing/10000/labelize"),
        RequestSpec("writing_case", "path", "GET", f"{PRIMARY_HOST}/Api/Writing/10000/Labelize"),
        RequestSpec("writing_labels", "path", "GET", f"{PRIMARY_HOST}/api/writing/10000/labels"),
        RequestSpec("writing_annotations", "path", "GET", f"{PRIMARY_HOST}/api/writing/10000/annotations"),
        RequestSpec("alternate_host_post", "host", "POST", f"{ALTERNATE_HOST}/api/tool/labelize", json_body=canonical_body),
        RequestSpec("alternate_host_writing", "host", "GET", f"{ALTERNATE_HOST}/api/writing/10000/labelize"),
        RequestSpec(
            "form_urlencoded",
            "content_type",
            "POST",
            f"{PRIMARY_HOST}/api/tool/labelize",
            form_body={"content": line_text, "dynasty": "宋"},
        ),
        RequestSpec(
            "text_plain",
            "content_type",
            "POST",
            f"{PRIMARY_HOST}/api/tool/labelize",
            text_body=line_text,
            headers={"Content-Type": "text/plain; charset=utf-8"},
        ),
        RequestSpec("field_text", "field_alias", "POST", f"{PRIMARY_HOST}/api/tool/labelize", json_body={"text": line_text, "dynasty": "宋"}),
        RequestSpec("field_dynasty_name", "field_alias", "POST", f"{PRIMARY_HOST}/api/tool/labelize", json_body={"content": line_text, "dynastyName": "宋"}),
        RequestSpec(
            "field_author",
            "field_alias",
            "POST",
            f"{PRIMARY_HOST}/api/tool/labelize",
            json_body={"content": line_text, "author": "周邦彦", "dynasty": "宋"},
        ),
        RequestSpec("text_short", "text_type", "POST", f"{PRIMARY_HOST}/api/tool/labelize", json_body={"content": short_text, "dynasty": "宋"}),
        RequestSpec("text_line", "text_type", "POST", f"{PRIMARY_HOST}/api/tool/labelize", json_body={"content": line_text, "dynasty": "宋"}),
        RequestSpec("text_full_ci", "text_type", "POST", f"{PRIMARY_HOST}/api/tool/labelize", json_body={"content": ci_text, "dynasty": "宋"}),
        RequestSpec("text_mixed", "text_type", "POST", f"{PRIMARY_HOST}/api/tool/labelize", json_body={"content": mixed_text, "dynasty": "宋"}),
        RequestSpec("options_tool", "method", "OPTIONS", f"{PRIMARY_HOST}/api/tool/labelize"),
        RequestSpec("options_writing", "method", "OPTIONS", f"{PRIMARY_HOST}/api/writing/10000/labelize"),
    ]
    specs.extend(
        RequestSpec(
            name=f"find_{author}",
            category="discovery",
            method="POST",
            url=f"{PRIMARY_HOST}/api/writing/find",
            json_body={"key": key, "exactlyMatch": True},
            expected_author=author,
        )
        for author, key in AUTHOR_SEARCHES
    )
    return specs


def parse_body(response: httpx.Response) -> tuple[Any, str, str]:
    try:
        body = response.json()
        serialized = json.dumps(body, ensure_ascii=False)
        return body, "json", serialized
    except ValueError:
        return response.text, "text", response.text


def body_shape(body: Any) -> dict[str, Any]:
    if isinstance(body, dict):
        return {"type": "object", "keys": list(body)[:30], "key_count": len(body)}
    if isinstance(body, list):
        return {"type": "array", "length": len(body)}
    return {"type": type(body).__name__}


def execute(client: httpx.Client, spec: RequestSpec) -> tuple[dict[str, Any], Any]:
    kwargs: dict[str, Any] = {"headers": spec.headers or {}}
    if spec.json_body is not None:
        kwargs["json"] = spec.json_body
    elif spec.form_body is not None:
        kwargs["data"] = spec.form_body
    elif spec.text_body is not None:
        kwargs["content"] = spec.text_body.encode("utf-8")

    started = time.perf_counter()
    try:
        response = client.request(spec.method, spec.url, **kwargs)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        body, body_format, serialized = parse_body(response)
        record = {
            **asdict(spec),
            "request_url": str(response.request.url),
            "request_headers": dict(response.request.headers),
            "status_code": response.status_code,
            "ok": response.is_success,
            "elapsed_ms": elapsed_ms,
            "response_headers": {
                key: value
                for key, value in response.headers.items()
                if key.lower() in {"allow", "content-type", "location", "server", "www-authenticate"}
            },
            "response_body_format": body_format,
            "response_shape": body_shape(body),
            "response_chars": len(serialized),
            "response_body_truncated": len(serialized) > MAX_RESPONSE_CHARS,
            "response_body": serialized[:MAX_RESPONSE_CHARS] if len(serialized) > MAX_RESPONSE_CHARS else body,
        }
        return record, body
    except httpx.RequestError as exc:
        record = {
            **asdict(spec),
            "request_url": str(exc.request.url),
            "status_code": None,
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        return record, None


def discover_writings(body: Any, expected_author: str) -> list[dict[str, Any]]:
    """Keep at most three search results whose author matches the requested poet."""
    if not isinstance(body, dict) or not isinstance(body.get("Writings"), list):
        return []
    matches = []
    for writing in body["Writings"]:
        if writing.get("Author") == expected_author and writing.get("Id") is not None:
            matches.append(
                {
                    "id": writing["Id"],
                    "author": writing.get("Author"),
                    "author_id": writing.get("AuthorId"),
                    "dynasty": writing.get("Dynasty"),
                    "type": writing.get("Type"),
                    "title": (writing.get("Title") or {}).get("Content"),
                }
            )
        if len(matches) == 3:
            break
    return matches


def first_author_match(body: Any, expected_author: str) -> dict[str, Any] | None:
    """Return one search hit that supplies the author browse route parameters."""
    if not isinstance(body, dict) or not isinstance(body.get("Writings"), list):
        return None
    return next(
        (writing for writing in body["Writings"] if writing.get("Author") == expected_author),
        None,
    )


def main() -> int:
    args = parse_args()
    if args.delay < MIN_DELAY_SECONDS:
        raise SystemExit(f"--delay must be at least {MIN_DELAY_SECONDS} seconds")

    specs = static_specs()
    results: list[dict[str, Any]] = []
    discovered: list[dict[str, Any]] = []

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=False,
        headers={"Accept": "application/json", "User-Agent": "qingshang-cnkgraph-labelize-probe/0.1"},
    ) as client:
        index = 0
        while index < len(specs):
            if len(results) >= MAX_REQUESTS:
                raise RuntimeError(f"request limit reached: {MAX_REQUESTS}")
            spec = specs[index]
            print(f"[{len(results) + 1:02d}] {spec.category} / {spec.name}")
            record, body = execute(client, spec)
            results.append(record)
            print(f"  -> {record.get('status_code')} in {record['elapsed_ms']} ms")

            if spec.category == "discovery" and spec.expected_author:
                match = first_author_match(body, spec.expected_author)
                if match:
                    writing_type = "Ci" if match.get("Type") == "词" else "Poem"
                    dynasty = quote(str(match.get("Dynasty") or ""), safe="")
                    author = quote(spec.expected_author, safe="")
                    specs.append(
                        RequestSpec(
                            f"browse_{spec.expected_author}",
                            "author_browse",
                            "GET",
                            f"{PRIMARY_HOST}/api/writing/{dynasty}/{author}/{match['AuthorId']}/{writing_type}?pageNo=0",
                            expected_author=spec.expected_author,
                        )
                    )

            if spec.category == "author_browse" and spec.expected_author:
                writings = discover_writings(body, spec.expected_author)
                discovered.extend(writings)
                for writing in writings:
                    writing_id = writing["id"]
                    specs.append(
                        RequestSpec(
                            f"detail_{spec.expected_author}_{writing_id}",
                            "writing_detail",
                            "GET",
                            f"{PRIMARY_HOST}/api/writing/{writing_id}",
                            expected_author=spec.expected_author,
                        )
                    )
                    specs.append(
                        RequestSpec(
                            f"labelize_{spec.expected_author}_{writing_id}",
                            "writing_id",
                            "GET",
                            f"{PRIMARY_HOST}/api/writing/{writing_id}/labelize",
                            expected_author=spec.expected_author,
                        )
                    )

            index += 1
            if index < len(specs):
                time.sleep(args.delay)

    timestamp = datetime.now(timezone.utc)
    output_path = args.output_dir / f"cnkgraph_labelize_probe_{timestamp:%Y%m%d_%H%M%S}.json"
    report = {
        "generated_at": timestamp.isoformat(),
        "limits": {
            "minimum_delay_seconds": MIN_DELAY_SECONDS,
            "configured_delay_seconds": args.delay,
            "maximum_requests": MAX_REQUESTS,
            "actual_requests": len(results),
        },
        "summary": {
            "total": len(results),
            "http_2xx": sum(result["ok"] for result in results),
            "http_non_2xx": sum(result.get("status_code") is not None and not result["ok"] for result in results),
            "connection_errors": sum(result.get("status_code") is None for result in results),
            "labelize_2xx": sum(
                result["ok"]
                for result in results
                if result["category"] in {"baseline", "path", "host", "content_type", "field_alias", "text_type", "writing_id"}
            ),
        },
        "discovered_writings": discovered,
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {output_path}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
