from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound
from common.permissions import IsTenantMember, CanApproveProject
from apps.projects.models import Project
from apps.projects.serializers import ProjectSerializer
from apps.approvals.models import ApprovalEvent
from apps.approvals.serializers import ApprovalActionSerializer, ApprovalEventSerializer
from apps.approvals.services import ApprovalWorkflowService

class ProjectApprovalActionView(APIView):
    """
    Executes a validated, concurrency-safe approval transition on a CapEx project.
    """
    permission_classes = [IsAuthenticated, IsTenantMember, CanApproveProject]

    def post(self, request, project_id):
        serializer = ApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data['action']
        notes = serializer.validated_data.get('notes', '')

        project, event = ApprovalWorkflowService.execute_transition(
            project_id=project_id,
            user=request.user,
            action=action,
            notes=notes
        )

        project_data = ProjectSerializer(project, context={'request': request}).data
        event_data = ApprovalEventSerializer(event).data

        return Response({
            'success': True,
            'message': f"Successfully executed '{action}' transition.",
            'project': project_data,
            'event': event_data
        }, status=status.HTTP_200_OK)


class ProjectApprovalHistoryView(APIView):
    """
    Retrieves the immutable audit trail of all approval events for a project.
    """
    permission_classes = [IsAuthenticated, IsTenantMember]

    def get(self, request, project_id):
        # Validate that the project is accessible to the current user
        try:
            project = Project.objects.for_user(request.user).get(id=project_id)
        except Project.DoesNotExist:
            raise NotFound("Project not found.") from None

        events = ApprovalEvent.objects.filter(project_id=project.id).select_related('actor').order_by('created_at')
        serializer = ApprovalEventSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
