from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from .models import KYCSubmission, KYCState, UserProfile


def create_user(username, role='merchant'):
    user = User.objects.create_user(username=username, password='testpass123')
    UserProfile.objects.create(user=user, role=role)
    return user


def get_token(user):
    token, _ = Token.objects.get_or_create(user=user)
    return token.key


class StateMachineTest(TestCase):
    def setUp(self):
        self.merchant = create_user('merchant1', 'merchant')
        self.reviewer = create_user('reviewer1', 'reviewer')

    def test_legal_transition_draft_to_submitted(self):
        sub = KYCSubmission.objects.create(merchant=self.merchant)
        self.assertEqual(sub.state, KYCState.DRAFT)
        sub.transition_to(KYCState.SUBMITTED)
        self.assertEqual(sub.state, KYCState.SUBMITTED)

    def test_illegal_transition_approved_to_draft(self):
        sub = KYCSubmission.objects.create(merchant=self.merchant, state=KYCState.APPROVED)
        with self.assertRaises(ValidationError):
            sub.transition_to(KYCState.DRAFT)

    def test_illegal_transition_draft_to_approved(self):
        sub = KYCSubmission.objects.create(merchant=self.merchant)
        with self.assertRaises(ValidationError):
            sub.transition_to(KYCState.APPROVED)

    def test_illegal_transition_submitted_to_rejected(self):
        """Must go through under_review before rejecting."""
        sub = KYCSubmission.objects.create(merchant=self.merchant, state=KYCState.SUBMITTED)
        with self.assertRaises(ValidationError):
            sub.transition_to(KYCState.REJECTED)

    def test_full_happy_path(self):
        sub = KYCSubmission.objects.create(merchant=self.merchant)
        sub.transition_to(KYCState.SUBMITTED)
        sub.transition_to(KYCState.UNDER_REVIEW)
        sub.transition_to(KYCState.APPROVED)
        self.assertEqual(sub.state, KYCState.APPROVED)

    def test_more_info_path(self):
        sub = KYCSubmission.objects.create(merchant=self.merchant)
        sub.transition_to(KYCState.SUBMITTED)
        sub.transition_to(KYCState.UNDER_REVIEW)
        sub.transition_to(KYCState.MORE_INFO_REQUESTED)
        sub.transition_to(KYCState.SUBMITTED)
        self.assertEqual(sub.state, KYCState.SUBMITTED)

    def test_illegal_more_info_to_approved(self):
        sub = KYCSubmission.objects.create(merchant=self.merchant, state=KYCState.MORE_INFO_REQUESTED)
        with self.assertRaises(ValidationError):
            sub.transition_to(KYCState.APPROVED)


class AuthorizationTest(TestCase):
    def setUp(self):
        self.merchant1 = create_user('merchant1', 'merchant')
        self.merchant2 = create_user('merchant2', 'merchant')
        self.reviewer = create_user('reviewer1', 'reviewer')
        self.client = APIClient()

    def test_merchant_cannot_see_other_merchants_submission(self):
        sub = KYCSubmission.objects.create(merchant=self.merchant1)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {get_token(self.merchant2)}')
        response = self.client.get(f'/api/v1/merchant/submissions/{sub.id}/')
        self.assertEqual(response.status_code, 404)

    def test_merchant_can_see_own_submission(self):
        sub = KYCSubmission.objects.create(merchant=self.merchant1)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {get_token(self.merchant1)}')
        response = self.client.get(f'/api/v1/merchant/submissions/{sub.id}/')
        self.assertEqual(response.status_code, 200)

    def test_reviewer_can_see_all_submissions(self):
        KYCSubmission.objects.create(merchant=self.merchant1)
        KYCSubmission.objects.create(merchant=self.merchant2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {get_token(self.reviewer)}')
        response = self.client.get('/api/v1/reviewer/submissions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_merchant_cannot_access_reviewer_endpoints(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {get_token(self.merchant1)}')
        response = self.client.get('/api/v1/reviewer/queue/')
        self.assertEqual(response.status_code, 403)


class APITransitionTest(TestCase):
    def setUp(self):
        self.merchant = create_user('merchant1', 'merchant')
        self.reviewer = create_user('reviewer1', 'reviewer')
        self.client = APIClient()

    def test_api_rejects_illegal_transition(self):
        sub = KYCSubmission.objects.create(merchant=self.merchant, state=KYCState.APPROVED)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {get_token(self.reviewer)}')
        response = self.client.post(
            f'/api/v1/reviewer/submissions/{sub.id}/transition/',
            {'new_state': 'draft'},
            format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
