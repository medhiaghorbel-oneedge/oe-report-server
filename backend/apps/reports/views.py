from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Report, ReportVersion
from .serializers import ReportSerializer, ReportVersionSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated


class ReportViewSet(viewsets.ModelViewSet):

    def get_permissions(self):
        if settings.DISABLE_AUTH:
            return [AllowAny()]
        return [IsAuthenticated()]

    # TODO permission_classes = [IsAuthenticated]

    serializer_class = ReportSerializer

    def get_queryset(self):
        if settings.DISABLE_AUTH:
            return Report.objects.filter(is_archived=False)

        return Report.objects.filter(owner=self.request.user, is_archived=False)

    def perform_create(self, serializer):
        user = self.request.user

        if settings.DISABLE_AUTH:
            from django.contrib.auth import get_user_model

            user = get_user_model().objects.first()

        report = serializer.save(owner=user)

        ReportVersion.objects.create(
            report=report, version=1, definition=report.definition
        )

    # TODO Versioning
    # def perform_update(self, serializer):
    #     report = serializer.save()
    #     last_version = report.versions.first()  # ordering is -version
    #     next_version = (last_version.version + 1) if last_version else 1
    #     ReportVersion.objects.create(
    #         report=report,
    #         version=next_version,
    #         definition=report.definition,
    #     )

    def perform_destroy(self, instance):
        instance.is_archived = True
        instance.save()

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
