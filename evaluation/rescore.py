"""Re-score saved evaluation results with the current checks, without calling OpenAI again.

Useful after a check turned out to be too strict (for example it missed a valid Arabic word form): the saved
replies are judged again and the summaries are rebuilt. The agent's answers are never changed.
"""
import copy

from . import scoring


def rescore_payload(payload: dict, cases) -> tuple[dict, list[dict]]:
    """Returns (new payload, list of runs whose verdict changed)."""
    by_id = {case.id: case for case in cases}
    new = copy.deepcopy(payload)
    changed: list[dict] = []
    for block in new.get("agent") or []:
        for run in block["runs"]:
            case = by_id.get(run["case_id"])
            if case is None:
                raise KeyError(f"Unknown case id in the results file: {run['case_id']}")
            was_passed = run["passed"]
            tool_failures = scoring.check_tools(case, run["tool_calls"])
            content_failures = scoring.check_content(case, run["reply"])
            failures = tool_failures + content_failures
            if run["failed"]:
                failures.append("agent returned the error fallback message")
            run.update(
                has_tool_expectation=scoring.has_tool_expectation(case),
                has_content_expectation=scoring.has_content_expectation(case),
                tool_ok=not tool_failures,
                content_ok=not content_failures,
                passed=not failures,
                failures=failures,
            )
            if run["passed"] != was_passed:
                changed.append(
                    {
                        "prompt_version": block["prompt_version"], "case_id": run["case_id"],
                        "repetition": run["repetition"], "was_passed": was_passed, "now_passed": run["passed"],
                    }
                )
        block["summary"] = scoring.summarize(block["runs"])
    return new, changed
