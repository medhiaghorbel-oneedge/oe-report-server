from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Report, ReportVersion
from .serializers import ReportSerializer, ReportVersionSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
import uuid


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

    @action(detail=False, methods=["post"], url_path="save")
    def save(self, request):
        """
        Upsert a report by its frontend-generated UUID.
        - If the UUID exists and belongs to user → update it
        - If the UUID doesn't exist → create new with that UUID
        POST /api/reports/save/
        Body: full ReportModel JSON from the Angular serialiser.
        """

        payload = request.data
        report_id = payload.get("id")

        if not report_id:
            return Response(
                {"detail": "Report payload must include an 'id' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate UUID format
        try:
            uuid_obj = uuid.UUID(report_id)
        except (ValueError, AttributeError, TypeError):
            return Response(
                {"detail": f"'{report_id}' is not a valid UUID format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if settings.DISABLE_AUTH:
            from django.contrib.auth import get_user_model

            user = get_user_model().objects.first()

        # Try to get existing report
        try:
            report = Report.objects.get(id=report_id)

            # Ownership check for existing report
            if not settings.DISABLE_AUTH and report.owner != user:
                return Response(
                    {"detail": "Not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Update existing report
            report.name = payload.get("name", report.name)
            report.definition = payload
            report.save()

            return Response({"id": str(report.id), "saved": True})

        except Report.DoesNotExist:
            # Create new report with the provided UUID
            report = Report.objects.create(
                id=report_id,
                owner=user,
                name=payload.get("name", "Untitled"),
                definition=payload,
            )

            # Create initial version
            ReportVersion.objects.create(
                report=report, version=1, definition=report.definition
            )

            return Response({"id": str(report.id), "saved": True})

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
