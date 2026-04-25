import os
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from .models import KYCSubmission, KYCDocument, NotificationEvent, UserProfile
from django.contrib.auth.models import User


# ─────────────────────────────────────────────
#  FILE VALIDATION  (server-side, never trust client)
# ─────────────────────────────────────────────

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
ALLOWED_MIME_TYPES = {'application/pdf', 'image/jpeg', 'image/png'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_kyc_file(file):
    """
    Validates uploaded file for:
    1. Extension (whitelist only — attacker cannot rename .exe to .pdf)
    2. Size (max 5 MB)
    3. MIME type from the actual file object
    """
    # 1. Check extension
    _, ext = os.path.splitext(file.name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise serializers.ValidationError(
            f"File type '{ext}' is not allowed. Accepted: PDF, JPG, PNG."
        )

    # 2. Check size
    if file.size > MAX_FILE_SIZE:
        size_mb = file.size / (1024 * 1024)
        raise serializers.ValidationError(
            f"File size {size_mb:.1f} MB exceeds the 5 MB limit."
        )

    # 3. Check content_type (sent by client but we still enforce it server-side
    #    as a secondary check; the extension check above is the hard gate)
    content_type = getattr(file, 'content_type', '')
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise serializers.ValidationError(
            f"MIME type '{content_type}' is not allowed."
        )

    return file


# ─────────────────────────────────────────────
#  AUTH SERIALIZERS
# ─────────────────────────────────────────────

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.ChoiceField(choices=['merchant', 'reviewer'], default='merchant')

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role']

    def create(self, validated_data):
        role = validated_data.pop('role', 'merchant')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        UserProfile.objects.create(user=user, role=role)
        return user


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']

    def get_role(self, obj):
        try:
            return obj.profile.role
        except UserProfile.DoesNotExist:
            return 'merchant'


# ─────────────────────────────────────────────
#  DOCUMENT SERIALIZER
# ─────────────────────────────────────────────

class KYCDocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField()

    class Meta:
        model = KYCDocument
        fields = ['id', 'doc_type', 'file', 'original_filename', 'file_size', 'uploaded_at']
        read_only_fields = ['original_filename', 'file_size', 'uploaded_at']

    def validate_file(self, value):
        return validate_kyc_file(value)

    def create(self, validated_data):
        validated_data['original_filename'] = validated_data['file'].name
        validated_data['file_size'] = validated_data['file'].size
        return super().create(validated_data)


# ─────────────────────────────────────────────
#  KYC SUBMISSION SERIALIZERS
# ─────────────────────────────────────────────

class KYCSubmissionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    merchant_username = serializers.CharField(source='merchant.username', read_only=True)
    is_sla_at_risk = serializers.SerializerMethodField()

    class Meta:
        model = KYCSubmission
        fields = [
            'id', 'merchant_username', 'state',
            'business_name', 'submitted_at', 'updated_at',
            'is_sla_at_risk',
        ]

    def get_is_sla_at_risk(self, obj):
        return obj.is_sla_at_risk


class KYCSubmissionDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail/create/update views."""
    documents = KYCDocumentSerializer(many=True, read_only=True)
    merchant_username = serializers.CharField(source='merchant.username', read_only=True)
    reviewer_username = serializers.CharField(source='reviewer.username', read_only=True, default=None)
    is_sla_at_risk = serializers.SerializerMethodField()

    class Meta:
        model = KYCSubmission
        fields = [
            'id', 'merchant_username', 'reviewer_username',
            'state', 'reviewer_note',
            'full_name', 'email', 'phone',
            'business_name', 'business_type', 'monthly_volume_usd',
            'documents',
            'created_at', 'submitted_at', 'updated_at',
            'is_sla_at_risk',
        ]
        read_only_fields = [
            'state', 'reviewer_note', 'merchant_username',
            'reviewer_username', 'created_at', 'submitted_at',
            'updated_at', 'is_sla_at_risk',
        ]

    def get_is_sla_at_risk(self, obj):
        return obj.is_sla_at_risk


class StateTransitionSerializer(serializers.Serializer):
    """Used by reviewer to change state."""
    new_state = serializers.CharField()
    reviewer_note = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_new_state(self, value):
        from .models import KYCState
        valid_states = [s for s, _ in KYCState.CHOICES]
        if value not in valid_states:
            raise serializers.ValidationError(
                f"'{value}' is not a valid state. Choose from: {valid_states}"
            )
        return value


# ─────────────────────────────────────────────
#  NOTIFICATION SERIALIZER
# ─────────────────────────────────────────────

class NotificationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationEvent
        fields = ['id', 'event_type', 'timestamp', 'payload', 'submission']
