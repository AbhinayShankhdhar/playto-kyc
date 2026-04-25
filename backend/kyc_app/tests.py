"""
Tests for the Playto KYC Pipeline.
Run: python manage.py test kyc_app
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from kyc_app.models import KYCSubmission, KYCState, UserProfile


def make_user(username, role):
    user = User.objects.create_user(username=username, password='testpass123')
    UserProfile.objects.create(user=user, role=role)
    return user


def auth_client(user):
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return client


# ─────────────────────────────────────────────
#  STATE MACHINE UNIT TESTS
# ─────────────────────────────────────────────

class StateMachineUnitTests(TestCase):

    def test_legal_draft_to_submitted(self):
        self.assertTrue(KYCState.can_transition('draft', 'submitted'))

    def test_legal_submitted_to_under_review(self):
        self.assertTrue(KYCState.can_transition('submitted', 'under_review'))

    def test_legal_under_review_to_approved(self):
        self.assertTrue(KYCState.can_transition('under_review', 'approved'))

    def test_legal_under_review_to_rejected(self):
        self.assertTrue(KYCState.can_transition('under_review', 'rejected'))

    def test_legal_under_review_to_more_info(self):
        self.assertTrue(KYCState.can_transition('under_review', 'more_info_requested'))

    def test_legal_more_info_back_to_submitted(self):
        self.assertTrue(KYCState.can_transition('more_info_requested', 'submitted'))

    # ILLEGAL transitions
    def test_illegal_approved_to_draft(self):
        self.assertFalse(KYCState.can_transition('approved', 'draft'))

    def test_illegal_approved_to_submitted(self):
        self.assertFalse(KYCState.can_transition('approved', 'submitted'))

    def test_illegal_rejected_to_approved(self):
        self.assertFalse(KYCState.can_transition('rejected', 'approved'))

    def test_illegal_draft_to_approved_skip(self):
        self.assertFalse(KYCState.can_transition('draft', 'approved'))

    def test_validate_transition_raises_on_illegal(self):
        with self.assertRaises(ValueError) as ctx:
            KYCState.validate_transition('approved', 'draft')
        self.assertIn('approved', str(ctx.exception))
        self.assertIn('draft', str(ctx.exception))


# ─────────────────────────────────────────────
#  API: ILLEGAL TRANSITION → 400
# ─────────────────────────────────────────────

class IllegalTransitionAPITest(TestCase):
    """
    Core test: reviewer tries to approve an already-approved submission → 400.
    """

    def setUp(self):
        self.reviewer = make_user('reviewer', 'reviewer')
        self.merchant = make_user('merchant', 'merchant')
        self.client = auth_client(self.reviewer)

        self.submission = KYCSubmission.objects.create(
            merchant=self.merchant,
            state=KYCState.APPROVED,
            full_name='Test User',
        )

    def test_approve_already_approved_returns_400(self):
        url = f'/api/v1/reviewer/submissions/{self.submission.pk}/transition/'
        resp = self.client.post(url, {'new_state': 'approved'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)
        self.assertIn('approved', resp.data['message'])

    def test_approved_to_draft_returns_400(self):
        url = f'/api/v1/reviewer/submissions/{self.submission.pk}/transition/'
        resp = self.client.post(url, {'new_state': 'draft'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_rejected_to_approved_returns_400(self):
        self.submission.state = KYCState.REJECTED
        self.submission.save()
        url = f'/api/v1/reviewer/submissions/{self.submission.pk}/transition/'
        resp = self.client.post(url, {'new_state': 'approved'}, format='json')
        self.assertEqual(resp.status_code, 400)


# ─────────────────────────────────────────────
#  API: MERCHANT ISOLATION
# ─────────────────────────────────────────────

class MerchantIsolationTest(TestCase):
    """
    Merchant A cannot access Merchant B's submission.
    """

    def setUp(self):
        self.merchant_a = make_user('merchant_a', 'merchant')
        self.merchant_b = make_user('merchant_b', 'merchant')

        self.sub_b = KYCSubmission.objects.create(
            merchant=self.merchant_b,
            state=KYCState.DRAFT,
        )

    def test_merchant_a_cannot_see_merchant_b_submission(self):
        client = auth_client(self.merchant_a)
        resp = client.get(f'/api/v1/submissions/{self.sub_b.pk}/')
        # Should be 403 (permission denied) or 404 (not in queryset)
        self.assertIn(resp.status_code, [403, 404])

    def test_merchant_a_cannot_submit_merchant_b_submission(self):
        client = auth_client(self.merchant_a)
        resp = client.post(f'/api/v1/submissions/{self.sub_b.pk}/submit/')
        self.assertIn(resp.status_code, [403, 404])


# ─────────────────────────────────────────────
#  API: LEGAL TRANSITION FLOW
# ─────────────────────────────────────────────

class FullFlowTest(TestCase):

    def setUp(self):
        self.merchant = make_user('merchant', 'merchant')
        self.reviewer = make_user('reviewer', 'reviewer')
        self.merchant_client = auth_client(self.merchant)
        self.reviewer_client = auth_client(self.reviewer)

    def test_full_kyc_flow(self):
        # 1. Create draft
        resp = self.merchant_client.post('/api/v1/submissions/', {
            'full_name': 'Test User',
            'email': 'test@example.com',
            'phone': '9999999999',
            'business_name': 'Test Co',
            'business_type': 'agency',
            'monthly_volume_usd': '1000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        sub_id = resp.data['id']
        self.assertEqual(resp.data['state'], 'draft')

        # 2. Submit
        resp = self.merchant_client.post(f'/api/v1/submissions/{sub_id}/submit/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['state'], 'submitted')

        # 3. Reviewer moves to under_review
        resp = self.reviewer_client.post(
            f'/api/v1/reviewer/submissions/{sub_id}/transition/',
            {'new_state': 'under_review'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['state'], 'under_review')

        # 4. Reviewer approves
        resp = self.reviewer_client.post(
            f'/api/v1/reviewer/submissions/{sub_id}/transition/',
            {'new_state': 'approved', 'reviewer_note': 'All good!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['state'], 'approved')
