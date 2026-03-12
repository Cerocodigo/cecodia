from django.urls import path
from . import views

urlpatterns = [

    path("modulo/<str:modulo>/consulta/<int:id>",views.cargar_formulario_consulta,name="modulo_form"), # 
    path("modulo/<str:modulo>/form/",views.cargar_formulario_modulo,name="modulo_form"), # 
    path("modulo/<str:modulo>/db/",views.actualiazarBd,name="modulo_form"), ##
    path("modulo/<str:modulo>/main/",views.cargar_modulo_main,name="modulo_form"), #     
    path("modulo/<str:modulo>/nuevo/",views.cargar_modulo_nuevo,name="modulo_form"), #     
    path("calculosCampos/<str:modelo>/<str:campo>/",views.calculosCampos,name="modulo_form"), #    
    path("calculosQueryBaseDatos/<str:modelo>/<str:campo>/",views.calculosQueryBaseDatos,name="modulo_form"), #   
    path("calculosReferenciaBuscador/<str:modelo>/<str:campo>/",views.calculosReferenciaBuscador,name="modulo_form"), #   

]