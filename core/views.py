# core/views.py
from django.views.generic import TemplateView, FormView
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy

class DashboardView(TemplateView):
    template_name = "dashboard.html"

class MapView(TemplateView):
    template_name = "map.html"

class UploadView(TemplateView):
    template_name = "upload.html"

class RecordsView(TemplateView):
    template_name = "records.html"

class SignUpView(FormView):
    template_name = "registration/signup.html"
    form_class = UserCreationForm
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)
