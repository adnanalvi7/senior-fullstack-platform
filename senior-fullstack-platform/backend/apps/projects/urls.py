from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.projects.views import ProjectViewSet
from apps.approvals.views import ProjectApprovalActionView, ProjectApprovalHistoryView

router = DefaultRouter()
router.register(r'', ProjectViewSet, basename='project')

urlpatterns = [
    # Approval action and history attached to project id
    path('<int:project_id>/approve/', ProjectApprovalActionView.as_view(), name='project_approve'),
    path('<int:project_id>/history/', ProjectApprovalHistoryView.as_view(), name='project_approval_history'),
    path('', include(router.urls)),
]
