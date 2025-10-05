# core/views.py
from django.views.generic import TemplateView

class DashboardView(TemplateView):
    template_name = "dashboard.html"

class MapView(TemplateView):
    template_name = "map.html"

class UploadView(TemplateView):
    template_name = "upload.html"

class RecordsView(TemplateView):
    template_name = "records.html"
