from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/register/', views.RegisterView.as_view()),
    path('auth/login/', views.LoginView.as_view()),
    path('auth/me/', views.MeView.as_view()),

    # Merchant
    path('merchant/submissions/', views.MerchantSubmissionListView.as_view()),
    path('merchant/submissions/<int:pk>/', views.MerchantSubmissionDetailView.as_view()),
    path('merchant/submissions/<int:pk>/submit/', views.MerchantSubmitView.as_view()),

    # Reviewer
    path('reviewer/queue/', views.ReviewerQueueView.as_view()),
    path('reviewer/submissions/', views.ReviewerAllSubmissionsView.as_view()),
    path('reviewer/submissions/<int:pk>/', views.ReviewerSubmissionDetailView.as_view()),
    path('reviewer/submissions/<int:pk>/transition/', views.ReviewerTransitionView.as_view()),
    path('reviewer/metrics/', views.ReviewerDashboardMetricsView.as_view()),

    # Notifications
    path('notifications/', views.NotificationListView.as_view()),
]
