from django.urls import path
from apps.analytics.views import DashboardAnalyticsView, RefreshAnalyticsView

urlpatterns = [
    path('dashboard/', DashboardAnalyticsView.as_view(), name='analytics_dashboard'),
    path('refresh/', RefreshAnalyticsView.as_view(), name='analytics_refresh'),
]
