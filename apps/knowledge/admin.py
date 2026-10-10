from django.contrib import admin
from django.db.models import Count
from django.utils.text import Truncator

from .models import KnowledgeChunk, KnowledgeDocument


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "language", "chunks_count", "is_active", "updated_at")
    list_filter = ("language", "is_active")
    search_fields = ("title", "slug")
    readonly_fields = ("slug", "language", "title", "source_path", "content_hash", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_chunks=Count("chunks"))

    @admin.display(description="Chunks", ordering="_chunks")
    def chunks_count(self, obj):
        return obj._chunks

    def has_add_permission(self, request):
        return False  # documents come from knowledge_base/*.md via `manage.py ingest_knowledge`


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "chunk_index", "section", "preview")
    list_filter = ("document__language", "document")
    search_fields = ("content", "section")
    exclude = ("embedding",)
    readonly_fields = ("document", "chunk_index", "section", "content", "created_at", "updated_at")

    @admin.display(description="Content")
    def preview(self, obj):
        return Truncator(obj.content).chars(90)

    def has_add_permission(self, request):
        return False
