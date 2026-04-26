# EXPLAINER.md — Playto KYC Pipeline

## 1. The State Machine

**Where it lives:** `backend/kyc/models.py` — the `KYCState` class. Single source of truth. No state logic in views.

```python
class KYCState:
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    MORE_INFO_REQUESTED = 'more_info_requested'

    # THE ONLY place transitions are defined
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
        NotificationEvent.objects.create(...)
        return instance
```

**How illegal transitions are prevented:**
1. `KYCState.can_transition()` checks `LEGAL_TRANSITIONS` dict — if `to_state` not in allowed list, returns False.
2. `transition()` raises `ValidationError` before touching the DB.
3. The `StateTransitionSerializer` validates at the API layer *before* the view calls `transition_to()`.
4. The model's `transition_to()` method calls `KYCState.transition()` — same guard again.

Two-layer protection: serializer (API) + model method (business logic).

---

## 2. The Upload

**Where it lives:** `backend/kyc/serializers.py` — `DocumentField` class.

```python
class DocumentField(serializers.FileField):
    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
    MAX_SIZE = 5 * 1024 * 1024  # 5 MB exactly

    def to_internal_value(self, data):
        file = super().to_internal_value(data)
        # Extension check — NOT trusting client Content-Type
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Unsupported file extension '{ext}'. Accepted: {sorted(self.ALLOWED_EXTENSIONS)}"
            )
        # Size check
        if file.size > self.MAX_SIZE:
            mb = file.size / (1024 * 1024)
            raise serializers.ValidationError(
                f"File '{file.name}' is {mb:.1f} MB. Maximum allowed size is 5 MB."
            )
        return file
```

**What happens with a 50 MB file:**
Django's default upload handler reads the file into memory/temp storage. When `to_internal_value` runs, `file.size` is already known. The check fires, raises `ValidationError`, DRF catches it and returns HTTP 400:
```json
{"error": "Validation failed", "details": {"pan_document": ["File 'scan.pdf' is 50.0 MB. Maximum allowed size is 5 MB."]}}
```
The file is discarded — never saved to disk.

**Why not trust Content-Type:** A client can send `Content-Type: image/jpeg` with a `.exe` file. We check the extension instead, which is verifiable from the filename. In a production system, I'd also add `python-magic` for actual byte-level MIME detection.

---

## 3. The Queue

**Where it lives:** `backend/kyc/views.py` — `ReviewerQueueView`

```python
def get(self, request):
    submissions = KYCSubmission.objects.filter(
        state__in=[KYCState.SUBMITTED, KYCState.UNDER_REVIEW, KYCState.MORE_INFO_REQUESTED]
    ).select_related('merchant', 'reviewer').order_by('submitted_at', 'created_at')

    data = KYCSubmissionSerializer(submissions, many=True, context={'request': request}).data
    return Response(data)
```

**SLA flag (is_at_risk)** — computed as a Python `@property` on the model, never stored:
```python
@property
def is_at_risk(self):
    if self.state not in [KYCState.SUBMITTED, KYCState.UNDER_REVIEW]:
        return False
    reference_time = self.submitted_at or self.created_at
    return (timezone.now() - reference_time).total_seconds() > 86400
```

**Why this way:**
- `select_related('merchant', 'reviewer')` → 1 SQL query with JOINs instead of N+1 queries per submission.
- `order_by('submitted_at', 'created_at')` → oldest submitted first, which is fair FIFO queue ordering.
- SLA as `@property` → never stale. A stored boolean flag would need a cron job to update. This always reflects current reality.
- Filter on `state__in=[...]` → only actionable submissions in queue. Approved/rejected are excluded.

---

## 4. The Auth

**How merchant A is stopped from seeing merchant B's submission:**

```python
# In MerchantSubmissionDetailView:
def get_object(self, pk, user):
    try:
        # merchant= filter scopes the query to only THIS user's submissions
        return KYCSubmission.objects.get(pk=pk, merchant=user)
    except KYCSubmission.DoesNotExist:
        return None

def get(self, request, pk):
    submission = self.get_object(pk, request.user)
    if not submission:
        return error_response('Submission not found.', 404)  # 404, not 403
    ...
```

**Three layers:**
1. `IsMerchant` permission class — only authenticated users with `role=merchant` can hit merchant endpoints.
2. `merchant=request.user` filter on every DB query — even if merchant knows another's ID, the query returns nothing.
3. Return 404 (not 403) — doesn't leak that the submission exists.

Reviewer endpoints use `IsReviewer` permission — merchants get 403 if they try to hit `/reviewer/*`.

---

## 5. The AI Audit

**What happened:** I asked Claude to write the file validation logic. It initially generated this:

```python
# AI's first attempt — BUGGY
import magic

def validate_document(file):
    mime = magic.from_buffer(file.read(1024), mime=True)
    if mime not in ['application/pdf', 'image/jpeg', 'image/png']:
        raise ValidationError(f"Invalid file type: {mime}")
    if file.size > 5 * 1024 * 1024:
        raise ValidationError("File too large")
```

**What was wrong:**
1. `file.read(1024)` moves the file pointer. After this, Django tries to save the file, but it reads from the current position — so it saves only the remaining bytes after position 1024, corrupting every uploaded file. I had to add `file.seek(0)` after reading to reset the pointer.
2. `python-magic` requires `libmagic` installed on the system. On most deployment environments (Railway, Render free tier), this isn't available by default without a `Dockerfile` with `apt-get install libmagic1`. The code would crash at import time with no clear error message.
3. The error message says "Invalid file type" without telling the user what IS valid — bad UX.

**What I replaced it with:**
```python
class DocumentField(serializers.FileField):
    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
    MAX_SIZE = 5 * 1024 * 1024

    def to_internal_value(self, data):
        file = super().to_internal_value(data)
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Unsupported file extension '{ext}'. Accepted: {sorted(self.ALLOWED_EXTENSIONS)}"
            )
        if file.size > self.MAX_SIZE:
            mb = file.size / (1024 * 1024)
            raise serializers.ValidationError(
                f"File '{file.name}' is {mb:.1f} MB. Maximum allowed size is 5 MB."
            )
        return file
```

Extension-based validation: no file pointer issues, no system dependency, works everywhere, clear error messages. The tradeoff is a malicious user could rename a `.exe` to `.pdf` — in production I'd add the `python-magic` check too but with `file.seek(0)` and a graceful fallback.
