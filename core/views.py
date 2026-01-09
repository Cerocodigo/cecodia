from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction

from datetime import datetime

from .forms import SignupForm
from .models import Empresa, UsuarioEmpresa
from .dynamic_form import build_dynamic_form

from core.utils import empresa_activa
from motor.loader import obtener_modulos_empresa
from motor.mongo import get_mongo_empresa   # ✅ IMPORT FALTANTE


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "core/home.html"


@login_required
def home(request):
    empresa = empresa_activa(request)
    print("empresa >>>", empresa)

    modulos = []
    if empresa:
        modulos = obtener_modulos_empresa(empresa)

    print("MODULOS >>>", modulos)

    return render(request, "core/home.html", {
        "empresa": empresa,
        "modulos": modulos
    })


@login_required
def modulo_home(request, codigo):
    empresa = empresa_activa(request)

    return render(request, "core/modulo.html", {
        "empresa": empresa,
        "codigo": codigo
    })


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    email=form.cleaned_data['email']
                )

                empresa = Empresa.objects.create(
                    nombre=form.cleaned_data['empresa']
                )

                UsuarioEmpresa.objects.create(
                    user=user,
                    empresa=empresa,
                    es_admin=True
                )

                login(request, user)
                request.session['empresa_id'] = empresa.id

                return redirect('/')
    else:
        form = SignupForm()

    return render(request, 'core/signup.html', {'form': form})

@login_required
def cargar_formulario_modulo(request, modulo):
    print("modulo >>>", modulo)
    empresa = empresa_activa(request)
    print("empresa >>>", empresa)

    if not empresa:
        return render(request, "modulos/formulario.html", {
            "error": "No hay empresa activa"
        })

    db = get_mongo_empresa(empresa)
    print("db get_mongo_empresa >>>", db)

    #Modulo
    config = db.modulos.find_one({"nombre": modulo})
    print("config >>>", config)

    if not config:
        return render(request, "modulos/formulario.html", {
            "error": "Módulo no existe"
        })
    
    #Modelo
    Modelo = db.modelos.find_one({"modulo": config['_id']})
    print("Modelo >>>", Modelo)

    if not Modelo:
        return render(request, "modulos/formulario.html", {
            "error": "Modelo no existe"
        })
    

    FormClass = build_dynamic_form(Modelo['modelo']["campos"])
    print("FormClass >>>", FormClass)
    if request.method == "POST":
        form = FormClass(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            data["_created"] = datetime.now()
            data["_modulo"] = modulo
            data["_empresa_id"] = str(empresa.id)

            # 🔥 recomendado: colección por módulo
            db[modulo].insert_one(data)

            return render(request, "modulos/formulario.html", {
                "form": FormClass(),
                "titulo": config["nombre"],
                "success": True
            })
    else:
        form = FormClass()

    return render(request, "modulos/formulario.html", {
        "form": form,
        "titulo": config["nombre"],
        "modulo": modulo
    })