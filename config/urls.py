from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "SmartSupport AI"
admin.site.site_title = "SmartSupport AI"
admin.site.index_title = "Customer support dashboard"

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/whatsapp/", include("apps.whatsapp.urls")),
    path("api/", include("apps.chat.urls")),
]
