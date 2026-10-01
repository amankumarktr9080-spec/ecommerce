from django.contrib import admin
from django.http import HttpResponseForbidden
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve


def serve_media(request, path):
    if path.startswith(('seller_kyc/', 'delivery_kyc/')):
        if not request.user.is_authenticated or request.user.role != 'admin':
            return HttpResponseForbidden()
    return serve(request, path, document_root=settings.MEDIA_ROOT)

urlpatterns = [
    path("django-admin/", admin.site.urls),

    path("", include("public.urls")),
    path("auth/", include("users.urls")),
    path("customer/", include("customer.urls")),
    path("seller/", include("sellers.urls")),
    path("delivery/", include("delivery.urls")),
    path("admin-panel/", include("admin_panel.urls")),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += [path('media/<path:path>', serve_media)]