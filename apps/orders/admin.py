from django.contrib import admin
from django.utils import timezone

from .models import Order, OrderItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "name_ar", "category", "price", "stock_quantity", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("sku", "name", "name_ar")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ("product",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer",
        "status",
        "payment_method",
        "payment_status",
        "total_amount",
        "estimated_delivery_date",
        "placed_at",
    )
    list_filter = ("status", "payment_method", "payment_status")
    search_fields = ("order_number", "customer__full_name", "customer__phone_number", "tracking_number")
    autocomplete_fields = ("customer",)
    date_hierarchy = "placed_at"
    inlines = [OrderItemInline]
    readonly_fields = ("total_amount", "created_at", "updated_at")
    actions = ["mark_shipped", "mark_delivered", "mark_cancelled"]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalculate_total()

    @admin.action(description="Mark selected orders as shipped")
    def mark_shipped(self, request, queryset):
        updated = queryset.filter(
            status__in=[Order.Status.CONFIRMED, Order.Status.PROCESSING]
        ).update(status=Order.Status.SHIPPED, shipped_at=timezone.now())
        self.message_user(request, f"{updated} order(s) marked as shipped.")

    @admin.action(description="Mark selected orders as delivered")
    def mark_delivered(self, request, queryset):
        updated = queryset.filter(
            status__in=[Order.Status.SHIPPED, Order.Status.OUT_FOR_DELIVERY]
        ).update(status=Order.Status.DELIVERED, delivered_at=timezone.now())
        self.message_user(request, f"{updated} order(s) marked as delivered.")

    @admin.action(description="Cancel selected orders (only pending/confirmed/processing)")
    def mark_cancelled(self, request, queryset):
        updated = queryset.filter(status__in=Order.CANCELLABLE_STATUSES).update(
            status=Order.Status.CANCELLED
        )
        self.message_user(request, f"{updated} order(s) cancelled.")
