"""Probe CNKGraph glossary and allusion endpoints from the Postman collection."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://api.cnkgraph.com"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data/generated/cnkgraph_glossary_probe.json"

PROBES: tuple[dict[str, Any], ...] = (
    {
        "name": "glossary_by_id",
        "method": "GET",
        "path": "/api/glossary/词典/10",
    },
    {
        "name": "allusion_by_id",
        "method": "GET",
        "path": "/api/glossary/典故/1000",
    },
    {
        "name": "buddhist_glossary_by_id",
        "method": "GET",
        "path": "/api/glossary/佛典/100",
    },
    {
        "name": "glossary_batch_by_ids",
        "method": "POST",
        "path": "/api/glossary/词典",
        "json": [10, 15, 30, 42],
    },
    {
        "name": "allusion_find_by_keyword",
        "method": "POST",
        "path": "/api/glossary/典故/find",
        "json": {"key": "桃花", "charIndex": "end"},
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def parse_response_body(response: httpx.Response) -> tuple[Any, str]:
    try:
        return response.json(), "json"
    except ValueError:
        return response.text, "text"


def run_probe(client: httpx.Client, probe: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    request_kwargs = {"json": probe["json"]} if "json" in probe else {}

    try:
        response = client.request(
            method=probe["method"],
            url=probe["path"],
            **request_kwargs,
        )
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        body, body_format = parse_response_body(response)

        return {
            **probe,
            "request_url": str(response.request.url),
            "status_code": response.status_code,
            "ok": response.is_success,
            "elapsed_ms": elapsed_ms,
            "response_content_type": response.headers.get("content-type"),
            "response_body_format": body_format,
            "response_body": body,
        }
    except httpx.RequestError as exc:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        return {
            **probe,
            "request_url": str(exc.request.url),
            "status_code": None,
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def main() -> int:
    args = parse_args()

    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=args.timeout,
        headers={
            "Accept": "application/json",
            "User-Agent": "qingshang-cnkgraph-probe/0.1",
        },
        follow_redirects=True,
    ) as client:
        results = [run_probe(client, probe) for probe in PROBES]

    successful = sum(result["ok"] for result in results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_collection": "docs/cnkgraph/postman/词汇、典故.postman_collection.json",
        "base_url": args.base_url.rstrip("/"),
        "summary": {
            "total": len(results),
            "successful": successful,
            "failed": len(results) - successful,
        },
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved probe results to: {args.output}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if successful == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
