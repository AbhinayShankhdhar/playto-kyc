# EXPLAINER.md

## 1. The State Machine

**Where does it live?**

The state machine lives entirely in `kyc_app/models.py` inside the `KYCState` class. There is a single `TRANSITIONS` dict that is the authoritative source of truth. No transitions are hardcoded in views.

```python
class KYCState:
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    MORE_INFO = 'more_info_requested'

    TRANSITIONS = {
        DRAFT:        [SUBMITTED],
        SUBMITTED:    [UNDER_REVIEW],
        UNDER_REVIEW: [APPROVED, REJECTED, MORE_INFO],
        MORE_INFO:    [SUBMITTED],
        APPROVED:     [],   # terminal
        REJECTED:     [],   # terminal
    }

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        return to_state in cls.TRANSITIONS.get(from_state, [])

    @classmethod
    def validate_transition(cls, from_state: str, to_state: str) -> None:
        if not cls.can_transition(from_state, to_state):
            allowed = cls.TRANSITIONS.get(from_state, [])
            raise ValueError(
                f"Cannot move from '{from_state}' to '{to_state}'. "
                f"Allowed: {allowed or ['none (terminal state)']}"
            )
```

**How is an illegal transition prevented?**

The `KYCSubmission.transition_to()` method calls `KYCState.validate_transition()` before doing anything. If the transition is illegal, it raises `ValueError`. The view catches this and returns a 400:

```python
try:
    submission.transition_to(new_state, reviewer_note=note, actor=request.user)
except ValueError as e:
    return Response({'error': True, 'message': str(e)}, status=400)
```

The state machine is never duplicated in views. Views call `transition_to()` and handle the exception. That's it.

---

## 2. The File Upload

**How are files validated?**

Validation is in `kyc_app/serializers.py`, `validate_kyc_file()`. It runs server-side in the DRF serializer — the client cannot bypass it.

```python
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
ALLOWED_MIME_TYPES = {'application/pdf', 'image/jpeg', 'image/png'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

def validate_kyc_file(file):
    # 1. Extension whitelist (primary gate)
    _, ext = os.path.splitext(file.name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise serializers.ValidationError(
            f"File type '{ext}' is not allowed. Accepted: PDF, JPG, PNG."
        )

    # 2. Size check
    if file.size > MAX_FILE_SIZE:
        size_mb = file.size / (1024 * 1024)
        raise serializers.ValidationError(
            f"File size {size_mb:.1f} MB exceeds the 5 MB limit."
        )

    # 3. MIME type (secondary check)
    content_type = getattr(file, 'content_type', '')
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise serializers.ValidationError(
            f"MIME type '{content_type}' is not allowed."
        )

    return file
```

**What happens with a 50 MB file?**

The size check `file.size > MAX_FILE_SIZE` catches it immediately. Django streams the file into a temp buffer before calling the serializer, so the full file is read — but we reject it with a clear 400 error:
`"File size 50.0 MB exceeds the 5 MB limit."`

Django's `DATA_UPLOAD_MAX_MEMORY_SIZE` provides a second layer of protection (default 2.5 MB for in-memory files; larger files are spooled to disk but still validated by our check).

Note: Extension check is the primary gate, not MIME type, because MIME type is client-supplied and an attacker can rename `malware.exe` to `doc.pdf` and set `content_type: application/pdf`. The extension whitelist + size check + content_type check together give defense-in-depth.

---

## 3. The Queue

**Query powering the reviewer queue:**

```python
# kyc_app/views.py — ReviewerQueue.get_queryset()
return KYCSubmission.objects.filter(
    state__in=[KYCState.SUBMITTED, KYCState.UNDER_REVIEW, KYCState.MORE_INFO]
).select_related('merchant').order_by('created_at')
```

**Why written this way:**

- `state__in=[...]` — only active (non-terminal) submissions appear in the queue. Approved and rejected are excluded.
- `order_by('created_at')` — oldest submissions first, enforcing FIFO review priority. This ensures merchants who waited longest get reviewed first.
- `select_related('merchant')` — joins the User table in a single SQL query instead of one extra query per row (N+1 prevention).

**SLA flag:**

The `is_sla_at_risk` flag is a `@property` on the model, computed dynamically:

```python
@property
def is_sla_at_risk(self) -> bool:
    if self.state not in (KYCState.SUBMITTED, KYCState.UNDER_REVIEW, KYCState.MORE_INFO):
        return False
    reference_time = self.submitted_at or self.updated_at
    return (timezone.now() - reference_time).total_seconds() > 86400
```

It is never stored in the database. This means it never goes stale. A submission that was submitted 23 hours ago will show `false`; 25 hours later it automatically shows `true` without any background job.

The metrics endpoint computes `at_risk_count` by iterating the queued queryset in Python — acceptable for reasonable queue sizes. For scale, this would move to a database annotation.

---

## 4. The Auth

**How does the system stop Merchant A from seeing Merchant B's submission?**

Two layers:

**Layer 1 — Queryset filter** (in `MerchantSubmissionListCreate`):

```python
def get_queryset(self):
    # Merchant only sees their OWN submissions
    return KYCSubmission.objects.filter(merchant=self.request.user)
```

This means even if Merchant A somehow guesses Merchant B's submission ID, the queryset won't include it.

**Layer 2 — Object-level permission** (in `permissions.py`):

```python
class IsOwnerOrReviewer(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        # Reviewer sees all
        if hasattr(user, 'profile') and user.profile.is_reviewer:
            return True
        # Merchant sees only their own
        return obj.merchant == user
```

The detail view (`MerchantSubmissionDetail.get_object`) calls `self.check_object_permissions(self.request, obj)` which invokes this check. If a merchant tries to access another merchant's submission ID directly via URL, they get a 403.

The combination of filtered queryset + object-level check means there is no single point of failure.

---

## 5. The AI Audit

**Example: AI wrote an insecure file validation**

When I asked an AI tool to write the file upload validation, it initially generated this:

```python
# WHAT THE AI GAVE ME (buggy/insecure)
def validate_file(file):
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
    if file.content_type not in allowed_types:
        raise ValidationError("Invalid file type.")
    if file.size > 5242880:
        raise ValidationError("File too large.")
    return file
```

**What I caught:**

The validation relies entirely on `file.content_type`, which is sent by the client in the HTTP request. An attacker can upload a malicious `.exe` file and simply set the `Content-Type` header to `image/jpeg`. The server would accept it because it never checks the actual file extension or content.

**What I replaced it with:**

```python
def validate_kyc_file(file):
    # Primary gate: extension whitelist (cannot be spoofed by header manipulation)
    _, ext = os.path.splitext(file.name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise serializers.ValidationError(
            f"File type '{ext}' is not allowed. Accepted: PDF, JPG, PNG."
        )
    # Size check
    if file.size > MAX_FILE_SIZE:
        size_mb = file.size / (1024 * 1024)
        raise serializers.ValidationError(
            f"File size {size_mb:.1f} MB exceeds the 5 MB limit."
        )
    # MIME type as a secondary (not primary) check
    content_type = getattr(file, 'content_type', '')
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise serializers.ValidationError(
            f"MIME type '{content_type}' is not allowed."
        )
    return file
```

The key fix: extension check (from the filename) comes first and is the hard gate. MIME type is a secondary check. For production I would also add magic-byte inspection (reading the first few bytes of the file) using the `python-magic` library to truly verify file content regardless of name or headers. I noted this in comments but didn't add the library to keep setup simple.

---

## Design decisions I'd revisit with more time

1. **Magic-byte validation** — Add `python-magic` to verify actual file content, not just extension/MIME.
2. **SLA metrics at scale** — Move the `at_risk_count` calculation to a database annotation using `Case/When` instead of a Python loop.
3. **Background jobs** — Use Celery to actually send notification emails when events are logged.
4. **Round-robin reviewer assignment** — Auto-assign incoming submissions to reviewers with the lightest load.
5. **Pagination** — Add cursor pagination to the queue endpoint for large datasets.
