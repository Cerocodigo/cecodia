from django import forms
from django.contrib.auth.models import User
from .models import Empresa

class SignupForm(forms.Form):
    username = forms.CharField(label="Usuario")
    password = forms.CharField(widget=forms.PasswordInput)
    email = forms.EmailField()
    empresa = forms.CharField(label="Nombre del negocio")