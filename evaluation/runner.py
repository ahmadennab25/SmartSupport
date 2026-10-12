"""Run the agent test cases against the real agent and collect accuracy, latency and memory."""
import os

import psutil
from django.conf import settings
from django.db import transaction
from django.test.utils import override_settings

from apps.agent.agent import SupportAgent
from apps.orders.models import Order
from apps.tickets.models import Ticket

from . import scoring
from .cases import AGENT_CASES


class _Rollback(Exception):
    """Raised on purpose to undo the database changes (tickets...) a test case made."""


def get_eval_customer():
    order = Order.objects.select_related("customer").filter(order_number=1025).first()
    if order is None:
        raise RuntimeError("Order 1025 not found. Run: python manage.py seed_demo_data --phone <your number>")
    return order.customer


def _mb(num_bytes) -> float:
    return num_bytes / 1024 / 1024


def run_agent_evaluation(cases=None, prompt_version=None, repeat=1, rollback=True, agent=None, progress=None) -> dict:
    """Run every case `repeat` times, each as a fresh conversation (history is only what the case defines).
    With rollback=True the database changes of each case (tickets, escalations) are undone."""
    cases = list(cases if cases is not None else AGENT_CASES)
    version = prompt_version or getattr(settings, "AGENT_PROMPT_VERSION", "v3")
    customer = get_eval_customer()
    process = psutil.Process(os.getpid())
    baseline = _mb(process.memory_info().rss)
    peak = baseline
    max_delta = 0.0
    runs: list[dict] = []

    with override_settings(AGENT_PROMPT_VERSION=version):
        agent = agent or SupportAgent()
        for repetition in range(1, repeat + 1):
            for case in cases:
                rss_before = _mb(process.memory_info().rss)
                tickets_before = Ticket.objects.count()
                history = [{"role": role, "content": content} for role, content in case.history]
                tickets_created = 0
                try:
                    with transaction.atomic():
                        result = agent.run(customer, case.message, history)
                        tickets_created = Ticket.objects.count() - tickets_before
                        if rollback:
                            raise _Rollback
                except _Rollback:
                    pass

                rss_after = _mb(process.memory_info().rss)
                peak = max(peak, rss_after)
                max_delta = max(max_delta, rss_after - rss_before)

                tool_failures = scoring.check_tools(case, result.tool_calls)
                content_failures = scoring.check_content(case, result.reply)
                failures = tool_failures + content_failures
                if result.failed:
                    failures.append("agent returned the error fallback message")
                run = {
                    "case_id": case.id,
                    "category": case.category,
                    "repetition": repetition,
                    "message": case.message,
                    "reply": result.reply,
                    "tool_calls": list(result.tool_calls),
                    "latency_ms": result.latency_ms,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "failed": result.failed,
                    "has_tool_expectation": scoring.has_tool_expectation(case),
                    "has_content_expectation": scoring.has_content_expectation(case),
                    "tool_ok": not tool_failures,
                    "content_ok": not content_failures,
                    "passed": not failures,
                    "failures": failures,
                    "tickets_created": tickets_created,
                    "rss_mb": rss_after,
                }
                runs.append(run)
                if progress:
                    progress(version, run)

    peak_wset = getattr(process.memory_info(), "peak_wset", None)  # Windows only
    if peak_wset:
        peak = max(peak, _mb(peak_wset))
    return {
        "prompt_version": version,
        "runs": runs,
        "summary": scoring.summarize(runs),
        "memory": {
            "baseline_mb": baseline,
            "peak_mb": peak,
            "end_mb": _mb(process.memory_info().rss),
            "max_case_delta_mb": max_delta,
        },
    }
