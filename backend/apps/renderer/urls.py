# apps/renderer/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("renderer/preview/", views.preview, name="renderer_preview"),
    path("renderer/jobs/<uuid:job_id>/", views.job_status, name="renderer_job_status"),
    path("renderer/download/<uuid:job_id>/", views.download, name="renderer_download"),
]
