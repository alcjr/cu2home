from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import TemplateView
from .utils.config_reader import read_config, write_config, get_all_sections
from .mixins import StaffRequiredMixin

class ConfigView(StaffRequiredMixin, TemplateView):
    template_name = 'dashboard/config.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sections'] = get_all_sections()
        return context

    def post(self, request, *args, **kwargs):
        for key, value in request.POST.items():
            if '__' in key and key != 'csrfmiddlewaretoken':
                section, k = key.split('__', 1)
                write_config(section, k, value)
        messages.success(request, 'Configuración actualizada.')
        return redirect('dashboard:config')