from django.urls import path
from . import views

urlpatterns = [
    # ── Auth ──────────────────────────────────
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),
    path('auth/me/', views.me, name='me'),

    # ── Merchant ──────────────────────────────
    path('submissions/', views.MerchantSubmissionListCreate.as_view(), name='submission-list'),
    path('submissions/<int:pk>/', views.MerchantSubmissionDetail.as_view(), name='submission-detail'),
    path('submissions/<int:pk>/submit/', views.merchant_submit, name='submission-submit'),
    path('submissions/<int:pk>/documents/<str:doc_type>/', views.upload_document, name='upload-document'),

    # ── Reviewer ──────────────────────────────
    path('reviewer/queue/', views.ReviewerQueue.as_view(), name='reviewer-queue'),
    path('reviewer/metrics/', views.reviewer_dashboard_metrics, name='reviewer-metrics'),
    path('reviewer/submissions/<int:pk>/', views.ReviewerSubmissionDetail.as_view(), name='reviewer-submission-detail'),
    path('reviewer/submissions/<int:pk>/transition/', views.reviewer_transition, name='reviewer-transition'),

    # ── Notifications ─────────────────────────
    path('notifications/', views.my_notifications, name='notifications'),
]
