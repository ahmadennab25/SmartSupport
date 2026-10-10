from django.contrib import admin
from django.db.models import Count

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "phone_number",
        "preferred_language",
        "city",
        "orders_count",
        "tickets_count",
        "is_active",
    )
    list_filter = ("preferred_language", "is_active", "city")
    search_fields = ("full_name", "phone_number", "email")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_orders=Count("orders", distinct=True), _tickets=Count("tickets", distinct=True))
        )

    @admin.display(description="Orders", ordering="_orders")
    def orders_count(self, obj):
        return obj._orders

    @admin.display(description="Tickets", ordering="_tickets")
    def tickets_count(self, obj):
        return obj._tickets
