"""Measure retrieval quality: does the right document come first, and where should the threshold be?"""
import os
import statistics
import time

import psutil

from apps.knowledge.models import KnowledgeChunk
from apps.knowledge.services import retrieval_service

from . import scoring
from .cases import RETRIEVAL_IN_SCOPE, RETRIEVAL_OUT_OF_SCOPE

DEFAULT_THRESHOLDS = [round(0.10 + 0.05 * step, 2) for step in range(9)]  # 0.10 ... 0.50


def _search(case, client):
    started = time.perf_counter()
    # min_score=-1 keeps every result, so ranks and scores can be analysed; top_k is capped at 10.
    results = retrieval_service.search(case.query, top_k=10, language=case.language, min_score=-1.0, client=client)
    return results, (time.perf_counter() - started) * 1000


def run_retrieval_evaluation(in_scope=None, out_of_scope=None, thresholds=None, client=None, progress=None) -> dict:
    in_scope = list(in_scope if in_scope is not None else RETRIEVAL_IN_SCOPE)
    out_of_scope = list(out_of_scope if out_of_scope is not None else RETRIEVAL_OUT_OF_SCOPE)
    thresholds = thresholds or DEFAULT_THRESHOLDS
    if not KnowledgeChunk.objects.exists():
        raise RuntimeError("The knowledge base is empty. Run: python manage.py ingest_knowledge")

    process = psutil.Process(os.getpid())
    rss_before = process.memory_info().rss / 1024 / 1024
    in_rows, out_rows = [], []

    for case in in_scope:
        results, latency = _search(case, client)
        rank = next((i for i, item in enumerate(results, start=1) if item.slug in case.expected), None)
        row = {
            "query": case.query, "language": case.language, "expected": list(case.expected), "rank": rank,
            "top_slug": results[0].slug if results else None, "top_score": results[0].score if results else 0.0,
            "latency_ms": latency,
        }
        in_rows.append(row)
        if progress:
            progress("in", row)

    for case in out_of_scope:
        results, latency = _search(case, client)
        row = {
            "query": case.query, "language": case.language, "expected": [], "rank": None,
            "top_slug": results[0].slug if results else None, "top_score": results[0].score if results else 0.0,
            "latency_ms": latency,
        }
        out_rows.append(row)
        if progress:
            progress("out", row)

    latencies = [row["latency_ms"] for row in in_rows + out_rows]
    table = scoring.threshold_table([r["top_score"] for r in in_rows], [r["top_score"] for r in out_rows], thresholds)
    mean_or_none = lambda values: statistics.fmean(values) if values else None
    return {
        "metrics": scoring.retrieval_metrics([row["rank"] for row in in_rows]),
        "in_scope": in_rows,
        "out_of_scope": out_rows,
        "thresholds": table,
        "suggested_threshold": scoring.best_threshold(table),
        "mean_score_in_scope": mean_or_none([r["top_score"] for r in in_rows]),
        "mean_score_out_of_scope": mean_or_none([r["top_score"] for r in out_rows]),
        "latency_ms": {"mean": mean_or_none(latencies), "p95": scoring.percentile(latencies, 95)},
        "memory": {"rss_before_mb": rss_before, "rss_after_mb": process.memory_info().rss / 1024 / 1024},
    }
