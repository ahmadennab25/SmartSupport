"""Pure scoring and statistics helpers (no Django, no network)."""
import math
import re
import statistics

from .cases import SAFETY_CATEGORIES

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,")


def normalize(text) -> str:
    """Lower-case and turn Arabic-Indic digits into Western digits, so '١٤' matches '14'."""
    return (text or "").translate(_DIGITS).lower()


def check_tools(case, tool_calls) -> list[str]:
    called = set(tool_calls)
    failures = [f"tool not called: {tool}" for tool in case.expect_tools if tool not in called]
    if case.any_tools and not called & set(case.any_tools):
        failures.append("none of these tools was called: " + ", ".join(case.any_tools))
    failures += [f"forbidden tool called: {tool}" for tool in case.forbid_tools if tool in called]
    return failures


def check_content(case, reply) -> list[str]:
    text = normalize(reply)
    failures = []
    for group in case.contain:
        if not any(normalize(alternative) in text for alternative in group):
            failures.append("reply lacks any of: " + " | ".join(group[:5]))
    for pattern in case.forbid_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            failures.append(f"forbidden pattern matched: {pattern}")
    return failures


def has_tool_expectation(case) -> bool:
    return bool(case.expect_tools or case.any_tools or case.forbid_tools)


def has_content_expectation(case) -> bool:
    return bool(case.contain or case.forbid_patterns)


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _rate(passed: int, total: int):
    return passed / total if total else None


def summarize(runs: list[dict]) -> dict:
    """Aggregate the per-run dicts produced by the runner."""
    latencies = [run["latency_ms"] for run in runs]
    tool_runs = [run for run in runs if run["has_tool_expectation"]]
    content_runs = [run for run in runs if run["has_content_expectation"]]
    safety_runs = [run for run in runs if run["category"] in SAFETY_CATEGORIES]

    by_category = {}
    for category in sorted({run["category"] for run in runs}):
        group = [run for run in runs if run["category"] == category]
        by_category[category] = {
            "runs": len(group),
            "passed": sum(run["passed"] for run in group),
            "success_rate": _rate(sum(run["passed"] for run in group), len(group)),
            "mean_latency_ms": statistics.fmean(run["latency_ms"] for run in group),
        }

    return {
        "runs": len(runs),
        "passed": sum(run["passed"] for run in runs),
        "success_rate": _rate(sum(run["passed"] for run in runs), len(runs)),
        "tool_accuracy": _rate(sum(run["tool_ok"] for run in tool_runs), len(tool_runs)),
        "content_accuracy": _rate(sum(run["content_ok"] for run in content_runs), len(content_runs)),
        "safety_pass_rate": _rate(sum(run["passed"] for run in safety_runs), len(safety_runs)),
        "failed_calls": sum(run["failed"] for run in runs),
        "latency_ms": {
            "mean": statistics.fmean(latencies) if latencies else None,
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "max": max(latencies) if latencies else None,
        },
        "tokens": {
            "prompt": sum(run["prompt_tokens"] for run in runs),
            "completion": sum(run["completion_tokens"] for run in runs),
        },
        "by_category": by_category,
    }


# ---------------------------------------------------------------- retrieval metrics

def retrieval_metrics(ranks: list) -> dict:
    """ranks: for each in-scope question, the 1-based rank of the first correct chunk (None = not found)."""
    total = len(ranks)
    if not total:
        return {"questions": 0, "hit_at_1": None, "hit_at_3": None, "hit_at_4": None, "mrr": None}
    hit = lambda k: sum(1 for rank in ranks if rank is not None and rank <= k) / total
    return {
        "questions": total,
        "hit_at_1": hit(1),
        "hit_at_3": hit(3),
        "hit_at_4": hit(4),
        "mrr": sum(1 / rank for rank in ranks if rank) / total,
    }


def threshold_table(in_scope_scores: list, out_scope_scores: list, thresholds: list) -> list[dict]:
    """For each threshold: how many in-scope questions are answered and how many out-of-scope ones
    wrongly are. A question counts as 'answered' when its best chunk scores >= threshold."""
    rows = []
    for threshold in thresholds:
        answered_in = sum(1 for score in in_scope_scores if score >= threshold)
        answered_out = sum(1 for score in out_scope_scores if score >= threshold)
        total = len(in_scope_scores) + len(out_scope_scores)
        rows.append(
            {
                "threshold": round(threshold, 2),
                "in_scope_recall": _rate(answered_in, len(in_scope_scores)),
                "out_of_scope_false_positive_rate": _rate(answered_out, len(out_scope_scores)),
                "accuracy": _rate(answered_in + (len(out_scope_scores) - answered_out), total),
            }
        )
    return rows


def best_threshold(rows: list[dict]):
    """The middle of the thresholds that reach the highest accuracy (None if there are no rows)."""
    scored = [row for row in rows if row["accuracy"] is not None]
    if not scored:
        return None
    top = max(row["accuracy"] for row in scored)
    tied = sorted(row["threshold"] for row in scored if row["accuracy"] == top)
    return tied[len(tied) // 2]
