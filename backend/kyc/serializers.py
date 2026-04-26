import os
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import KYCSubmission, KYCState, NotificationEvent, UserProfile


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField(required=False, default='')
    role = serializers.ChoiceField(choices=['merchant', 'reviewer'], default='merchant')

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value

    def create(self, validated_data):
        role = validated_data.pop('role', 'merchant')
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            email=validated_data.get('email', ''),
        )
        UserProfile.objects.create(user=user, role=role)
        return user


class DocumentField(serializers.FileField):
    """Validates file type and size. Does NOT trust client Content-Type."""
    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
    MAX_SIZE = 5 * 1024 * 1024  # 5 MB

    def to_internal_value(self, data):
        file = super().to_internal_value(data)
        # Check extension
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Unsupported file extension '{ext}'. Accepted: {sorted(self.ALLOWED_EXTENSIONS)}"
            )
        # Check size
        if file.size > self.MAX_SIZE:
            mb = file.size / (1024 * 1024)
            raise serializers.ValidationError(
                f"File '{file.name}' is {mb:.1f} MB. Maximum allowed size is 5 MB."
            )
        return file


class KYCSubmissionSerializer(serializers.ModelSerializer):
    pan_document = DocumentField(required=False, allow_null=True)
    aadhaar_document = DocumentField(required=False, allow_null=True)
    bank_statement = DocumentField(required=False, allow_null=True)
    is_at_risk = serializers.SerializerMethodField()
    merchant_username = serializers.CharField(source='merchant.username', read_only=True)
    reviewer_username = serializers.CharField(source='reviewer.username', read_only=True, allow_null=True)

    class Meta:
        model = KYCSubmission
        fields = [
            'id', 'state', 'merchant_username', 'reviewer_username',
            'full_name', 'email', 'phone',
            'business_name', 'business_type', 'expected_monthly_volume',
            'pan_document', 'aadhaar_document', 'bank_statement',
            'reviewer_notes', 'is_at_risk',
            'created_at', 'updated_at', 'submitted_at',
        ]
        read_only_fields = ['id', 'state', 'merchant_username', 'reviewer_username',
                            'is_at_risk', 'created_at', 'updated_at', 'submitted_at']

    def get_is_at_risk(self, obj):
        return obj.is_at_risk


class StateTransitionSerializer(serializers.Serializer):
    new_state = serializers.ChoiceField(choices=[s[0] for s in KYCState.CHOICES])
    reason = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        submission = self.context['submission']
        new_state = data['new_state']
        if not KYCState.can_transition(submission.state, new_state):
            allowed = KYCState.LEGAL_TRANSITIONS.get(submission.state, [])
            raise serializers.ValidationError({
                'new_state': (
                    f"Cannot transition from '{submission.state}' to '{new_state}'. "
                    f"Allowed transitions from '{submission.state}': {allowed or ['none']}"
                )
            })
        return data


class NotificationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationEvent
        fields = ['id', 'event_type', 'timestamp', 'payload', 'submission']
