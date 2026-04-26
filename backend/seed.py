#!/usr/bin/env python
"""
Seed script — idempotent, safe to run on every deploy.
Creates: 2 merchants (draft + under_review) + 1 reviewer.
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from kyc.models import KYCSubmission, KYCState, UserProfile, NotificationEvent
from django.utils import timezone
from datetime import timedelta


def get_or_create_user(username, password, role, email=''):
    user, created = User.objects.get_or_create(username=username, defaults={'email': email})
    if created:
        user.set_password(password)
        user.save()
        UserProfile.objects.create(user=user, role=role)
        print(f"  Created {role}: {username}")
    else:
        print(f"  Exists  {role}: {username}")
    token, _ = Token.objects.get_or_create(user=user)
    return user, token


print("\n🌱 Seeding Playto KYC database...")

# ── Reviewer ──────────────────────────────────────────────────────────────
reviewer, r_tok = get_or_create_user(
    'reviewer1', 'reviewer123', 'reviewer', 'reviewer@playto.so'
)

# ── Merchant 1: DRAFT ────────────────────────────────────────────────────
m1, m1_tok = get_or_create_user(
    'merchant_arjun', 'merchant123', 'merchant', 'arjun@example.com'
)
if not KYCSubmission.objects.filter(merchant=m1).exists():
    KYCSubmission.objects.create(
        merchant=m1,
        state=KYCState.DRAFT,
        full_name='Arjun Sharma',
        email='arjun@example.com',
        phone='+91 98765 43210',
        business_name='Arjun Digital Studio',
        business_type='agency',
        expected_monthly_volume=5000.00,
    )
    print("  Created draft submission for merchant_arjun")

# ── Merchant 2: UNDER_REVIEW, AT RISK (30h old) ──────────────────────────
m2, m2_tok = get_or_create_user(
    'merchant_priya', 'merchant123', 'merchant', 'priya@example.com'
)
if not KYCSubmission.objects.filter(merchant=m2).exists():
    sub2 = KYCSubmission.objects.create(
        merchant=m2,
        state=KYCState.UNDER_REVIEW,
        full_name='Priya Mehta',
        email='priya@example.com',
        phone='+91 91234 56789',
        business_name='Priya Freelance Services',
        business_type='freelancer',
        expected_monthly_volume=2000.00,
        reviewer=reviewer,
        reviewer_notes='Initial review in progress.',
        submitted_at=timezone.now() - timedelta(hours=30),  # Triggers AT RISK flag
    )
    NotificationEvent.objects.create(
        merchant=m2,
        submission=sub2,
        event_type='state_changed_to_under_review',
        payload={
            'from_state': 'submitted',
            'to_state': 'under_review',
            'reason': '',
            'actor_id': reviewer.id,
        }
    )
    print("  Created under_review submission for merchant_priya (AT RISK)")

print(f"""
✅ Seed complete!

🔑 Login credentials:
   reviewer1 / reviewer123        → Reviewer dashboard
   merchant_arjun / merchant123   → Draft KYC (edit & submit)
   merchant_priya / merchant123   → Under review (SLA at risk ⚠️)

📊 Database:
   Users:       {User.objects.count()}
   Submissions: {KYCSubmission.objects.count()}
   Events:      {NotificationEvent.objects.count()}
""")
