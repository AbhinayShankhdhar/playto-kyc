from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q, Avg, F, ExpressionWrapper, DurationField
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.contrib.auth import authenticate

from .models import KYCSubmission, KYCState, NotificationEvent, UserProfile
from .serializers import (
    RegisterSerializer, KYCSubmissionSerializer,
    StateTransitionSerializer, NotificationEventSerializer
)
from .permissions import IsMerchant, IsReviewer, IsMerchantOrReviewer


def error_response(message, status_code=400, **extra):
    return Response({'error': message, **extra}, status=status_code)


class RegisterView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'Validation failed', 'details': serializer.errors}, status=400)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.id,
            'username': user.username,
            'role': user.profile.role,
        }, status=201)


class LoginView(APIView):
    permission_classes = []

    def post(self, request):
        username = request.data.get('username', '')
        password = request.data.get('password', '')
        user = authenticate(username=username, password=password)
        if not user:
            return error_response('Invalid credentials.', 401)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.id,
            'username': user.username,
            'role': user.profile.role,
        })


class MeView(APIView):
    def get(self, request):
        return Response({
            'user_id': request.user.id,
            'username': request.user.username,
            'role': request.user.profile.role,
        })


# ── Merchant Views ──────────────────────────────────────────────────────────

class MerchantSubmissionListView(APIView):
    permission_classes = [IsMerchant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        """Merchant sees ONLY their own submissions."""
        submissions = KYCSubmission.objects.filter(merchant=request.user)
        serializer = KYCSubmissionSerializer(submissions, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        """Create a new KYC submission (starts as draft)."""
        submission = KYCSubmission.objects.create(merchant=request.user)
        serializer = KYCSubmissionSerializer(
            submission, data=request.data, partial=True, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response({'error': 'Validation failed', 'details': serializer.errors}, status=400)


class MerchantSubmissionDetailView(APIView):
    permission_classes = [IsMerchant]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, pk, user):
        try:
            # Merchant can ONLY access their own submission
            return KYCSubmission.objects.get(pk=pk, merchant=user)
        except KYCSubmission.DoesNotExist:
            return None

    def get(self, request, pk):
        submission = self.get_object(pk, request.user)
        if not submission:
            return error_response('Submission not found.', 404)
        return Response(KYCSubmissionSerializer(submission, context={'request': request}).data)

    def patch(self, request, pk):
        submission = self.get_object(pk, request.user)
        if not submission:
            return error_response('Submission not found.', 404)
        if submission.state not in [KYCState.DRAFT, KYCState.MORE_INFO_REQUESTED]:
            return error_response(
                f"Cannot edit submission in state '{submission.state}'. "
                "You can only edit drafts or submissions where more info was requested."
            )
        serializer = KYCSubmissionSerializer(
            submission, data=request.data, partial=True, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response({'error': 'Validation failed', 'details': serializer.errors}, status=400)


class MerchantSubmitView(APIView):
    """Merchant submits their KYC (draft → submitted)."""
    permission_classes = [IsMerchant]

    def post(self, request, pk):
        try:
            submission = KYCSubmission.objects.get(pk=pk, merchant=request.user)
        except KYCSubmission.DoesNotExist:
            return error_response('Submission not found.', 404)

        try:
            submission.transition_to(KYCState.SUBMITTED, actor=request.user)
        except Exception as e:
            return error_response(str(e))

        return Response(KYCSubmissionSerializer(submission, context={'request': request}).data)


# ── Reviewer Views ───────────────────────────────────────────────────────────

class ReviewerQueueView(APIView):
    permission_classes = [IsReviewer]

    def get(self, request):
        """
        Queue: all non-draft, non-approved, non-rejected submissions, oldest first.
        SLA flag computed dynamically via Python property (no DB flag that goes stale).
        """
        submissions = KYCSubmission.objects.filter(
            state__in=[KYCState.SUBMITTED, KYCState.UNDER_REVIEW, KYCState.MORE_INFO_REQUESTED]
        ).select_related('merchant', 'reviewer').order_by('submitted_at', 'created_at')

        data = KYCSubmissionSerializer(submissions, many=True, context={'request': request}).data
        return Response(data)


class ReviewerAllSubmissionsView(APIView):
    permission_classes = [IsReviewer]

    def get(self, request):
        submissions = KYCSubmission.objects.all().select_related('merchant', 'reviewer')
        serializer = KYCSubmissionSerializer(submissions, many=True, context={'request': request})
        return Response(serializer.data)


class ReviewerSubmissionDetailView(APIView):
    permission_classes = [IsReviewer]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, pk):
        try:
            submission = KYCSubmission.objects.get(pk=pk)
        except KYCSubmission.DoesNotExist:
            return error_response('Submission not found.', 404)
        return Response(KYCSubmissionSerializer(submission, context={'request': request}).data)

    def patch(self, request, pk):
        """Reviewer can add notes."""
        try:
            submission = KYCSubmission.objects.get(pk=pk)
        except KYCSubmission.DoesNotExist:
            return error_response('Submission not found.', 404)
        notes = request.data.get('reviewer_notes', '')
        submission.reviewer_notes = notes
        submission.reviewer = request.user
        submission.save()
        return Response(KYCSubmissionSerializer(submission, context={'request': request}).data)


class ReviewerTransitionView(APIView):
    """Reviewer triggers state transitions."""
    permission_classes = [IsReviewer]

    def post(self, request, pk):
        try:
            submission = KYCSubmission.objects.get(pk=pk)
        except KYCSubmission.DoesNotExist:
            return error_response('Submission not found.', 404)

        serializer = StateTransitionSerializer(
            data=request.data, context={'submission': submission}
        )
        if not serializer.is_valid():
            return Response({'error': 'Invalid transition', 'details': serializer.errors}, status=400)

        new_state = serializer.validated_data['new_state']
        reason = serializer.validated_data.get('reason', '')

        # Assign reviewer if moving to under_review
        if new_state == KYCState.UNDER_REVIEW:
            submission.reviewer = request.user

        if reason:
            submission.reviewer_notes = reason

        try:
            submission.transition_to(new_state, actor=request.user, reason=reason)
        except Exception as e:
            return error_response(str(e))

        return Response(KYCSubmissionSerializer(submission, context={'request': request}).data)


class ReviewerDashboardMetricsView(APIView):
    permission_classes = [IsReviewer]

    def get(self, request):
        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)

        in_queue = KYCSubmission.objects.filter(
            state__in=[KYCState.SUBMITTED, KYCState.UNDER_REVIEW]
        ).count()

        # Average time in queue for currently queued items
        queued = KYCSubmission.objects.filter(
            state__in=[KYCState.SUBMITTED, KYCState.UNDER_REVIEW],
            submitted_at__isnull=False
        )
        avg_hours = None
        if queued.exists():
            durations = [(now - s.submitted_at).total_seconds() / 3600 for s in queued]
            avg_hours = round(sum(durations) / len(durations), 1)

        # Approval rate last 7 days
        recent = KYCSubmission.objects.filter(updated_at__gte=seven_days_ago)
        total_resolved = recent.filter(state__in=[KYCState.APPROVED, KYCState.REJECTED]).count()
        approved = recent.filter(state=KYCState.APPROVED).count()
        approval_rate = round((approved / total_resolved * 100) if total_resolved > 0 else 0, 1)

        at_risk_count = sum(1 for s in queued if s.is_at_risk)

        return Response({
            'in_queue': in_queue,
            'avg_hours_in_queue': avg_hours,
            'approval_rate_7d': approval_rate,
            'at_risk_count': at_risk_count,
            'total_submissions': KYCSubmission.objects.count(),
            'approved_total': KYCSubmission.objects.filter(state=KYCState.APPROVED).count(),
            'rejected_total': KYCSubmission.objects.filter(state=KYCState.REJECTED).count(),
        })


class NotificationListView(APIView):
    def get(self, request):
        if hasattr(request.user, 'profile') and request.user.profile.is_reviewer:
            events = NotificationEvent.objects.all()
        else:
            events = NotificationEvent.objects.filter(merchant=request.user)
        serializer = NotificationEventSerializer(events[:50], many=True)
        return Response(serializer.data)
