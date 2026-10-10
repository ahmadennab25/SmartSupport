"""Write evaluation results to disk: results.json, CSV files and a markdown summary."""
import csv
import json
from pathlib import Path


def _pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _ms(value) -> str:
    return "n/a" if value is None else f"{value:,.0f} ms"


def _num(value, digits=2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def render_summary(payload: dict) -> str:
    out = ["# SmartSupport AI - evaluation summary", ""]
    out.append(
        f"Generated: {payload.get('generated_at', '?')} | chat model: {payload.get('model', '?')} | "
        f"embedding model: {payload.get('embedding_model', '?')}"
    )
    out.append("")

    agent = payload.get("agent") or []
    if agent:
        out += ["## 1. Agent (end-to-end, real OpenAI calls)", ""]
        if len(agent) > 1:
            out.append(
                _table(
                    ["Prompt", "Runs", "Success", "Tool accuracy", "Content accuracy", "Safety/grounding", "Mean latency", "p95 latency"],
                    [
                        [
                            block["prompt_version"], s["runs"], _pct(s["success_rate"]), _pct(s["tool_accuracy"]),
                            _pct(s["content_accuracy"]), _pct(s["safety_pass_rate"]),
                            _ms(s["latency_ms"]["mean"]), _ms(s["latency_ms"]["p95"]),
                        ]
                        for block in agent
                        for s in [block["summary"]]
                    ],
                )
            )
            out.append("")
        for block in agent:
            s = block["summary"]
            mem = block.get("memory", {})
            out += [f"### Prompt {block['prompt_version']}", ""]
            out.append(
                _table(
                    ["Metric", "Value"],
                    [
                        ["Runs / passed", f"{s['runs']} / {s['passed']}"],
                        ["Task success rate", _pct(s["success_rate"])],
                        ["Tool selection accuracy", _pct(s["tool_accuracy"])],
                        ["Reply content accuracy", _pct(s["content_accuracy"])],
                        ["Safety and grounding pass rate", _pct(s["safety_pass_rate"])],
                        ["Calls that fell back to the error message", s["failed_calls"]],
                        ["Latency mean / p50 / p95 / max", " / ".join(_ms(s["latency_ms"][k]) for k in ("mean", "p50", "p95", "max"))],
                        ["Tokens prompt / completion", f"{s['tokens']['prompt']:,} / {s['tokens']['completion']:,}"],
                        ["Memory baseline / peak / end (MB)", " / ".join(_num(mem.get(k), 1) for k in ("baseline_mb", "peak_mb", "end_mb"))],
                        ["Largest memory growth in one case (MB)", _num(mem.get("max_case_delta_mb"), 1)],
                    ],
                )
            )
            out += ["", _table(
                ["Category", "Runs", "Passed", "Success", "Mean latency"],
                [[c, v["runs"], v["passed"], _pct(v["success_rate"]), _ms(v["mean_latency_ms"])] for c, v in s["by_category"].items()],
            ), ""]
            failed = [run for run in block["runs"] if not run["passed"]]
            if failed:
                out += ["Failed runs:", ""]
                out += [f"- `{run['case_id']}` ({run['category']}): " + "; ".join(run["failures"]) for run in failed]
                out.append("")

    retrieval = payload.get("retrieval")
    if retrieval:
        m = retrieval["metrics"]
        out += ["## 2. Retrieval (RAG)", ""]
        out.append(
            _table(
                ["Metric", "Value"],
                [
                    ["In-scope questions", m["questions"]],
                    ["Hit@1 / Hit@3 / Hit@4", " / ".join(_pct(m[k]) for k in ("hit_at_1", "hit_at_3", "hit_at_4"))],
                    ["MRR", _num(m["mrr"], 3)],
                    ["Search latency mean / p95 (embedding + similarity)", f"{_ms(retrieval['latency_ms']['mean'])} / {_ms(retrieval['latency_ms']['p95'])}"],
                    ["Mean best score, in-scope / out-of-scope", f"{_num(retrieval['mean_score_in_scope'], 3)} / {_num(retrieval['mean_score_out_of_scope'], 3)}"],
                    ["Suggested RAG_MIN_SCORE", retrieval.get("suggested_threshold")],
                ],
            )
        )
        out += ["", "Threshold analysis (question counts as answered when its best chunk scores >= threshold):", ""]
        out.append(
            _table(
                ["Threshold", "In-scope answered", "Out-of-scope wrongly answered", "Accuracy"],
                [[r["threshold"], _pct(r["in_scope_recall"]), _pct(r["out_of_scope_false_positive_rate"]), _pct(r["accuracy"])] for r in retrieval["thresholds"]],
            )
        )
        misses = [row for row in retrieval["in_scope"] if row["rank"] is None or row["rank"] > 1]
        if misses:
            out += ["", "In-scope questions whose correct document was not ranked first:", ""]
            out += [f"- rank {row['rank'] or 'not found'}: {row['query']} (expected {', '.join(row['expected'])}; got {row['top_slug']})" for row in misses]
        out.append("")
    return "\n".join(out) + "\n"


def write_results(output_dir, payload: dict) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    (directory / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (directory / "summary.md").write_text(render_summary(payload), encoding="utf-8")

    agent_columns = [
        "prompt_version", "repetition", "case_id", "category", "passed", "tool_ok", "content_ok", "latency_ms",
        "tools_called", "failures", "tickets_created", "rss_mb", "prompt_tokens", "completion_tokens", "message", "reply",
    ]
    with (directory / "agent_runs.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(agent_columns)
        for block in payload.get("agent") or []:
            for run in block["runs"]:
                writer.writerow(
                    [
                        block["prompt_version"], run["repetition"], run["case_id"], run["category"], run["passed"],
                        run["tool_ok"], run["content_ok"], run["latency_ms"], "|".join(run["tool_calls"]),
                        "; ".join(run["failures"]), run["tickets_created"], round(run["rss_mb"], 1),
                        run["prompt_tokens"], run["completion_tokens"], run["message"], run["reply"],
                    ]
                )

    retrieval = payload.get("retrieval")
    if retrieval:
        with (directory / "retrieval_cases.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["scope", "language", "query", "expected", "rank", "top_slug", "top_score", "latency_ms"])
            for scope, rows in (("in", retrieval["in_scope"]), ("out", retrieval["out_of_scope"])):
                for row in rows:
                    writer.writerow(
                        [scope, row["language"], row["query"], "|".join(row["expected"]), row.get("rank"),
                         row["top_slug"], round(row["top_score"], 4), round(row["latency_ms"], 1)]
                    )
    return directory
