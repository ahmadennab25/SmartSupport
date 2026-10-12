import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Re-score a saved evaluation results.json with the current checks (no OpenAI calls)."

    def add_arguments(self, parser):
        parser.add_argument("input", help="Path to a results.json written by evaluate_agent.")
        parser.add_argument("--output", help="Output folder (default: <input folder>-rescored).")

    def handle(self, *args, **options):
        from evaluation.cases import AGENT_CASES, HOLDOUT_CASES
        from evaluation.report import write_results
        from evaluation.rescore import rescore_payload

        source = Path(options["input"])
        if not source.is_file():
            raise CommandError(f"File not found: {source}")
        payload = json.loads(source.read_text(encoding="utf-8"))
        try:
            new_payload, changed = rescore_payload(payload, AGENT_CASES + HOLDOUT_CASES)
        except KeyError as exc:
            raise CommandError(str(exc)) from exc
        new_payload["rescored_from"] = str(source)

        output = Path(options["output"]) if options["output"] else source.parent.with_name(source.parent.name + "-rescored")
        directory = write_results(output, new_payload)

        self.stdout.write("prompt   before -> after (success rate)")
        for old, new in zip(payload.get("agent") or [], new_payload.get("agent") or []):
            self.stdout.write(
                f"{old['prompt_version']:<8} {self._pct(old['summary']['success_rate'])} -> {self._pct(new['summary']['success_rate'])}"
                f"   tools {self._pct(old['summary']['tool_accuracy'])} -> {self._pct(new['summary']['tool_accuracy'])}"
                f"   safety {self._pct(old['summary']['safety_pass_rate'])} -> {self._pct(new['summary']['safety_pass_rate'])}"
            )
        self.stdout.write(f"{len(changed)} run(s) changed verdict:")
        for item in changed:
            self.stdout.write(
                f"  [{item['prompt_version']}] {item['case_id']} rep {item['repetition']}: "
                f"{'PASS' if item['was_passed'] else 'FAIL'} -> {'PASS' if item['now_passed'] else 'FAIL'}"
            )
        self.stdout.write(self.style.SUCCESS(f"Re-scored results written to {directory}"))

    @staticmethod
    def _pct(value):
        return "n/a" if value is None else f"{value * 100:.1f}%"
