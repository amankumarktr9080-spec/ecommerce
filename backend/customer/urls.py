from django.contrib.auth.decorators import login_required
from django.urls import path
from . import views

app_name = "customer"

urlpatterns = [

    # Dashboard
    path("dashboard/", login_required(views.dashboard, login_url='/auth/login/'), name="dashboard"),

    # Products
    path("products/", views.products, name="products"),
    path("product/<int:product_id>/", views.product_details, name="product_detail_view"),
    path("product-details/<int:product_id>/", views.product_details, name="product_details"),
    path("orders/<int:order_id>/invoice/", login_required(views.order_invoice, login_url='/auth/login/'), name="order_invoice"),

    # Categories
    path("categories/", views.categories, name="categories"),
    path("categories/<int:category_id>/", views.category_products, name="category_products"),

    # Search
    path("search/", views.search, name="search"),

    # Cart
    path("cart/", views.cart, name="cart"),

    # Wishlist
    path("wishlist/", views.wishlist, name="wishlist"),

    # Compare
    path("compare/", views.compare, name="compare"),

    # Checkout
    path("checkout/", login_required(views.checkout, login_url='/auth/login/'), name="checkout"),

    # Payment
    path("payment/", login_required(views.payment, login_url='/auth/login/'), name="payment"),
    path("payment/success/", login_required(views.payment_success, login_url='/auth/login/'), name="payment_success"),
    path("payment/failed/", login_required(views.payment_failed, login_url='/auth/login/'), name="payment_failed"),
    path("razorpay/create-order/", login_required(views.razorpay_create_order, login_url='/auth/login/'), name="razorpay_create_order"),
    path("razorpay/verify-payment/", login_required(views.razorpay_verify_payment, login_url='/auth/login/'), name="razorpay_verify_payment"),

    # Orders
    path("orders/", login_required(views.orders, login_url='/auth/login/'), name="orders"),
    path("orders/<int:order_id>/", login_required(views.order_details, login_url='/auth/login/'), name="order_details"),
    path("orders/<int:order_id>/track/", login_required(views.track_order, login_url='/auth/login/'), name="track_order"),
    path("track-order/", login_required(views.track_order, login_url='/auth/login/'), name="track_order_default"),

    # Returns / Refunds
    path("returns/", login_required(views.returns, login_url='/auth/login/'), name="returns"),
    path("refunds/", login_required(views.refunds, login_url='/auth/login/'), name="refunds"),

    # Reviews
    path("reviews/", login_required(views.reviews, login_url='/auth/login/'), name="reviews"),
    path("reports/", login_required(views.reports, login_url='/auth/login/'), name="reports"),

    # Coupons
    path("coupons/", login_required(views.coupons, login_url='/auth/login/'), name="coupons"),

    # Notifications
    path("notifications/", login_required(views.notifications, login_url='/auth/login/'), name="notifications"),

    # Payment History
    path("payments/", login_required(views.payments, login_url='/auth/login/'), name="payments"),

    # Profile
    path("profile/", login_required(views.profile, login_url='/auth/login/'), name="profile"),

    # Addresses
    path("addresses/", login_required(views.addresses, login_url='/auth/login/'), name="addresses"),

    # Rewards
    path("rewards/", login_required(views.rewards, login_url='/auth/login/'), name="rewards"),

    # Support
    path("support/", login_required(views.support, login_url='/auth/login/'), name="support"),

    # Settings
    path("settings/", login_required(views.settings, login_url='/auth/login/'), name="settings"),
]