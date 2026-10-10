from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.services.ingestion_service import ingest_directory


class Command(BaseCommand):
    help = "Chunk the policy documents in knowledge_base/, embed them with OpenAI and store them in PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument("--path", help="Folder with <slug>.<ar|en>.md files (default: knowledge_base/).")
        parser.add_argument("--force", action="store_true", help="Re-embed documents even if unchanged.")
        parser.add_argument("--prune", action="store_true", help="Delete documents whose file no longer exists.")

    def handle(self, *args, **options):
        default_dir = getattr(settings, "KNOWLEDGE_BASE_DIR", settings.BASE_DIR / "knowledge_base")
        directory = Path(options["path"] or default_dir)
        if not directory.is_dir():
            raise CommandError(f"Folder not found: {directory}")

        report = ingest_directory(directory, force=options["force"], prune=options["prune"])

        self.stdout.write(
            f"created={report.created} updated={report.updated} skipped={report.skipped} "
            f"pruned={report.pruned} chunks_written={report.chunks}"
        )
        for error in report.errors:
            self.stderr.write(self.style.ERROR(error))
        if report.errors:
            raise CommandError("Some documents could not be indexed (see errors above).")
        self.stdout.write(self.style.SUCCESS("Knowledge base is up to date."))
