from django.urls import path
from . import views

app_name = "public"

urlpatterns = [

    path("", views.home, name="home"),

    path(
        "about/",
        views.about,
        name="about"
    ),

    path(
        "contact/",
        views.contact,
        name="contact"
    ),

    path(
        "faq/",
        views.faq,
        name="faq"
    ),

    path(
        "help/",
        views.help_page,
        name="help"
    ),

    path(
        "privacy/",
        views.privacy,
        name="privacy"
    ),

    path(
        "terms/",
        views.terms,
        name="terms"
    ),

    path(
        "refund-policy/",
        views.refund_policy,
        name="refund_policy"
    ),

    path(
        "shipping-policy/",
        views.shipping_policy,
        name="shipping_policy"
    ),

    path(
        "cancellation-policy/",
        views.cancellation_policy,
        name="cancellation_policy"
    ),

    path(
        "seller-register/",
        views.seller_register,
        name="seller_register"
    ),

    path(
        "delivery-register/",
        views.delivery_register,
        name="delivery_register"
    ),

    path(
        "username-availability/",
        views.username_availability,
        name="username_availability"
    ),
]