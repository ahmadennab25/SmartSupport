import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="KnowledgeDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("slug", models.SlugField(max_length=80)),
                ("language", models.CharField(choices=[("ar", "Arabic"), ("en", "English")], max_length=2)),
                ("title", models.CharField(max_length=200)),
                ("source_path", models.CharField(blank=True, max_length=300)),
                ("content_hash", models.CharField(blank=True, max_length=64)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["slug", "language"],
                "constraints": [
                    models.UniqueConstraint(fields=("slug", "language"), name="unique_document_slug_language")
                ],
            },
        ),
        migrations.CreateModel(
            name="KnowledgeChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("chunk_index", models.PositiveIntegerField()),
                ("section", models.CharField(blank=True, max_length=200)),
                ("content", models.TextField()),
                (
                    "embedding",
                    django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), size=1536),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="knowledge.knowledgedocument",
                    ),
                ),
            ],
            options={
                "ordering": ["document_id", "chunk_index"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("document", "chunk_index"), name="unique_chunk_index_per_document"
                    )
                ],
            },
        ),
    ]
