"""跑评估集，输出指标到 markdown 报告。

用法：
  uv run python -m scripts.eval.run_eval --golden eval/golden.jsonl --output docs/specs/2026-05-27-measurement-and-fix/report-baseline.md
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

import httpx

from scripts.eval.sse_client import ask_question


BASE_URL = os.environ.get("EVAL_BASE_URL", "http://localhost:8080")
TOKEN = os.environ.get("EVAL_TOKEN")  # 必填，从已登录的浏览器 localStorage 复制


async def create_conversation(kb_id: int) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/api/v1/qa/conversations",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"knowledge_base_id": kb_id},
        )
        resp.raise_for_status()
        return resp.json()["data"]["conv_id"]


def citation_match(expected: list[str], actual: list[dict]) -> bool:
    """期望引用至少命中 1 个即算通过。expected 格式 'chunk:42'。"""
    if not expected:
        return True  # 如果没标期望，默认通过（虽然指标会失真）
    actual_ids = {f"chunk:{c.get('chunk_id')}" for c in actual}
    return any(e in actual_ids for e in expected)


def keyword_coverage(keywords: list[str], answer: str) -> float:
    if not keywords:
        return 1.0
    hits = sum(1 for k in keywords if k in answer)
    return hits / len(keywords)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--label", default="baseline", help="baseline or after")
    args = parser.parse_args()

    if not TOKEN:
        print("Error: EVAL_TOKEN environment variable is required.")
        sys.exit(1)

    golden = [json.loads(l) for l in open(args.golden, encoding="utf-8")]
    print(f"Evaluating {len(golden)} samples...")

    results = []
    for i, sample in enumerate(golden, 1):
        kb_id = sample["kb_id"]
        question = sample["question"]
        try:
            conv_id = await create_conversation(kb_id)
            r = await ask_question(BASE_URL, TOKEN, conv_id, question, timeout=120)
        except Exception as e:
            print(f"  [{i}/{len(golden)}] ERROR: {e}")
            results.append(
                {**sample, "result": {"outcome": "error", "error_code": str(e)}}
            )
            continue

        citation_ok = citation_match(sample.get("expected_citations", []), r.citations)
        kw_coverage = keyword_coverage(
            sample.get("expected_answer_keywords", []), r.answer
        )
        print(
            f"  [{i}/{len(golden)}] outcome={r.outcome} citation_ok={citation_ok} kw_cov={kw_coverage:.2f} "
            f"ttft={r.ttft_ms}ms total={r.total_ms}ms"
        )
        results.append(
            {
                **sample,
                "result": {
                    "outcome": r.outcome,
                    "error_code": r.error_code,
                    "citation_ok": citation_ok,
                    "kw_coverage": kw_coverage,
                    "ttft_ms": r.ttft_ms,
                    "total_ms": r.total_ms,
                    "answer_excerpt": r.answer[:200],
                },
            }
        )

    # 汇总
    total = len(results)
    if total == 0:
        print("No results to report.")
        return

    success = sum(1 for r in results if r["result"]["outcome"] == "success")
    citation_hit = sum(1 for r in results if r["result"].get("citation_ok"))
    avg_kw = statistics.mean(
        [
            r["result"].get("kw_coverage", 0)
            for r in results
            if "kw_coverage" in r["result"]
        ]
        or [0]
    )
    ttfts = [r["result"]["ttft_ms"] for r in results if r["result"].get("ttft_ms")]
    totals = [r["result"]["total_ms"] for r in results if r["result"].get("total_ms")]
    outcomes = Counter(r["result"]["outcome"] for r in results)

    def pct(values, p):
        """线性插值分位数，避免 int 截断导致的系统性偏差。"""
        if not values:
            return None
        values = sorted(values)
        n = len(values)
        idx = p * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        if lo == hi:
            return values[lo]
        frac = idx - lo
        return round(values[lo] + frac * (values[hi] - values[lo]), 1)

    report_lines = [
        f"# 评估报告 — {args.label}",
        f"",
        f"**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**评估集**: `{args.golden}` ({total} 道)",
        f"",
        f"## 核心指标",
        f"",
        f"| 指标 | 值 |",
        f"|---|---|",
        f"| 总成功率 | **{success}/{total} = {success / total * 100:.1f}%** |",
        f"| 引用命中率 | **{citation_hit}/{total} = {citation_hit / total * 100:.1f}%** |",
        f"| 平均关键词覆盖率 | **{avg_kw:.2f}** |",
        f"| TTFT p50 / p95 | {pct(ttfts, 0.5)} / {pct(ttfts, 0.95)} ms |",
        f"| Total p50 / p95 | {pct(totals, 0.5)} / {pct(totals, 0.95)} ms |",
        f"",
        f"## Outcome 分布",
        f"",
    ]
    for outcome, n in outcomes.most_common():
        report_lines.append(f"- {outcome}: {n}")

    report_lines += [
        f"",
        f"## 失败样本",
        f"",
    ]
    for r in results:
        if r["result"]["outcome"] != "success" or not r["result"].get("citation_ok"):
            report_lines.append(
                f"- KB {r['kb_id']} / Q: {r['question']}\n"
                f"  outcome={r['result']['outcome']} citation_ok={r['result'].get('citation_ok')} "
                f"err={r['result'].get('error_code')}"
            )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport written: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
