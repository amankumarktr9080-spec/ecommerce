from django.urls import path
from . import views

app_name = "delivery"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/", views.dashboard, name="dashboard_named"),
    path("toggle-duty/", views.toggle_duty, name="toggle_duty"),
    path("delivery-history/", views.delivery_history, name="delivery_history_named"),

    path(
        "active-delivery/",
        views.active_delivery,
        name="active_delivery",
    ),

    path(
    "active-delivery/<int:delivery_id>/",
    views.delivery_details,
    name="active_delivery_details",
),
    path("return-pickup/<int:return_id>/", views.return_pickup_details, name="return_pickup_details"),

    path("navigation/", views.navigation, name="navigation"),
    path("history/", views.delivery_history, name="history"),
    path("earnings/", views.earnings, name="earnings"),
    path("reports/", views.reports, name="reports"),
    path("incentives/", views.incentives, name="incentives"),
    path("ratings/", views.ratings, name="ratings"),
    path("notifications/", views.notifications, name="notifications"),
    path("profile/", views.profile, name="profile"),
    path("documents/", views.documents, name="documents"),
    path("bank/", views.bank, name="bank"),
    path("withdrawals/", views.withdrawals, name="withdrawals"),
    path("support/", views.support, name="support"),
    path("settings/", views.settings, name="settings"),
]