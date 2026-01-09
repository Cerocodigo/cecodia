from django.urls import path
from . import views

urlpatterns = [
    path(
        "modulo/<str:modulo>/form/",
        views.cargar_formulario_modulo,
        name="modulo_form"
    ),
]