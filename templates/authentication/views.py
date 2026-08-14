from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.models import User


class RegisterView(CreateView):
    model = User
    form_class = UserCreationForm
    template_name = 'authentication/register.html'
    success_url = reverse_lazy('authentication:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        # Opcional: iniciar sesión automáticamente
        # login(self.request, self.object)
        return response