
import pymysql


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
from .dynamic_form import build_dynamic_form,  build_dynamic_formAdmin

from core.utils import empresa_activa
from motor.loader import obtener_modulos_empresa
from motor.mongo import get_mongo_empresa, mongo_field_to_sql  # ✅ IMPORT FALTANTE
from core.ia import interpretar_prompt


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
    config = db.modulos.find_one({"_id": modulo})
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
    
    prompt = request.GET.get("prompt", "")
    modeloIA = None
    if prompt:
        # 🔮 FUTURO: aquí se enviará a IA
        modeloIA = interpretar_prompt(prompt, Modelo['modelo']["campos"])
        print("modeloIA >>" , modeloIA)

    if modeloIA == None:
        FormClass = build_dynamic_form(Modelo['modelo']["campos"])
    else:
        FormClass = build_dynamic_formAdmin(modeloIA["campos"])
                
    print("FormClass >>>", FormClass)
    campos_activos = (
        modeloIA["campos"]
        if modeloIA else
        Modelo['modelo']["campos"]
    )
    if request.method == "POST":
        form = FormClass(request.POST)

        if form.is_valid():

            # 🔹 guardar cambios del modelo IA (si existen)
            if modeloIA:
                db.modelos.update_one(
                    {"_id": Modelo["_id"]},
                    {"$set": {"modelo.campos": campos_activos}}
                )

            return render(request, "modulos/formulario.html", {
                "form": FormClass(),
                "titulo": config["nombre"],
                "modulo": modulo,
                "success": "estructura actualizada correctamente"
            })
           
    else:
        form = FormClass()

    return render(request, "modulos/formulario.html", {
        "form": form,
        "titulo": config["nombre"],
        "modulo": modulo
    })


@login_required
def actualiazarBd(request, modulo):

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
    config = db.modulos.find_one({"_id": modulo})
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

    mysql = pymysql.connect(
        host=empresa.sql_url,
        user=empresa.sql_user,
        password=empresa.sql_clave,
        database=empresa.sql_db
    )

    """
    mongo_db: conexión pymongo
    mysql_conn: conexión MySQL/MariaDB
    modulo: nombre del módulo (ej: 'items')
    """

    tabla_mongo = Modelo['modelo']["entidad"]['tabla']
    print("tabla_mongo >>>", tabla_mongo)

    campos_mongo = Modelo['modelo']["campos"]
    print("campos_mongo >>>", campos_mongo)

    cursor = mysql.cursor()

    # 🔹 2. Ver si la tabla existe
    cursor.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        AND table_name = %s
    """, (tabla_mongo,))
    existe = cursor.fetchone()[0] == 1
    print("existe >>>", existe)

    # 🔹 3. Crear tabla si no existe
    if not existe:
        columnas = []
        for campo in campos_mongo:
            columnas.append(mongo_field_to_sql(campo))

        sql = f"""
            CREATE TABLE {tabla_mongo} (
                {", ".join(columnas)}
            ) ENGINE=InnoDB
        """
        print("sql >>>", sql)

        cursor.execute(sql)
        mysql.commit()
        print(f"✅ Tabla creada: {tabla_mongo}")
        return

    # 🔹 4. Comparar columnas
    columnas_sql = get_mysql_columns(cursor, tabla_mongo)
    print("columnas_sql >>>", columnas_sql)

    for campo in campos_mongo:
        nombre = campo["nombre"]

        # FK → nombre_id
        if campo["tipo"] == "fk":
            nombre = f"{nombre}_id"

        if nombre not in columnas_sql:
            sql_campo = mongo_field_to_sql({**campo, "nombre": nombre})
            cursor.execute(f"ALTER TABLE {tabla_mongo} ADD COLUMN {sql_campo}")
            print(f"➕ Columna agregada: {nombre}")

    mysql.commit()
    print(f"🔄 Tabla sincronizada: {tabla_mongo}")
    modulos = obtener_modulos_empresa(empresa)

    return render(request, "core/home.html", {
        "empresa": empresa,
        "modulos": modulos
    })




def get_mysql_columns(cursor, table_name):
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    return {row[0]: row for row in cursor.fetchall()}



@login_required
def cargar_formulario_consulta(request, modulo, id):
    empresa = empresa_activa(request)

    if not empresa:
        return render(request, "modulos/consulta.html", {
            "error": "No hay empresa activa"
        })

    # 🔹 Mongo (estructura)
    mongo = get_mongo_empresa(empresa)

    config = mongo.modulos.find_one({"_id": modulo})
    if not config:
        return render(request, "modulos/consulta.html", {
            "error": "Módulo no existe"
        })

    Modelo = mongo.modelos.find_one({"modulo": config["_id"]})
    if not Modelo:
        return render(request, "modulos/consulta.html", {
            "error": "Modelo no existe"
        })
        
    campos_activos = Modelo["modelo"]["campos"]
    tablaNombre = Modelo["modelo"]["entidad"]["tabla"]
    FormClass = build_dynamic_form(campos_activos)

    # ======================
    # 📌 POST
    # ======================
    if request.method == "POST":
        form = FormClass(request.POST)

        if form.is_valid():

            columnas = []
            valores = []

            for campo in campos_activos:
                nombre = campo["nombre"]
                tipo = campo["tipo"]

                if nombre not in form.cleaned_data:
                    continue

                valor = form.cleaned_data[nombre]

                if valor in ("", None):
                    continue

                if tipo == "fk":
                    valor = valor.id

                if tipo == "boolean":
                    valor = 1 if valor else 0

                columnas.append(nombre)
                valores.append(valor)

            mysql = pymysql.connect(
                host=empresa.sql_url,
                user=empresa.sql_user,
                password=empresa.sql_clave,
                database=empresa.sql_db,
                charset="utf8mb4",
                autocommit=False
            )
            try:
                cursor = mysql.cursor()

                if id > 0:
                    set_sql = ", ".join([f"{c}=%s" for c in columnas])
                    sql = f"""
                        UPDATE {tablaNombre}
                        SET {set_sql}
                        WHERE id = %s
                    """
                    valores.append(id)
                else:
                    campos_sql = ", ".join(columnas)
                    placeholders = ", ".join(["%s"] * len(valores))
                    sql = f"""
                        INSERT INTO {tablaNombre}
                        ({campos_sql})
                        VALUES ({placeholders})
                    """

                cursor.execute(sql, valores)
                mysql.commit()

            except Exception as e:
                mysql.rollback()
                raise e

            finally:
                mysql.close()

            return render(request, "modulos/consulta.html", {
                "form": FormClass(),
                "titulo": config["nombre"],
                "modulo": modulo,
                "success": "Registro guardado correctamente"
            })
    else:
        if id >0:
            # EDITAR / CONSULTAR REGISTRO EXISTENTE
            mysql = pymysql.connect(
                host=empresa.sql_url,
                user=empresa.sql_user,
                password=empresa.sql_clave,
                database=empresa.sql_db,
                cursorclass=pymysql.cursors.DictCursor
            )

            cursor = mysql.cursor()

            sql = f"SELECT * FROM {tablaNombre} WHERE id = %s"
            cursor.execute(sql, (id,))
            registro = cursor.fetchone()

            cursor.close()
            mysql.close()

            if not registro:
                return render(request, "modulos/consulta.html", {
                    "error": "Registro no encontrado",
                    "titulo": config["nombre"],
                    "modulo": modulo
                })

            # Preparar datos iniciales del formulario
            initial_data = {}

            for campo in campos_activos:
                nombre = campo["nombre"]
                tipo = campo["tipo"]

                if nombre not in registro:
                    continue

                valor = registro[nombre]

                # Ajustes por tipo
                if tipo == "boolean":
                    valor = bool(valor)

                initial_data[nombre] = valor
            form = FormClass(initial=initial_data)
        else:
            form = FormClass()
  
    return render(request, "modulos/consulta.html", {
        "form": form,
        "titulo": config["nombre"],
        "modulo": modulo
    })