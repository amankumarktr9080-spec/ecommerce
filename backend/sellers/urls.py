from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

app_name = "seller"

urlpatterns = [
    path("", views.dashboard, name="dashboard_root"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("store/", views.store, name="store"),

    # Products
    path("products/", views.products, name="products"),
    path("products/add/", views.add_product, name="add_product"),
    path("products/<int:product_id>/", views.product_details, name="product_details"),
    path("products/<int:product_id>/edit/", views.edit_product, name="edit_product"),

    # Categories
    path("categories/", views.categories, name="categories"),

    # Inventory
    path("inventory/", views.inventory, name="inventory"),

    # Orders
    path("orders/", views.orders, name="orders"),
    path("orders/<int:order_id>/", views.order_details, name="order_details"),

    # Shipping
    path("shipping/", views.shipping, name="shipping"),

    # Returns & Refunds
    path("returns/", login_required(views.returns, login_url='/auth/login/'), name="returns"),
    path("refunds/", views.refunds, name="refunds"),

    # Earnings
    path("earnings/", views.earnings, name="earnings"),
    path("withdrawals/", views.withdrawals, name="withdrawals"),

    # Reviews & Offers
    path("reviews/", views.reviews, name="reviews"),
    path("offers/", views.offers, name="offers"),

    # Customers
    path("customers/", views.customers, name="customers"),
    path("reports/", views.reports, name="reports"),
    path("notifications/", views.notifications, name="notifications"),
    path("support/", views.support, name="support"),
    path("settings/", views.settings, name="settings"),
]