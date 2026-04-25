"""
Seed script — creates test data for the Playto KYC demo.

Usage:
    cd backend
    python manage.py shell < seed.py
    # OR
    python seed.py  (if run from project root with DJANGO_SETTINGS_MODULE set)
"""

import os
import sys
import django

# Allow running directly: python seed.py
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(__file__))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kyc_project.settings')
    django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from kyc_app.models import KYCSubmission, KYCState, UserProfile


def create_user(username, password, email, role):
    user, created = User.objects.get_or_create(username=username)
    user.set_password(password)
    user.email = email
    user.save()
    UserProfile.objects.get_or_create(user=user, defaults={'role': role})
    # Fix role if user already existed
    profile = user.profile
    profile.role = role
    profile.save()
    token, _ = Token.objects.get_or_create(user=user)
    print(f"  {'Created' if created else 'Updated'}: {role} '{username}' | token: {token.key}")
    return user


print("\n=== Playto KYC Seed Script ===\n")

# 1. Reviewer
reviewer = create_user('reviewer1', 'reviewer123', 'reviewer@playto.so', 'reviewer')

# 2. Merchant A — submission in DRAFT
merchant_a = create_user('merchant_draft', 'merchant123', 'draft@example.com', 'merchant')
sub_a, _ = KYCSubmission.objects.get_or_create(
    merchant=merchant_a,
    defaults={
        'full_name': 'Rahul Sharma',
        'email': 'rahul@example.com',
        'phone': '+91-9876543210',
        'business_name': 'Sharma Digital Agency',
        'business_type': 'agency',
        'monthly_volume_usd': 5000,
        'state': KYCState.DRAFT,
    }
)
print(f"  Submission #{sub_a.pk}: merchant_draft → state={sub_a.state}")

# 3. Merchant B — submission in UNDER_REVIEW
merchant_b = create_user('merchant_review', 'merchant123', 'review@example.com', 'merchant')
from django.utils import timezone
sub_b, created_b = KYCSubmission.objects.get_or_create(
    merchant=merchant_b,
    defaults={
        'full_name': 'Priya Singh',
        'email': 'priya@example.com',
        'phone': '+91-9123456789',
        'business_name': 'Singh Freelance Studio',
        'business_type': 'freelancer',
        'monthly_volume_usd': 2000,
        'state': KYCState.UNDER_REVIEW,
        'submitted_at': timezone.now() - timezone.timedelta(hours=30),  # triggers SLA flag
        'reviewer': reviewer,
    }
)
if not created_b:
    sub_b.state = KYCState.UNDER_REVIEW
    sub_b.submitted_at = timezone.now() - timezone.timedelta(hours=30)
    sub_b.reviewer = reviewer
    sub_b.save()
print(f"  Submission #{sub_b.pk}: merchant_review → state={sub_b.state} (SLA at risk: {sub_b.is_sla_at_risk})")

print("\n=== Seed complete. Login credentials ===")
print("  Reviewer  → username: reviewer1      | password: reviewer123")
print("  Merchant1 → username: merchant_draft  | password: merchant123")
print("  Merchant2 → username: merchant_review | password: merchant123")
print()
