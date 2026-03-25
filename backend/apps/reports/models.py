import uuid
from django.db import models
from django.conf import settings


class Report(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports"
    )
    name = models.CharField(max_length=255)
    definition = models.JSONField()  # JSON payload from Angular
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ReportVersion(models.Model):
    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="versions"
    )
    version = models.PositiveIntegerField()
    definition = models.JSONField()
    note = models.CharField(max_length=255, blank=True)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
