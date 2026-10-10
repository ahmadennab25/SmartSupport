from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Ticket, TicketMessage

PRIORITY_COLORS = {
    Ticket.Priority.LOW: "#6c757d",
    Ticket.Priority.MEDIUM: "#0d6efd",
    Ticket.Priority.HIGH: "#fd7e14",
    Ticket.Priority.URGENT: "#dc3545",
}


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 1


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "subject",
        "customer",
        "order",
        "category",
        "priority_badge",
        "status",
        "escalated_to_human",
        "assigned_to",
        "created_at",
    )
    list_filter = ("status", "priority", "category", "escalated_to_human", "created_by_ai")
    search_fields = ("subject", "description", "customer__full_name", "customer__phone_number")
    autocomplete_fields = ("customer",)
    raw_id_fields = ("order",)
    readonly_fields = ("created_at", "updated_at", "resolved_at")
    date_hierarchy = "created_at"
    inlines = [TicketMessageInline]
    actions = ["take_ticket", "escalate_to_human", "mark_resolved"]

    @admin.display(description="Ticket", ordering="id")
    def reference(self, obj):
        return obj.reference

    @admin.display(description="Priority", ordering="priority")
    def priority_badge(self, obj):
        return format_html(
            '<b style="color:{}">{}</b>',
            PRIORITY_COLORS.get(obj.priority, "#000"),
            obj.get_priority_display(),
        )

    @admin.action(description="Assign to me and set in progress")
    def take_ticket(self, request, queryset):
        updated = queryset.exclude(status__in=Ticket.CLOSED_STATUSES).update(
            assigned_to=request.user, status=Ticket.Status.IN_PROGRESS
        )
        self.message_user(request, f"{updated} ticket(s) assigned to you.")

    @admin.action(description="Escalate to a human agent")
    def escalate_to_human(self, request, queryset):
        updated = queryset.exclude(status__in=Ticket.CLOSED_STATUSES).update(
            status=Ticket.Status.ESCALATED, escalated_to_human=True
        )
        self.message_user(request, f"{updated} ticket(s) escalated.")

    @admin.action(description="Mark as resolved")
    def mark_resolved(self, request, queryset):
        updated = queryset.exclude(status__in=Ticket.CLOSED_STATUSES).update(
            status=Ticket.Status.RESOLVED, resolved_at=timezone.now()
        )
        self.message_user(request, f"{updated} ticket(s) resolved.")
