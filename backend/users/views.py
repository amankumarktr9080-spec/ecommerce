import uuid
import requests
from urllib.parse import urlencode
from django.conf import settings
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import User, Address


def _is_account_suspended(user):
    if not user.is_active:
        return True
    if user.role == 'seller':
        profile = getattr(user, 'seller_profile', None)
        return profile is not None and not profile.is_approved
    if user.role == 'delivery':
        profile = getattr(user, 'delivery_profile', None)
        return profile is not None and not profile.is_approved
    return False


def login_view(request):
    if request.user.is_authenticated:
        if _is_account_suspended(request.user):
            logout(request)
            messages.error(request, "Your account is suspended.")
            return redirect('/auth/login/')
        if request.user.role == 'seller':
            seller_profile = getattr(request.user, 'seller_profile', None)
            if seller_profile is None:
                logout(request)
                messages.error(request, "Your seller account is pending admin approval. Please wait for approval before logging in.")
                return redirect('/auth/login/')
        elif request.user.role == 'delivery':
            delivery_profile = getattr(request.user, 'delivery_profile', None)
            if delivery_profile is None:
                logout(request)
                messages.error(request, "Your delivery partner account is pending admin approval. Please wait for approval before logging in.")
                return redirect('/auth/login/')
        return redirect_user_by_role(request.user)

    if request.method == "POST":
        username_or_email = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        if "@" in username_or_email:
            matched_user = User.objects.filter(email__iexact=username_or_email).first()
        else:
            matched_user = User.objects.filter(username=username_or_email).first()

        if matched_user and matched_user.check_password(password) and _is_account_suspended(matched_user):
            messages.error(request, "Your account is suspended.")
            return redirect('/auth/login/')

        # Allow login via username or email
        user = None
        if "@" in username_or_email:
            if matched_user:
                user = authenticate(request, username=matched_user.username, password=password)
        else:
            user = authenticate(request, username=username_or_email, password=password)

        if user is not None:
            if user.role == 'seller':
                seller_profile = getattr(user, 'seller_profile', None)
                if seller_profile is None:
                    messages.error(request, "Your seller account is pending admin approval. Please wait for approval before logging in.")
                    logout(request)
                    return redirect('/auth/login/')
            elif user.role == 'delivery':
                delivery_profile = getattr(user, 'delivery_profile', None)
                if delivery_profile is None:
                    messages.error(request, "Your delivery partner account is pending admin approval. Please wait for approval before logging in.")
                    logout(request)
                    return redirect('/auth/login/')

            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return redirect_user_by_role(user)
        else:
            messages.error(request, "Invalid username/email or password.")

    return render(request, "auth/login.html")


def google_login(request):
    """Start a real Google OAuth 2.0 authorization flow."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        messages.error(request, 'Google login is not configured yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env.')
        return redirect('/auth/login/')

    redirect_uri = settings.GOOGLE_REDIRECT_URI or request.build_absolute_uri(reverse('users:google_callback'))
    state = uuid.uuid4().hex
    request.session['google_oauth_state'] = state
    params = urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    })
    return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?{params}')


def google_callback(request):
    """Exchange Google's authorization code and sign in the verified profile."""
    if request.GET.get('state') != request.session.pop('google_oauth_state', None):
        messages.error(request, 'Google login session expired. Please try again.')
        return redirect('/auth/login/')

    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Google login was cancelled.')
        return redirect('/auth/login/')

    try:
        redirect_uri = settings.GOOGLE_REDIRECT_URI or request.build_absolute_uri(reverse('users:google_callback'))
        token_response = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
            timeout=10,
        )
        token_response.raise_for_status()
        access_token = token_response.json()['access_token']
        profile_response = requests.get(
            'https://openidconnect.googleapis.com/v1/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    except (requests.RequestException, KeyError, ValueError):
        messages.error(request, 'Google login could not be verified. Please try again.')
        return redirect('/auth/login/')

    email = profile.get('email', '').strip().lower()
    if not email or not profile.get('email_verified', False):
        messages.error(request, 'Google did not return a verified email address.')
        return redirect('/auth/login/')

    username_base = email.split('@')[0].replace('.', '_').lower()
    username = username_base
    suffix = 1
    while User.objects.filter(username=username).exclude(email__iexact=email).exists():
        suffix += 1
        username = f'{username_base}_{suffix}'

    first_name = profile.get('given_name', '').strip()
    last_name = profile.get('family_name', '').strip()
    user = User.objects.filter(email__iexact=email).order_by('id').first()
    created = user is None
    if user is not None and _is_account_suspended(user):
        messages.error(request, "Your account is suspended.")
        return redirect('/auth/login/')

    if created:
        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='customer',
            wallet_balance=2000.00,
            avatar_url=profile.get('picture', ''),
        )
    if not created:
        changed = []
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed.append('first_name')
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            changed.append('last_name')
        if profile.get('picture') and user.avatar_url != profile['picture']:
            user.avatar_url = profile['picture']
            changed.append('avatar_url')
        if changed:
            user.save(update_fields=changed)

    if created:
        Address.objects.create(
            user=user,
            full_name=f'{first_name} {last_name}'.strip() or email,
            phone='9876543210',
            street_address='Add your delivery address',
            city='New Delhi',
            state='Delhi',
            pincode='110001',
            is_default=True,
        )

    login(request, user)
    messages.success(request, f"Signed in as {user.get_full_name() or user.username}!")
    return redirect('/customer/dashboard/')


def register(request):
    """Public Registration is for CUSTOMERS only. Sellers and Riders are onboarded by Admin."""
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        referral_code = request.POST.get("referral_code", "").strip()
        password = request.POST.get("password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()
        referrer = None

        if referral_code:
            referrer = User.objects.filter(
                referral_code__iexact=referral_code,
                role='customer',
            ).first()
            if not referrer:
                messages.error(request, "Invalid referral code.")
                return render(request, "auth/register.html")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "auth/register.html")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return render(request, "auth/register.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered.")
            return render(request, "auth/register.html")

        # Create Customer
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role="customer",
            wallet_balance=2000.00,
            referral_code=f"REF-{username[:4].upper()}100",
            referred_by=referrer,
            avatar_url=f"https://api.dicebear.com/7.x/avataaars/svg?seed={username}"
        )

        if referrer:
            referrer.wallet_balance += 200
            referrer.save(update_fields=['wallet_balance'])

        # Create starter address
        Address.objects.create(
            user=user,
            full_name=f"{first_name} {last_name}".strip() or username,
            phone=phone or "9876543210",
            street_address="New Resident Block, Flat 101",
            city="New Delhi",
            state="Delhi",
            pincode="110001",
            is_default=True
        )

        login(request, user)
        message = "Registration successful! ₹2000.00 has been added to your wallet."
        if referrer:
            message += " Referral reward of ₹200 was credited to your referrer."
        messages.success(request, message)
        return redirect("/customer/dashboard/")

    return render(request, "auth/register.html")


def forgot_password(request):
    reset_link = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        user = User.objects.filter(username__iexact=username, email__iexact=email).first()
        if user:
            token = uuid.uuid4().hex
            user.reset_token = token
            user.reset_token_created_at = timezone.now()
            user.save()
            reset_link = f"/auth/reset-password/?token={token}"
            messages.success(request, f"Password reset link generated! Click below to reset your password.")
        else:
            messages.error(request, "No account found with this User ID and email combination.")

    return render(request, "auth/forgot-password.html", {"reset_link": reset_link})


def reset_password(request):
    token = request.GET.get("token") or request.POST.get("token")
    user = User.objects.filter(reset_token=token).first() if token else None

    if not user and request.method == "GET":
        messages.error(request, "Invalid or expired password reset link.")

    if request.method == "POST":
        new_password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        if user and new_password and new_password == confirm_password:
            user.set_password(new_password)
            user.reset_token = None
            user.save()
            messages.success(request, "Password has been successfully updated! Please log in.")
            return redirect("/auth/login/")
        else:
            messages.error(request, "Passwords do not match or token is invalid.")

    return render(request, "auth/reset-password.html", {"token": token, "valid_user": bool(user)})


@login_required(login_url='/auth/login/')
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
        elif len(new_password) < 6 or len(new_password) > 10:
            messages.error(request, 'New password must be between 6 and 10 characters long.')
        elif new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
        else:
            request.user.set_password(new_password)
            request.user.save(update_fields=['password'])
            logout(request)
            messages.success(request, 'Password changed successfully. Please log in again with your new password.')
            return redirect('/auth/login/')

    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or '/auth/login/')


def logout_view(request):
    logout(request)
    messages.info(request, "You have been safely logged out.")
    return redirect("/auth/login/")


def verify_otp(request):
    return render(request, "auth/otp-verification.html")


def redirect_user_by_role(user):
    """Smart role-based navigation router"""
    if user.is_superuser or user.role == "admin":
        return redirect("/admin-panel/dashboard/")
    elif user.role == "seller":
        return redirect("/seller/dashboard/")
    elif user.role == "delivery":
        return redirect("/delivery/dashboard/")
    else:
        return redirect("/customer/dashboard/")