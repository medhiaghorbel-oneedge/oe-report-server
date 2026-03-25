# apps/renderer/views.py
import io
import uuid

from django.core.files.base import ContentFile
from django.http import FileResponse
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.reports.models import Report
from .models import PDFJob
from .serializers import PDFJobSerializer
from .permissions import IsAuthenticatedOrDevDisabled

from engine.models.report_models import parse_report
from engine.renderers.pdf_renderer import PDFRenderer


from django.contrib.auth import get_user_model
from django.conf import settings


def get_dev_user(request):
    if request.user.is_authenticated:
        return request.user
    return get_user_model().objects.first()


def _render_to_job(payload: dict, owner, report_instance=None) -> PDFJob:
    """
    Core helper: parse payload → render PDF → save PDFJob record.
    Raises ValueError / ValidationError on bad input.
    Raises RuntimeError on render failure.
    """
    job = PDFJob.objects.create(
        owner=owner,
        report=report_instance,
        status=PDFJob.Status.PROCESSING,
    )

    try:
        report_model = parse_report(payload)
        pdf_bytes = PDFRenderer().render(report_model)
    except Exception as exc:
        job.status = PDFJob.Status.FAILED
        job.error = str(exc)
        job.save()
        raise RuntimeError(str(exc)) from exc

    filename = f"{report_model.name or 'report'}-{uuid.uuid4().hex[:8]}.pdf"
    job.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
    job.status = PDFJob.Status.DONE
    job.save()
    return job


# ── POST /api/renderer/preview/ ───────────────────────────────────────────────


@api_view(["POST"])
@permission_classes([IsAuthenticatedOrDevDisabled])
def preview(request):
    """
    Render a raw ReportModel JSON payload → PDF.
    Does not require a saved report. Used by the Angular Export PDF button.
    Returns the PDF file directly (no job polling needed for Phase 4).
    """
    payload = request.data
    if not isinstance(payload, dict):
        return Response(
            {"detail": "Request body must be a JSON object."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        owner = get_dev_user(request)
        job = _render_to_job(payload, owner=owner)
    except RuntimeError as exc:
        return Response(
            {"detail": f"Render error: {exc}"},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # Stream the file directly — client downloads immediately
    job.pdf_file.open("rb")
    response = FileResponse(
        job.pdf_file,
        content_type="application/pdf",
        as_attachment=True,
        filename=job.pdf_file.name.split("/")[-1],
    )
    return response


# ── GET /api/renderer/jobs/{job_id}/ ─────────────────────────────────────────


@api_view(["GET"])
@permission_classes([IsAuthenticatedOrDevDisabled])
def job_status(request, job_id):
    """
    Return the current status of a PDF job.
    Phase 6 will make rendering async — this endpoint is already in place
    so the Angular polling pattern can be wired without future URL changes.
    """

    owner = get_dev_user(request)

    job = get_object_or_404(PDFJob, id=job_id, owner=owner)
    serializer = PDFJobSerializer(job, context={"request": request})
    return Response(serializer.data)


# ── GET /api/renderer/download/{job_id}/ ──────────────────────────────────────


from django.http import FileResponse
import os


# TODO FIX IT BROKEN PDF
@api_view(["GET"])
@permission_classes([IsAuthenticatedOrDevDisabled])
def download(request, report_id):
    owner = get_dev_user(request)

    job = (
        PDFJob.objects.filter(
            report_id=report_id,
            owner=owner,
            status=PDFJob.Status.DONE,
        )
        .order_by("-created_at")
        .first()
    )

    print(job)

    if not job or not job.pdf_file:
        return Response(
            {"detail": "No completed PDF found for this report."},
            status=status.HTTP_404_NOT_FOUND,
        )

    file_path = job.pdf_file.path  # 🔥 IMPORTANT

    if not os.path.exists(file_path):
        return Response(
            {"detail": "File not found on disk."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return FileResponse(
        open(file_path, "rb"),  # ✅ real file stream
        content_type="application/pdf",
        as_attachment=True,
        filename=os.path.basename(file_path),
    )
