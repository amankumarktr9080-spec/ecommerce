from django.urls import path
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from functools import wraps
from . import views

app_name = "admin_panel"


def admin_only(view):
    @wraps(view)
    def check_admin_role(request, *args, **kwargs):
        if getattr(request.user, "role", None) != "admin":
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return login_required(check_admin_role, login_url="/auth/login/")

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/", views.dashboard, name="dashboard_named"),
    path("profile/", views.profile, name="profile"),
    path("search/", views.admin_search, name="search"),

    # Customers
    path("customers/", views.customers, name="customers"),
    path("customers/<int:customer_id>/", views.customer_details, name="customer_details"),
    path("customers/<int:customer_id>/toggle-block/", views.toggle_customer_block, name="toggle_customer_block"),

    # Sellers (Admin onboarding & approval)
    path("sellers/", views.sellers, name="sellers"),
    path("seller-applications/", views.seller_applications, name="seller_applications"),
    path("sellers/add/", views.add_seller, name="add_seller"),
    path("sellers/<int:seller_id>/", views.seller_details, name="seller_details"),
    path("sellers/<int:seller_id>/toggle-status/", views.toggle_seller_status, name="toggle_seller_status"),

    # Delivery Partners (Admin onboarding & approval)
    path("delivery-partners/", views.delivery_partners, name="delivery_partners"),
    path("delivery-applications/", views.delivery_applications, name="delivery_applications"),
    path("delivery-partners/add/", views.add_delivery_partner, name="add_delivery_partner"),
    path("delivery-partners/<int:partner_id>/", views.delivery_details, name="delivery_details"),
    path("delivery-partners/<int:partner_id>/toggle-status/", views.toggle_delivery_status, name="toggle_delivery_status"),

    # Products & Catalog
    path("products/", views.products, name="products"),
    path("products/<int:product_id>/", views.product_details, name="product_details"),
    path("products/<int:product_id>/toggle-status/", views.toggle_product_status, name="toggle_product_status"),

    path("categories/", views.categories, name="categories"),
    path("subcategories/", views.subcategories, name="subcategories"),
    path("brands/", views.brands, name="brands"),

    # Orders & Operations
    path("orders/", views.orders, name="orders"),
    path("orders/<int:order_id>/", views.order_details, name="order_details"),

    path("payments/", views.payments, name="payments"),
    path("payouts/", views.payouts, name="payouts"),
    path("commissions/", views.commissions, name="commissions"),

    path("returns/", login_required(views.returns, login_url='/auth/login/'), name="returns"),
    path("refunds/", login_required(views.refunds, login_url='/auth/login/'), name="refunds"),

    path("coupons/", views.coupons, name="coupons"),
    path("offers/", views.offers, name="offers"),
    path("banners/", views.banners, name="banners"),

    path("reviews/", views.reviews, name="reviews"),

    path("reports/", views.reports, name="reports"),
    path("reports/export/<str:report_type>/", views.export_report, name="export_report"),
    path("analytics/", views.analytics, name="analytics"),
    path("live-operations/", views.live_operations, name="live_operations"),

    path("support/", views.support, name="support"),
    path("notifications/", views.notifications, name="notifications"),
    path("tickets/", views.tickets, name="tickets"),

    path("admins/", views.admins, name="admins"),
    path("roles-permissions/", views.roles_permissions, name="roles_permissions"),

    path("ai-assistant/", views.ai_assistant, name="ai_assistant"),

    path("settings/", views.settings, name="settings"),
    path("marketplace-content/", views.marketplace_content, name="marketplace_content"),
]

for pattern in urlpatterns:
    pattern.callback = admin_only(pattern.callback)