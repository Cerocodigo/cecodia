
import pymysql
import json


from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction, connection
from django.urls import reverse
from django.http import JsonResponse


from datetime import datetime

from .forms import SignupForm
from .models import Empresa, UsuarioEmpresa
from .dynamic_form import build_dynamic_form

from .datosCliente import *


from core.utils import empresa_activa
from motor.loader import obtener_modulos_empresa
from motor.mongo import get_mongo_empresa, mongo_field_to_sql  # ✅ IMPORT FALTANTE
from core.ia import interpretar_prompt


import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from datetime import datetime

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "core/home.html"

@login_required
def subir_archivo(request):

    if request.method == "POST":

        archivo = request.FILES.get("archivo")
        empresa = request.POST.get("empresa")

        carpeta = os.path.join(settings.MEDIA_ROOT, "uploads", empresa)

        if not os.path.exists(carpeta):
            os.makedirs(carpeta)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        nombre = f"{timestamp}_{archivo.name}"

        ruta = os.path.join(carpeta, nombre)

        with open(ruta, "wb+") as destino:
            for chunk in archivo.chunks():
                destino.write(chunk)

        ruta_db = f"uploads/{empresa}/{nombre}"

        return JsonResponse({
            "estado": True,
            "ruta": ruta_db,
            "url": settings.MEDIA_URL + ruta_db
        })
    return JsonResponse({"estado": False})

@login_required
def calculosReferenciaBuscador(request, modelo, campo):
    print("calculosCampos - calculosReferenciaBuscador")

    empresa = empresa_activa(request)
    if not empresa:
        return JsonResponse({"estado": False, "msg": "empresa no existe"})

    db = get_mongo_empresa(empresa)

    # 1️⃣ Buscar modelo
    modelo_conf = db.modelos.find_one({"_id": modelo})
    print("modelo_conf >>>", modelo_conf)

    if not modelo_conf:
        return JsonResponse({"estado": False, "msg": "modelo no encontrado"})

    # 2️⃣ Buscar campo
    campo_conf = next(
        (c for c in modelo_conf.get("campos", []) if c.get("nombre") == campo),
        None
    )
    print("campo_conf >>>", campo_conf)

    if not campo_conf:
        return JsonResponse({"estado": False, "msg": "campo no existe en el modelo"})

    # 3️⃣ Verificar tipo funcional
    if campo_conf.get("tipo_funcional") != "ReferenciaBuscador":
        return JsonResponse({
            "estado": True,
            "msg": "campo no es ReferenciaBuscador",
            "valor": None
        })

    print('Analisis ReferenciaBuscador')
    config = campo_conf.get("configuracion", {})
    print("config >>>", config)
    sql_template = config.get("sql")
    if len(request.body) >0:
        variables_valores =  json.loads(request.body.decode("utf-8"))
        variables_conf =  config.get("parametros")
    else:
        variables_valores= []
        variables_conf =  None

    
    print('sql_template >>>>' , sql_template)
    
    print('variables_conf >>>>' , variables_conf)


    if not sql_template:
        return JsonResponse({
            "estado": False,
            "msg": "SQL no definido en configuración"
        })

    # 4️⃣ Resolver variables
    sql = sql_template

    if variables_conf:
        # formato soportado: "@Var@=CampoFormulario"
        pares = variables_conf.split(",")
        for par in pares:
            print('par >>>', par)
            var_sql, campo_origen = par.split("=")
            valor = variables_valores[campo_origen]
            print("valor >>>", valor)
            if valor is None:
                return JsonResponse({
                    "estado": False,
                    "msg": f"valor no enviado para {campo_origen}"
                })

            sql = sql.replace(var_sql, str(valor))
            

    q = request.GET.get("q")
    qq = ' and ('
    
    Campos_filtros = config.get("campos_filtrables")
    if len(q)>0:
        for campo in Campos_filtros:
            qq = qq + '' + campo+ ' like "%' + q + '%" or ' 
        qq = qq[:-3] + ')'
        sql = sql + qq

    print("Ejecutar SQL >>>", sql)

    # 5️⃣ Ejecutar SQL
    try:
        conn = pymysql.connect(
            host=empresa.sql_url,
            user=empresa.sql_user,
            password=empresa.sql_clave,
            database=empresa.sql_db,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )

        with conn.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()

        conn.close()

        return JsonResponse({
            "estado": True,
            "resultados": rows,
            "Campos_filtros":Campos_filtros
        })

    except Exception as e:
        return JsonResponse({
            "estado": False,
            "msg": "Error ejecutando SQL",
            "error": str(e)
        })



@login_required
def calculosQueryBaseDatos(request, modelo, campo):
    print("calculosCampos - QueryBaseDatos")

    empresa = empresa_activa(request)
    if not empresa:
        return JsonResponse({"estado": False, "msg": "empresa no existe"})

    db = get_mongo_empresa(empresa)

    # 1️⃣ Buscar modelo
    modelo_conf = db.modelos.find_one({"_id": modelo})
    print("modelo_conf >>>", modelo_conf)

    if not modelo_conf:
        return JsonResponse({"estado": False, "msg": "modelo no encontrado"})

    # 2️⃣ Buscar campo
    campo_conf = next(
        (c for c in modelo_conf.get("campos", []) if c.get("nombre") == campo),
        None
    )
    print("campo_conf >>>", campo_conf)

    if not campo_conf:
        return JsonResponse({"estado": False, "msg": "campo no existe en el modelo"})

    # 3️⃣ Verificar tipo funcional
    if campo_conf.get("tipo_funcional") != "QueryBaseDatos":
        return JsonResponse({
            "estado": True,
            "msg": "campo no es QueryBaseDatos",
            "valor": None
        })

    print('Analisis')
    config = campo_conf.get("configuracion", {})
    print("config >>>", config)
    sql_template = config.get("query")['sql']
    variables_valores =  json.loads(request.body.decode("utf-8"))
    variables_conf =  config.get("parametros")

    
    print('sql_template >>>>' , sql_template)
    
    print('variables_conf >>>>' , variables_conf)


    if not sql_template:
        return JsonResponse({
            "estado": False,
            "msg": "SQL no definido en configuración"
        })

    # 4️⃣ Resolver variables
    sql = sql_template

    if variables_conf:
        # formato soportado: "@Var@=CampoFormulario"
        pares = variables_conf.split(",")
        for par in pares:
            print('par >>>', par)
            var_sql, campo_origen = par.split("=")
            valor = variables_valores[campo_origen]
            print("valor >>>", valor)
            if valor is None:
                return JsonResponse({
                    "estado": False,
                    "msg": f"valor no enviado para {campo_origen}"
                })

            sql = sql.replace(var_sql, str(valor))

    print("SQL >>>", sql)

    # 5️⃣ Ejecutar SQL
    try:
        conn = pymysql.connect(
            host=empresa.sql_url,
            user=empresa.sql_user,
            password=empresa.sql_clave,
            database=empresa.sql_db,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )

        with conn.cursor() as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()

        conn.close()

        valor = list(row.values())[0] if row else None

        return JsonResponse({
            "estado": True,
            "tipo": "QueryBaseDatos",
            "campo": campo,
            "valor": valor
        })

    except Exception as e:
        return JsonResponse({
            "estado": False,
            "msg": "Error ejecutando SQL",
            "error": str(e)
        })



@login_required
def calculosCampos(request, modelo, campo):
    empresa = empresa_activa(request)
    if not empresa:
        return JsonResponse({"estado": False, "msg": "empresa no existe"})

    db = get_mongo_empresa(empresa)

    # 1️⃣ Buscar modelo
    modelo_conf = db.modelos.find_one({"_id": modelo})
    
    if not modelo_conf:
        return JsonResponse({"estado": False, "msg": "modelo no encontrado"})

    # 2️⃣ Buscar campo dentro del modelo
    campo_conf = next(
        (c for c in modelo_conf.get("campos", []) if c.get("nombre") == campo),
        None
    )

    if not campo_conf:
        return JsonResponse({"estado": False, "msg": "campo no existe en el modelo"})

    # 3️⃣ Verificar tipo
    if campo_conf.get("tipo_funcional") != "NumeroSecuencial":
        return JsonResponse({
            "estado": True,
            "msg": "campo no es secuencial",
            "valor": None
        })

    campo = campo_conf.get("nombre")
    tabla = modelo_conf.get("tabla")
    sql = f"""
        SELECT COALESCE(MAX({campo}), 0) AS actual
        FROM {tabla}
    """
    try:
        conn = pymysql.connect(
            host=empresa.sql_url,
            user=empresa.sql_user,
            password=empresa.sql_clave,
            database=empresa.sql_db,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )

        with conn.cursor() as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()

        conn.close()

        actual = row["actual"] if row and row["actual"] is not None else 0
        siguiente = actual + 1

        return JsonResponse({
            "estado": True,
            "tipo": "NumeroSecuencial",
            "campo": campo,
            "tabla": tabla,
            "actual": actual,
            "siguiente": siguiente
        })

    except Exception as e:
        return JsonResponse({
            "estado": False,
            "msg": "Error ejecutando SQL",
            "error": str(e)
        })



def home(request):
    empresa = empresa_activa(request)
    print("empresa >>>", empresa)

    modulos = []
    if empresa:
        modulos = obtener_modulos_empresa(empresa)

    print("MODULOS >>>", modulos)

    return render(request, "core/home.html", {
        "empresa": empresa,
        "modulos": modulos,
        "usuario":request.user
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


def pregarga_modulo(request, modulo):

    empresa = empresa_activa(request)
    
    print("empresa >>>", empresa)
    if not empresa:
        return({"estado":False, "msg":"empresa no existe"})

    db = get_mongo_empresa(empresa)

    #Modulo
    modulo = db.modulos.find_one({"_id": modulo})

    if not modulo:
        return({"estado":False, "msg":"Módulo no existe"})
    
    #Modelo
    #Modelos = list(db.modelos.find({"modulo": modulo['_id']}))
    return {"estado":True, "empresa":empresa, "mongo":db, "modulo":modulo}



@login_required
def cargar_modulo_nuevo(request, modulo):
    resultado = pregarga_modulo(request, modulo)
    if resultado['estado'] == False:
        return render(request, "modulos/moduloNuevo.html", {
            "error":  resultado['msg']
        })

    empresa = resultado["empresa"]

    db =  resultado["mongo"]
    modulo = resultado["modulo"]
    
    #Modelo
    Modelos = list(db.modelos.find({"modulo": modulo['_id']}))

    modelo_cab = None
    modelos_det = []

    for m in Modelos:
        entidad = m["tabla"]
        rol = m["rol"]

        if rol == "cabecera":
            modelo_cab = m
        elif rol == "detalle":
            modelos_det.append(m)

    if not modelo_cab:
        return render(request, "modulos/moduloMain.html", {
            "error": "No existe entidad cabecera"
        })

    #filtro
    if request.method == "POST":
        # === CABECERA ===
        FormCabecera = build_dynamic_form(modelo_cab["campos"], empresa, modelo_cab["_id"])
        form_cab = FormCabecera(request.POST)

        # === DETALLES ===


        forms_detalle = []
        for det in modelos_det:
            FormDet = build_dynamic_form(det["campos"], empresa, det["_id"])
            form_det = FormDet(request.POST, prefix=str(det["_id"]))
            forms_detalle.append({
                "modelo": det,
                "form": form_det
            })

        # === VALIDACIÓN GENERAL ===
        if not form_cab.is_valid() or any(not f["form"].is_valid() for f in forms_detalle):
            return render(request, "modulos/moduloNuevo.html", {
                "form": form_cab,
                "formularios_detalle": [
                    {
                        "id": f["modelo"]["_id"],
                        "display": f["modelo"]["display"],
                        "entidad": f["modelo"]["tabla"],
                        "form": f["form"]
                    } for f in forms_detalle
                ],
                "titulo": modulo["nombre"],
                "modulo": modulo,
                "empresa": empresa,
                "usuario": request.user,
                "error": "Corrige los errores del formulario"
            })

        # ================= TRANSACCIÓN MYSQL =================
        mysql = pymysql.connect(
            host=empresa.sql_url,
            user=empresa.sql_user,
            password=empresa.sql_clave,
            database=empresa.sql_db,
            autocommit=False
        )

        cursor = mysql.cursor()
        try:
            # ========= CABECERA =========
            campos = []
            valores = []

            for k, v in form_cab.cleaned_data.items():
                campos.append(k)
                valores.append(v)

            sql = f"""
                INSERT INTO {modelo_cab['tabla']}
                ({','.join(campos)})
                VALUES ({','.join(['%s'] * len(valores))})
            """

            cursor.execute(sql, valores)
            idregistro = cursor.lastrowid

            # ========= DETALLES =========
            for f in forms_detalle:
                modelo_det = f["modelo"]
                fk_field = modelo_det["fk"]

                campos = []
                valores = []

                for k, v in f["form"].cleaned_data.items():
                    campos.append(k)
                    valores.append(v)

                campos.append(fk_field)
                valores.append(idregistro)

                sql = f"""
                    INSERT INTO {modelo_det['tabla']}
                    ({','.join(campos)})
                    VALUES ({','.join(['%s'] * len(valores))})
                """

                cursor.execute(sql, valores)

            # ✅ TODO OK
            mysql.commit()

        except Exception as e:
            mysql.rollback()
            raise e

        finally:
            cursor.close()
            mysql.close()

        # ========= REDIRECCIÓN =========
        return redirect(
            "modulo_form",
            modulo=modulo["_id"],
            id=idregistro
        )
    
    if request.method == "GET":
        FormCabecera = build_dynamic_form(modelo_cab["campos"], empresa, modelo_cab["_id"])

        FormsDetalle = []
        for i, det in enumerate(modelos_det):
            campos = det["campos"]
            FormsDetalle.append({
                "modelo_id": det["_id"],
                "entidad": det["tabla"],
                "display": det["display"],
                "form": build_dynamic_form(campos, empresa, det["_id"])
            })


        return render(request, "modulos/moduloNuevo.html", {
            "form": FormCabecera(),
            "formularios_detalle": [
            {
                "modelo_id": f["modelo_id"],
                "entidad": f["entidad"],
                "display": f["display"],
                "form": f["form"]()
            } for f in FormsDetalle
        ],
            "titulo": modulo["nombre"],
            "modulo": modulo,
            "success": "estructura actualizada correctamente",    
            "empresa": empresa,
            "usuario":request.user,
            "moduloId": modulo['_id'],

            
        })
           

@login_required
def cargar_modulo_main(request, modulo):
    resultado = pregarga_modulo(request, modulo)

    if resultado['estado'] == False:
        return render(request, "modulos/moduloMenu.html", {
            "error":  resultado['msg']
        })
    empresa = resultado["empresa"]
    db =  resultado["mongo"]
    modulo = resultado["modulo"]
    
    #Modelo
    Modelos = list(db.modelos.find({"modulo": modulo['_id']}))


    modelo_cab = None
    modelos_det = []

    for m in Modelos:
        entidad = m["tabla"]
        rol = m["rol"]

        if rol == "cabecera":
            modelo_cab = m
        elif rol == "detalle":
            modelos_det.append(m)

    if not modelo_cab:
        return render(request, "modulos/moduloMain.html", {
            "error": "No existe entidad cabecera"
        })

    #filtro
    if request.method == "POST":
        pass
    
    if request.method == "GET":
        ListadoDatos = viewbasemodulo(modelo_cab, modulo, empresa )

    # 🔹 GET
    return render(request, "modulos/moduloMain.html", {
        "titulo": modulo["nombre"],
        "modulo": modulo,
        "ListadoDatos": ListadoDatos,
        "empresa": empresa,
        "modulo_id":modulo['_id'],
        "usuario":request.user
    })


@login_required
def cargar_formulario_modulo(request, modulo):
    empresa = empresa_activa(request)

    if not empresa:
        return render(request, "modulos/moduloMenu.html", {
            "error": "No hay empresa activa"
        })

    db = get_mongo_empresa(empresa)
    config = db.modulos.find_one({"_id": modulo})

    if not config:
        return render(request, "modulos/moduloMenu.html", {
            "error": "Módulo no existe"
        })
    
    #Modelo
    #Modelo = db.modelos.find_one({"modulo": config['_id']})
    Modelos = list(db.modelos.find({"modulo": config['_id']}))


    modelo_cab = None
    modelos_det = []

    for m in Modelos:
        entidad = m["tabla"]
        rol = m["rol"]

        if rol == "cabecera":
            modelo_cab = m
        elif rol == "detalle":
            modelos_det.append(m)

    if not modelo_cab:
        return render(request, "modulos/moduloMenu.html", {
            "error": "No existe entidad cabecera"
        })

    modeloIA_cab = None
    modelosIA_det = None   

    prompt = request.GET.get("prompt", "")
    if prompt:
        # 🔮 FUTURO: aquí se enviará a IA
        modeloIA_cab = interpretar_prompt(prompt, modelo_cab["campos"])
        if modelosIA_det != None:
            modelosIA_det = interpretar_prompt(prompt, modelos_det[0]["campos"])

    FormCabecera = build_dynamic_form(modeloIA_cab if modeloIA_cab else modelo_cab["campos"], empresa, modelo_cab["_id"])

    FormsDetalle = []
    for i, det in enumerate(modelos_det):
        campos = (modelosIA_det[i]["campos"] if prompt else det["campos"])
        FormsDetalle.append({
            "modelo_id": det["_id"],
            "entidad": det["tabla"],
            "form": build_dynamic_form(campos, empresa, det["_id"])
        })



    if request.method == "POST":

        if FormCabecera.is_valid():

            # 🔹 guardar cambios del modelo IA (si existen)
            if modeloIA_cab:
                db.modelos.update_one(
                    {"_id": modelo_cab["_id"]},
                    {"$set": {"modelo.campos": modeloIA_cab}}
                )
            if modelosIA_det:
                db.modelos.update_one(
                    {"_id": modelos_det["_id"]},
                    {"$set": {"modelo.campos": modelosIA_det}}
                )

            return render(request, "modulos/formulario.html", {
                "form": FormCabecera(),
                "formularios_detalle": [
                {
                    "entidad": f["entidad"],
                    "form": f["form"]()
                } for f in FormsDetalle
            ],
                "titulo": config["nombre"],
                "modulo": modulo,
                "success": "estructura actualizada correctamente"
            })
           

    # 🔹 GET
    return render(request, "modulos/formulario.html", {
        "titulo": config["nombre"],
        "modulo": modulo,
        "form": FormCabecera(),
        "formularios_detalle": [
            {
                "entidad": f["entidad"],
                "form": f["form"]()
            } for f in FormsDetalle
        ]
    })


@login_required
def actualiazarBd(request, modulo):

    resultado = pregarga_modulo(request, modulo)
    if resultado["estado"] is False:
        return render(request, "modulos/moduloNuevo.html", {
            "error": resultado["msg"]
        })

    empresa = resultado["empresa"]
    db = resultado["mongo"]

    #Modelo
    modelos = list(db.modelos.find({
            "modulo": modulo,
            "activo": True
        }))


    if not modelos:
        return render(request, "modulos/formulario.html", {
            "error": "No hay modelos definidos para el módulo"
        })
    cabecera = None
    detalles = []

    for m in modelos:
        rol = m.get("rol")
        if rol == "cabecera":
            cabecera = m
        elif rol == "detalle":
            detalles.append(m)

    if not cabecera:
        return render(request, "modulos/formulario.html", {
            "error": "El módulo no tiene entidad cabecera"
        })


    # 🔹 Conexión MySQL / MariaDB
    mysql = pymysql.connect(
        host=empresa.sql_url,
        user=empresa.sql_user,
        password=empresa.sql_clave,
        database=empresa.sql_db,
        autocommit=False
    )

    cursor = mysql.cursor()

    try:
        # =========================
        # 🔹 SINCRONIZAR CABECERA
        # =========================
        tabla_cab = cabecera["tabla"]
        campos_cab = cabecera["campos"]

        sincronizar_tabla(cursor, mysql, tabla_cab, campos_cab)
        # =========================
        # 🔹 SINCRONIZAR DETALLES
        # =========================
        for det in detalles:
            tabla_det = det["tabla"]
            campos_det = det["campos"]
            sincronizar_tabla(cursor, mysql, tabla_det, campos_det)

        mysql.commit()
        print("✅ Base de datos sincronizada correctamente")

    except Exception as e:
        mysql.rollback()
        print("❌ Error:", str(e))

        return render(request, "modulos/formulario.html", {
            "error": str(e)
        })

    finally:
        cursor.close()
        mysql.close()

    # 🔹 Volver al home
    modulos = obtener_modulos_empresa(empresa)

    return render(request, "core/home.html", {
        "empresa": empresa,
        "modulos": modulos
    })



def sincronizar_tabla(cursor, mysql, tabla, campos):
    # 1. Ver si la tabla existe
    cursor.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        AND table_name = %s
    """, (tabla,))
    existe = cursor.fetchone()[0] == 1

    # 2. Crear tabla
    if not existe:
        columnas = []
        for campo in campos:
            print("campo >>", campo, '  --  ' , mongo_field_to_sql(campo)  )
            columnas.append(mongo_field_to_sql(campo))


        sql = f"""
            CREATE TABLE {tabla} (
                {", ".join(columnas)}
            ) ENGINE=InnoDB
        """
        print("sql >>>", sql)
        cursor.execute(sql)
        mysql.commit()
        print(f"✅ Tabla creada: {tabla}")
        return

    # 3. Comparar columnas
    columnas_sql = get_mysql_columns(cursor, tabla)

    for campo in campos:
        nombre = campo["nombre"]

        if campo["tipo"] == "fk":
            nombre = f"{nombre}_id"

        if nombre not in columnas_sql:
            sql_campo = mongo_field_to_sql({**campo, "nombre": nombre})
            cursor.execute(
                f"ALTER TABLE {tabla} ADD COLUMN {sql_campo}"
            )
            print(f"➕ Columna agregada: {tabla}.{nombre}")

    mysql.commit()
    print(f"🔄 Tabla sincronizada: {tabla}")



def get_mysql_columns(cursor, table_name):
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    return {row[0]: row for row in cursor.fetchall()}


@login_required
def cargar_formulario_consulta(request, modulo, id):

    resultado = pregarga_modulo(request, modulo)
    if resultado["estado"] is False:
        return render(request, "modulos/moduloNuevo.html", {
            "error": resultado["msg"]
        })

    empresa = resultado["empresa"]
    db = resultado["mongo"]
    modulo_conf = resultado["modulo"]

    # ================= METADATA =================
    Modelo = db.modelos.find_one({
        "modulo": modulo_conf["_id"],
        "rol": "cabecera",
        "activo": True
    })

    modelos_det = list(db.modelos.find({
        "modulo": modulo_conf["_id"],
        "rol": "detalle",
        "activo": True
    }))

    tabla_cab = Modelo["tabla"]
    pk = Modelo["pk"]
    campos_cab = [c for c in Modelo["campos"] if c.get("activo", True)]
    cab_id = Modelo["_id"]

    # ================= MYSQL =================
    mysql = pymysql.connect(
        host=empresa.sql_url,
        user=empresa.sql_user,
        password=empresa.sql_clave,
        database=empresa.sql_db,
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor
    )

    cursor = mysql.cursor()

    try:
        # =====================================================
        # ======================= POST =======================
        # =====================================================
        if request.method == "POST":

            accion = request.POST.get("accion")

            # ---------- DELETE ----------
            if accion == "eliminar":

                for det in modelos_det:
                    sql = f"DELETE FROM {det['tabla']} WHERE {det['fk']} = %s"
                    cursor.execute(sql, (id,))

                sql = f"DELETE FROM {tabla_cab} WHERE {pk} = %s"
                cursor.execute(sql, (id,))

                mysql.commit()

                return redirect(
                    "modulo_form",
                    modulo=modulo_conf["_id"]
                )

            # ---------- UPDATE ----------
            FormCab = build_dynamic_form(campos_cab, empresa, cab_id)
            form_cab = FormCab(request.POST)

            forms_detalle = []
            for det in modelos_det:
                FormDet = build_dynamic_form(det["campos"], empresa, det["_id"])
                i = 0
                while f"{det['tabla']}_{i}-" in "".join(request.POST.keys()):
                    forms_detalle.append({
                        "modelo": det,
                        "form": FormDet(
                            request.POST,
                            prefix=f"{det['tabla']}_{i}"
                        )
                    })
                    i += 1

            if not form_cab.is_valid() or any(not f["form"].is_valid() for f in forms_detalle):
                return render(request, "modulos/moduloNuevo.html", {
                    "form": form_cab,
                    "formularios_detalle": formularios_detalle,
                    "titulo": modulo_conf["nombre"],
                    "modulo": modulo_conf,
                    "id": id,
                    "error": "Corrige los errores del formulario"
                })

            # ---- UPDATE CABECERA ----
            sets = []
            valores = []

            for campo in campos_cab:
                nombre = campo["nombre"]
                if campo.get("editable", True):
                    sets.append(f"{nombre} = %s")
                    valores.append(form_cab.cleaned_data.get(nombre))

            valores.append(id)

            sql = f"""
                UPDATE {tabla_cab}
                SET {', '.join(sets)}
                WHERE {pk} = %s
            """

            cursor.execute(sql, valores)

            # ---- DELETE + INSERT DETALLES ----
            for det in modelos_det:
                sql = f"DELETE FROM {det['tabla']} WHERE {det['fk']} = %s"
                cursor.execute(sql, (id,))

            for f in forms_detalle:
                modelo_det = f["modelo"]
                fk = modelo_det["fk"]

                campos = []
                valores = []

                for k, v in f["form"].cleaned_data.items():
                    campos.append(k)
                    valores.append(v)

                campos.append(fk)
                valores.append(id)

                sql = f"""
                    INSERT INTO {modelo_det['tabla']}
                    ({','.join(campos)})
                    VALUES ({','.join(['%s'] * len(valores))})
                """
                cursor.execute(sql, valores)

            mysql.commit()

            return redirect(
                "modulo_form",
                modulo=modulo_conf["_id"],
                id=id
            )

        # =====================================================
        # ======================= GET ========================
        # =====================================================

        sql = f"SELECT * FROM {tabla_cab} WHERE {pk} = %s"
        cursor.execute(sql, (id,))
        registro = cursor.fetchone()

        if not registro:
            return render(request, "modulos/consulta.html", {
                "error": "Registro no encontrado",
                "titulo": modulo_conf["nombre"],
                "modulo": modulo_conf
            })

        FormCab = build_dynamic_form(campos_cab, empresa, cab_id)

        initial_cab = {}
        for campo in campos_cab:
            nombre = campo["nombre"]
            if nombre in registro:
                valor = registro[nombre]
                if campo.get("tipo_funcional") == "boolean":
                    valor = bool(valor)
                initial_cab[nombre] = valor

        form_cab = FormCab(initial=initial_cab)

        formularios_detalle = []

        for det in modelos_det:
            sql = f"SELECT * FROM {det['tabla']} WHERE {det['fk']} = %s"
            cursor.execute(sql, (id,))
            rows = cursor.fetchall() or []

            FormDet = build_dynamic_form(det["campos"], empresa, det['_id'])
            forms = []

            for i, row in enumerate(rows):
                forms.append(
                    FormDet(initial=row, prefix=f"{det['tabla']}_{i}")
                )

            if not forms:
                forms.append(FormDet(prefix=f"{det['tabla']}_0"))

            formularios_detalle.append({
                "entidad": det["tabla"],
                "forms": forms
            })

    except Exception as e:
        mysql.rollback()
        raise e

    finally:
        cursor.close()
        mysql.close()

    return render(request, "modulos/moduloNuevo.html", {
        "form": form_cab,
        "formularios_detalle": formularios_detalle,
        "titulo": modulo_conf["nombre"],
        "moduloId": modulo_conf["_id"],
        "modulo": modulo_conf,
        "id": id
    })
