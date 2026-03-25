from rest_framework import serializers
from .models import PDFJob


class PDFJobSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = PDFJob
        fields = [
            "id",
            "status",
            "error",
            "created_at",
            "updated_at",
            "download_url",
        ]

    def get_download_url(self, obj):
        if obj.status == PDFJob.Status.DONE and obj.pdf_file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.pdf_file.url)
        return None
