from rest_framework import serializers
from .models import Report, ReportVersion


class ReportVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportVersion
        fields = ["id", "version", "note", "saved_at"]


class ReportSerializer(serializers.ModelSerializer):
    versions = ReportVersionSerializer(many=True, read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "name",
            "definition",
            "is_archived",
            "created_at",
            "updated_at",
            "versions",
        ]
