from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Avg, F, ExpressionWrapper, DurationField, Count, Q
from datetime import timedelta

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import KYCSubmission, KYCDocument, KYCState, NotificationEvent
from .serializers import (
    RegisterSerializer, UserSerializer,
    KYCSubmissionListSerializer, KYCSubmissionDetailSerializer,
    KYCDocumentSerializer, StateTransitionSerializer,
    NotificationEventSerializer,
)
from .permissions import IsMerchant, IsReviewer, IsOwnerOrReviewer


# ─────────────────────────────────────────────
#  AUTH ENDPOINTS
# ─────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': UserSerializer(user).data,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    from django.contrib.auth import authenticate
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()

    user = authenticate(username=username, password=password)
    if not user:
        return Response(
            {'error': True, 'message': 'Invalid credentials.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': UserSerializer(user).data,
    })


@api_view(['GET'])
def me(request):
    return Response(UserSerializer(request.user).data)


# ─────────────────────────────────────────────
#  MERCHANT: KYC SUBMISSION CRUD
# ─────────────────────────────────────────────

class MerchantSubmissionListCreate(generics.ListCreateAPIView):
    """
    GET  /api/v1/submissions/           → merchant's own submissions
    POST /api/v1/submissions/           → create new draft submission
    """
    permission_classes = [IsAuthenticated, IsMerchant]
    serializer_class = KYCSubmissionDetailSerializer

    def get_queryset(self):
        # Merchant only sees their OWN submissions — enforced at queryset level
        return KYCSubmission.objects.filter(merchant=self.request.user)

    def perform_create(self, serializer):
        serializer.save(merchant=self.request.user)


class MerchantSubmissionDetail(generics.RetrieveUpdateAPIView):
    """
    GET   /api/v1/submissions/<id>/     → view own submission
    PATCH /api/v1/submissions/<id>/     → update draft fields
    """
    permission_classes = [IsAuthenticated, IsOwnerOrReviewer]
    serializer_class = KYCSubmissionDetailSerializer

    def get_queryset(self):
        return KYCSubmission.objects.filter(merchant=self.request.user)

    def get_object(self):
        obj = KYCSubmission.objects.get(pk=self.kwargs['pk'])
        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, request, *args, **kwargs):
        submission = self.get_object()
        # Merchants can only edit in draft or more_info_requested states
        if submission.state not in (KYCState.DRAFT, KYCState.MORE_INFO):
            return Response(
                {'error': True, 'message': f"Cannot edit a submission in state '{submission.state}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMerchant])
def merchant_submit(request, pk):
    """
    POST /api/v1/submissions/<id>/submit/
    Moves submission from draft → submitted.
    """
    try:
        submission = KYCSubmission.objects.get(pk=pk, merchant=request.user)
    except KYCSubmission.DoesNotExist:
        return Response({'error': True, 'message': 'Submission not found.'}, status=404)

    try:
        submission.transition_to(KYCState.SUBMITTED)
    except ValueError as e:
        return Response({'error': True, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(KYCSubmissionDetailSerializer(submission).data)


# ─────────────────────────────────────────────
#  DOCUMENT UPLOAD
# ─────────────────────────────────────────────

@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated, IsMerchant])
def upload_document(request, pk, doc_type):
    """
    POST   /api/v1/submissions/<id>/documents/<doc_type>/  → upload
    DELETE /api/v1/submissions/<id>/documents/<doc_type>/  → remove
    """
    try:
        submission = KYCSubmission.objects.get(pk=pk, merchant=request.user)
    except KYCSubmission.DoesNotExist:
        return Response({'error': True, 'message': 'Submission not found.'}, status=404)

    if submission.state not in (KYCState.DRAFT, KYCState.MORE_INFO):
        return Response(
            {'error': True, 'message': 'Documents can only be uploaded in draft or more_info_requested state.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    valid_doc_types = ['pan', 'aadhaar', 'bank_statement']
    if doc_type not in valid_doc_types:
        return Response(
            {'error': True, 'message': f"Invalid doc_type. Choose from: {valid_doc_types}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == 'DELETE':
        deleted, _ = KYCDocument.objects.filter(submission=submission, doc_type=doc_type).delete()
        if deleted:
            return Response({'message': f'{doc_type} document removed.'})
        return Response({'error': True, 'message': 'Document not found.'}, status=404)

    # POST: upload
    file = request.FILES.get('file')
    if not file:
        return Response({'error': True, 'message': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = KYCDocumentSerializer(data={'doc_type': doc_type, 'file': file})
    serializer.is_valid(raise_exception=True)

    # Upsert: replace existing doc of same type
    KYCDocument.objects.filter(submission=submission, doc_type=doc_type).delete()
    serializer.save(submission=submission)

    return Response(serializer.data, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────
#  REVIEWER: QUEUE + ACTIONS
# ─────────────────────────────────────────────

class ReviewerQueue(generics.ListAPIView):
    """
    GET /api/v1/reviewer/queue/
    Returns all submissions in submitted/under_review/more_info_requested,
    oldest first, with SLA flag computed dynamically.
    """
    permission_classes = [IsAuthenticated, IsReviewer]
    serializer_class = KYCSubmissionListSerializer

    def get_queryset(self):
        # The queue: active (non-terminal) submissions, oldest first
        return KYCSubmission.objects.filter(
            state__in=[KYCState.SUBMITTED, KYCState.UNDER_REVIEW, KYCState.MORE_INFO]
        ).select_related('merchant').order_by('created_at')


class ReviewerSubmissionDetail(generics.RetrieveAPIView):
    """
    GET /api/v1/reviewer/submissions/<id>/
    Reviewer sees full detail of any submission.
    """
    permission_classes = [IsAuthenticated, IsReviewer]
    serializer_class = KYCSubmissionDetailSerializer
    queryset = KYCSubmission.objects.all()


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsReviewer])
def reviewer_transition(request, pk):
    """
    POST /api/v1/reviewer/submissions/<id>/transition/
    Body: { "new_state": "approved", "reviewer_note": "Looks good" }
    """
    try:
        submission = KYCSubmission.objects.get(pk=pk)
    except KYCSubmission.DoesNotExist:
        return Response({'error': True, 'message': 'Submission not found.'}, status=404)

    serializer = StateTransitionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    new_state = serializer.validated_data['new_state']
    note = serializer.validated_data.get('reviewer_note', '')

    try:
        submission.transition_to(new_state, reviewer_note=note, actor=request.user)
    except ValueError as e:
        return Response({'error': True, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(KYCSubmissionDetailSerializer(submission).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsReviewer])
def reviewer_dashboard_metrics(request):
    """
    GET /api/v1/reviewer/metrics/

    Returns:
    - submissions_in_queue (count)
    - average_time_in_queue_hours (for currently queued items)
    - approval_rate_last_7_days (%)
    - at_risk_count
    """
    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)

    # All queued submissions
    queued = KYCSubmission.objects.filter(
        state__in=[KYCState.SUBMITTED, KYCState.UNDER_REVIEW, KYCState.MORE_INFO]
    )
    queue_count = queued.count()

    # Average time in queue (hours) — computed in Python to keep it simple + portable
    avg_hours = None
    if queue_count > 0:
        total_seconds = sum(
            (now - (s.submitted_at or s.created_at)).total_seconds()
            for s in queued
        )
        avg_hours = round(total_seconds / queue_count / 3600, 1)

    # Approval rate over last 7 days
    resolved = KYCSubmission.objects.filter(
        state__in=[KYCState.APPROVED, KYCState.REJECTED],
        updated_at__gte=seven_days_ago,
    )
    total_resolved = resolved.count()
    approved_count = resolved.filter(state=KYCState.APPROVED).count()
    approval_rate = round(approved_count / total_resolved * 100, 1) if total_resolved else None

    # SLA at risk — computed dynamically
    at_risk = sum(1 for s in queued if s.is_sla_at_risk)

    return Response({
        'submissions_in_queue': queue_count,
        'average_time_in_queue_hours': avg_hours,
        'approval_rate_last_7_days_pct': approval_rate,
        'at_risk_count': at_risk,
    })


# ─────────────────────────────────────────────
#  NOTIFICATIONS (read-only, merchant sees own)
# ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_notifications(request):
    events = NotificationEvent.objects.filter(merchant=request.user)[:50]
    return Response(NotificationEventSerializer(events, many=True).data)
