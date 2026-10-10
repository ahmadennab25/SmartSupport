from django.contrib import admin
from django.utils.text import Truncator

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "customer", "channel", "role", "short_content", "tool_calls", "latency_ms")
    list_filter = ("channel", "role")
    search_fields = ("content", "customer__full_name", "customer__phone_number")
    date_hierarchy = "created_at"
    readonly_fields = [field.name for field in ChatMessage._meta.fields]

    @admin.display(description="Message")
    def short_content(self, obj):
        return Truncator(obj.content).chars(70)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
