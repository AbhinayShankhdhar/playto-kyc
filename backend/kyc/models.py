from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


class KYCState:
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    MORE_INFO_REQUESTED = 'more_info_requested'

    CHOICES = [
        (DRAFT, 'Draft'),
        (SUBMITTED, 'Submitted'),
        (UNDER_REVIEW, 'Under Review'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (MORE_INFO_REQUESTED, 'More Info Requested'),
    ]

    # THE STATE MACHINE - single source of truth
    LEGAL_TRANSITIONS = {
        DRAFT: [SUBMITTED],
        SUBMITTED: [UNDER_REVIEW],
        UNDER_REVIEW: [APPROVED, REJECTED, MORE_INFO_REQUESTED],
        MORE_INFO_REQUESTED: [SUBMITTED],
        APPROVED: [],
        REJECTED: [],
    }

    @classmethod
    def can_transition(cls, from_state, to_state):
        return to_state in cls.LEGAL_TRANSITIONS.get(from_state, [])

    @classmethod
    def transition(cls, instance, to_state, actor=None, reason=None):
        if not cls.can_transition(instance.state, to_state):
            raise ValidationError(
                f"Illegal transition: '{instance.state}' → '{to_state}'. "
                f"Allowed from '{instance.state}': {cls.LEGAL_TRANSITIONS.get(instance.state, [])}"
            )
        instance.state = to_state
        if to_state == KYCState.SUBMITTED and instance.submitted_at is None:
            instance.submitted_at = timezone.now()
        instance.save()
        # Log notification event
        NotificationEvent.objects.create(
            merchant=instance.merchant,
            submission=instance,
            event_type=f'state_changed_to_{to_state}',
            payload={
                'from_state': instance.state if hasattr(instance, '_original_state') else 'unknown',
                'to_state': to_state,
                'reason': reason,
                'actor_id': actor.id if actor else None,
            }
        )
        return instance


class UserProfile(models.Model):
    ROLE_MERCHANT = 'merchant'
    ROLE_REVIEWER = 'reviewer'
    ROLE_CHOICES = [
        (ROLE_MERCHANT, 'Merchant'),
        (ROLE_REVIEWER, 'Reviewer'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MERCHANT)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_merchant(self):
        return self.role == self.ROLE_MERCHANT

    @property
    def is_reviewer(self):
        return self.role == self.ROLE_REVIEWER


def validate_document(file):
    import os
    ext = os.path.splitext(file.name)[1].lower()
    allowed_ext = ['.pdf', '.jpg', '.jpeg', '.png']
    if ext not in allowed_ext:
        raise ValidationError(f"Unsupported file type '{ext}'. Allowed: {allowed_ext}")
    # 5 MB limit
    if file.size > 5 * 1024 * 1024:
        raise ValidationError(
            f"File too large: {file.size / (1024*1024):.1f} MB. Maximum allowed: 5 MB."
        )


class KYCSubmission(models.Model):
    BUSINESS_TYPE_CHOICES = [
        ('freelancer', 'Freelancer'),
        ('agency', 'Agency'),
        ('ecommerce', 'E-commerce'),
        ('saas', 'SaaS'),
        ('other', 'Other'),
    ]

    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_submissions')
    state = models.CharField(max_length=30, choices=KYCState.CHOICES, default=KYCState.DRAFT)

    # Step 1: Personal details
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Step 2: Business details
    business_name = models.CharField(max_length=255, blank=True)
    business_type = models.CharField(max_length=50, choices=BUSINESS_TYPE_CHOICES, blank=True)
    expected_monthly_volume = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Step 3: Documents
    pan_document = models.FileField(upload_to='documents/pan/', null=True, blank=True, validators=[validate_document])
    aadhaar_document = models.FileField(upload_to='documents/aadhaar/', null=True, blank=True, validators=[validate_document])
    bank_statement = models.FileField(upload_to='documents/bank/', null=True, blank=True, validators=[validate_document])

    # Reviewer info
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_submissions'
    )
    reviewer_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['submitted_at', 'created_at']

    def __str__(self):
        return f"KYC#{self.id} - {self.merchant.username} [{self.state}]"

    @property
    def is_at_risk(self):
        """Dynamically computed - never stored, never stale."""
        if self.state not in [KYCState.SUBMITTED, KYCState.UNDER_REVIEW]:
            return False
        reference_time = self.submitted_at or self.created_at
        return (timezone.now() - reference_time).total_seconds() > 86400  # 24 hours

    def transition_to(self, new_state, actor=None, reason=None):
        return KYCState.transition(self, new_state, actor=actor, reason=reason)


class NotificationEvent(models.Model):
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    submission = models.ForeignKey(KYCSubmission, on_delete=models.CASCADE, related_name='events', null=True)
    event_type = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.event_type} for merchant {self.merchant_id} at {self.timestamp}"
