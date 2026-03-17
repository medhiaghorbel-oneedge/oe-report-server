from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Report, ReportVersion
from .serializers import ReportSerializer, ReportVersionSerializer
from rest_framework.permissions import IsAuthenticated


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Report.objects.filter(owner=self.request.user, is_archived=False)

    def perform_create(self, serializer):
        report = serializer.save(owner=self.request.user)
        # automatically create initial version
        ReportVersion.objects.create(
            report=report, version=1, definition=report.definition
        )

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        report = self.get_object()
        versions = report.versions.all()
        serializer = ReportVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="restore/(?P<version>\d+)")
    def restore_version(self, request, pk=None, version=None):
        report = self.get_object()
        try:
            report_version = report.versions.get(version=version)
        except ReportVersion.DoesNotExist:
            return Response(
                {"detail": "Version not found"}, status=status.HTTP_404_NOT_FOUND
            )
        report.definition = report_version.definition
        report.save()
        return Response(ReportSerializer(report).data)
