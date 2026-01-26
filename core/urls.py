from django.urls import path
from . import views

urlpatterns = [
    path("modulo/<str:modulo>/consulta/<int:id>",views.cargar_formulario_consulta,name="modulo_form"), # 
    path("modulo/<str:modulo>/form/",views.cargar_formulario_modulo,name="modulo_form"), # 
    path("modulo/<str:modulo>/bd/",views.actualiazarBd,name="modulo_form"), ##
    path("modulo/<str:modulo>/main/",views.cargar_modulo_main,name="modulo_form"), #     
    path("modulo/<str:modulo>/nuevo/",views.cargar_modulo_nuevo,name="modulo_form"), #     

]