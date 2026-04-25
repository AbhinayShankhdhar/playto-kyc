from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─────────────────────────────────────────────
#  STATE MACHINE  (single source of truth)
# ─────────────────────────────────────────────

class KYCState:
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    MORE_INFO = 'more_info_requested'

    CHOICES = [
        (DRAFT, 'Draft'),
        (SUBMITTED, 'Submitted'),
        (UNDER_REVIEW, 'Under Review'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (MORE_INFO, 'More Info Requested'),
    ]

    # Legal transitions: from_state -> [allowed to_states]
    TRANSITIONS = {
        DRAFT:        [SUBMITTED],
        SUBMITTED:    [UNDER_REVIEW],
        UNDER_REVIEW: [APPROVED, REJECTED, MORE_INFO],
        MORE_INFO:    [SUBMITTED],
        APPROVED:     [],   # terminal state
        REJECTED:     [],   # terminal state
    }

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        return to_state in cls.TRANSITIONS.get(from_state, [])

    @classmethod
    def validate_transition(cls, from_state: str, to_state: str) -> None:
        """Raise ValueError with a clear message if transition is illegal."""
        if not cls.can_transition(from_state, to_state):
            allowed = cls.TRANSITIONS.get(from_state, [])
            raise ValueError(
                f"Cannot move from '{from_state}' to '{to_state}'. "
                f"Allowed transitions from '{from_state}': {allowed or ['none (terminal state)']}"
            )


# ─────────────────────────────────────────────
#  USER PROFILE  (merchant vs reviewer role)
# ─────────────────────────────────────────────

class UserProfile(models.Model):
    MERCHANT = 'merchant'
    REVIEWER = 'reviewer'
    ROLE_CHOICES = [(MERCHANT, 'Merchant'), (REVIEWER, 'Reviewer')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=MERCHANT)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_merchant(self):
        return self.role == self.MERCHANT

    @property
    def is_reviewer(self):
        return self.role == self.REVIEWER


# ─────────────────────────────────────────────
#  KYC SUBMISSION
# ─────────────────────────────────────────────

class KYCSubmission(models.Model):
    BUSINESS_TYPE_CHOICES = [
        ('agency', 'Agency'),
        ('freelancer', 'Freelancer'),
        ('ecommerce', 'E-commerce'),
        ('saas', 'SaaS'),
        ('other', 'Other'),
    ]

    # Ownership
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')

    # State
    state = models.CharField(
        max_length=30,
        choices=KYCState.CHOICES,
        default=KYCState.DRAFT,
        db_index=True,
    )

    # Personal details
    full_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Business details
    business_name = models.CharField(max_length=200, blank=True)
    business_type = models.CharField(max_length=50, choices=BUSINESS_TYPE_CHOICES, blank=True)
    monthly_volume_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Reviewer fields
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_submissions'
    )
    reviewer_note = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)  # when first submitted

    class Meta:
        ordering = ['created_at']  # oldest first for review queue

    def __str__(self):
        return f"KYC#{self.pk} - {self.merchant.username} [{self.state}]"

    def transition_to(self, new_state: str, reviewer_note: str = '', actor=None) -> None:
        """
        Perform a state transition after validating it.
        Raises ValueError for illegal transitions (caught by view → 400).
        """
        KYCState.validate_transition(self.state, new_state)

        old_state = self.state
        self.state = new_state

        if new_state == KYCState.SUBMITTED and self.submitted_at is None:
            self.submitted_at = timezone.now()

        if reviewer_note:
            self.reviewer_note = reviewer_note

        if actor:
            self.reviewer = actor

        self.save()

        # Log notification event
        NotificationEvent.objects.create(
            merchant=self.merchant,
            submission=self,
            event_type=f'state_changed_to_{new_state}',
            payload={
                'from_state': old_state,
                'to_state': new_state,
                'reviewer_note': reviewer_note,
                'actor_id': actor.id if actor else None,
            }
        )

    @property
    def is_sla_at_risk(self) -> bool:
        """
        Dynamically computed — never stored, never stale.
        A submission is at_risk if it has been in the queue (submitted or under_review)
        for more than 24 hours without resolution.
        """
        if self.state not in (KYCState.SUBMITTED, KYCState.UNDER_REVIEW, KYCState.MORE_INFO):
            return False
        reference_time = self.submitted_at or self.updated_at
        return (timezone.now() - reference_time).total_seconds() > 86400  # 24h


# ─────────────────────────────────────────────
#  KYC DOCUMENTS
# ─────────────────────────────────────────────

class KYCDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ('pan', 'PAN Card'),
        ('aadhaar', 'Aadhaar'),
        ('bank_statement', 'Bank Statement'),
    ]

    submission = models.ForeignKey(KYCSubmission, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to='kyc_docs/%Y/%m/')
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()  # bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('submission', 'doc_type')  # one doc per type per submission

    def __str__(self):
        return f"{self.doc_type} for KYC#{self.submission_id}"


# ─────────────────────────────────────────────
#  NOTIFICATION EVENTS  (audit log)
# ─────────────────────────────────────────────

class NotificationEvent(models.Model):
    merchant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    submission = models.ForeignKey(KYCSubmission, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.event_type} for merchant {self.merchant_id} at {self.timestamp}"
