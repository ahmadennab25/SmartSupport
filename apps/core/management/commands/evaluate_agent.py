import datetime as dt
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Evaluate the agent (task success, tool choice, grounding, latency, memory) and the RAG retrieval "
        "(Hit@k, MRR, threshold analysis). Uses the real OpenAI API."
    )

    def add_arguments(self, parser):
        parser.add_argument("--only", choices=["agent", "retrieval", "all"], default="all")
        parser.add_argument("--prompt-version", choices=["v1", "v2"], default="v2", help="System prompt to test.")
        parser.add_argument("--compare", action="store_true", help="Run the agent cases with prompt v1 and v2.")
        parser.add_argument("--repeat", type=int, default=1, help="Run every agent case N times (LLM answers vary).")
        parser.add_argument("--limit", type=int, default=0, help="Only the first N agent cases (quick smoke test).")
        parser.add_argument("--keep-data", action="store_true", help="Keep tickets created during the agent cases.")
        parser.add_argument("--output", help="Output folder (default: evaluation/results/<timestamp>).")

    def handle(self, *args, **options):
        from evaluation.cases import AGENT_CASES
        from evaluation.report import write_results
        from evaluation.retrieval_eval import run_retrieval_evaluation
        from evaluation.runner import run_agent_evaluation

        if options["repeat"] < 1:
            raise CommandError("--repeat must be at least 1.")
        payload = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "model": settings.OPENAI_MODEL,
            "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
            "agent": [],
            "retrieval": None,
        }

        try:
            if options["only"] in ("agent", "all"):
                cases = AGENT_CASES[: options["limit"]] if options["limit"] else AGENT_CASES
                versions = ["v1", "v2"] if options["compare"] else [options["prompt_version"]]
                for version in versions:
                    self.stdout.write(f"\n== Agent, prompt {version}: {len(cases)} cases x {options['repeat']} ==")
                    payload["agent"].append(
                        run_agent_evaluation(
                            cases, prompt_version=version, repeat=options["repeat"],
                            rollback=not options["keep_data"], progress=self._print_agent,
                        )
                    )
            if options["only"] in ("retrieval", "all"):
                self.stdout.write("\n== Retrieval ==")
                payload["retrieval"] = run_retrieval_evaluation(progress=self._print_retrieval)
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        default_dir = Path(settings.BASE_DIR) / "evaluation" / "results" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        directory = write_results(options["output"] or default_dir, payload)

        self.stdout.write("\n== Summary ==")
        for block in payload["agent"]:
            s = block["summary"]
            self.stdout.write(
                f"prompt {block['prompt_version']}: success={self._pct(s['success_rate'])} "
                f"tools={self._pct(s['tool_accuracy'])} safety={self._pct(s['safety_pass_rate'])} "
                f"latency mean={s['latency_ms']['mean']:.0f}ms p95={s['latency_ms']['p95']:.0f}ms "
                f"memory peak={block['memory']['peak_mb']:.0f}MB"
            )
        if payload["retrieval"]:
            m = payload["retrieval"]["metrics"]
            self.stdout.write(
                f"retrieval: hit@1={self._pct(m['hit_at_1'])} hit@3={self._pct(m['hit_at_3'])} mrr={m['mrr']:.3f} "
                f"suggested RAG_MIN_SCORE={payload['retrieval']['suggested_threshold']}"
            )
        self.stdout.write(self.style.SUCCESS(f"Results written to {directory}"))

    @staticmethod
    def _pct(value):
        return "n/a" if value is None else f"{value * 100:.1f}%"

    def _print_agent(self, version, run):
        status = self.style.SUCCESS("PASS") if run["passed"] else self.style.ERROR("FAIL")
        self.stdout.write(f"[{version}] {run['case_id']:<12} {status} {run['latency_ms']:>5} ms  tools={','.join(run['tool_calls']) or '-'}")

    def _print_retrieval(self, scope, row):
        rank = row["rank"] if scope == "in" else "-"
        self.stdout.write(f"[{scope}] rank={rank!s:<4} score={row['top_score']:.3f} top={row['top_slug']}")
