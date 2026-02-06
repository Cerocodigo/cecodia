
import pymysql


from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import transaction, connection
from django.urls import reverse

from datetime import datetime

from .forms import SignupForm
from .models import Empresa, UsuarioEmpresa
from .dynamic_form import build_dynamic_form

from .datosCliente import *


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
        FormCabecera = build_dynamic_form(modelo_cab["campos"], empresa)
        form_cab = FormCabecera(request.POST)

        # === DETALLES ===
        forms_detalle = []
        for det in modelos_det:
            FormDet = build_dynamic_form(det["campos"], empresa)
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
        FormCabecera = build_dynamic_form(modelo_cab["campos"], empresa)

        FormsDetalle = []
        for i, det in enumerate(modelos_det):
            campos = det["campos"]
            FormsDetalle.append({
                "modelo_id": det["_id"],
                "entidad": det["tabla"],
                "form": build_dynamic_form(campos, empresa)
            })


        return render(request, "modulos/moduloNuevo.html", {
            "form": FormCabecera(),
            "formularios_detalle": [
            {
                "entidad": f["entidad"],
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

    print("Modelos >>>", Modelos)

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
    print("modulo >>>", modulo)
    empresa = empresa_activa(request)
    print("empresa >>>", empresa)

    if not empresa:
        return render(request, "modulos/moduloMenu.html", {
            "error": "No hay empresa activa"
        })

    db = get_mongo_empresa(empresa)
    print("db get_mongo_empresa >>>", db)

    #Modulo
    config = db.modulos.find_one({"_id": modulo})
    print("config >>>", config)

    if not config:
        return render(request, "modulos/moduloMenu.html", {
            "error": "Módulo no existe"
        })
    
    #Modelo
    #Modelo = db.modelos.find_one({"modulo": config['_id']})
    Modelos = list(db.modelos.find({"modulo": config['_id']}))

    print("Modelos >>>", Modelos)

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
        print("modeloIA >>" , modeloIA_cab)
        if modelosIA_det != None:
            modelosIA_det = interpretar_prompt(prompt, modelos_det[0]["campos"])
            print("modeloIA_cab >>" , modelosIA_det)

    FormCabecera = build_dynamic_form(modeloIA_cab if modeloIA_cab else modelo_cab["campos"], empresa)

    FormsDetalle = []
    for i, det in enumerate(modelos_det):
        campos = (modelosIA_det[i]["campos"] if prompt else det["campos"])
        FormsDetalle.append({
            "modelo_id": det["_id"],
            "entidad": det["tabla"],
            "form": build_dynamic_form(campos, empresa)
        })

    print("FormCabecera >>>", FormCabecera)
    print("FormsDetalle >>>", FormsDetalle)

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
    print(" modulo >>> " ,  modulo)

    resultado = pregarga_modulo(request, modulo)
    if resultado["estado"] is False:
        return render(request, "modulos/moduloNuevo.html", {
            "error": resultado["msg"]
        })

    empresa = resultado["empresa"]
    db = resultado["mongo"]
    print("  aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa " )

    #Modelo
    modelos = list(db.modelos.find({
            "modulo": modulo,
            "activo": True
        }))
    print(" modelos >>> " ,  modelos)
    print("  bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb " )

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
        print("sincro tabla")
        tabla_cab = cabecera["tabla"]
        campos_cab = cabecera["campos"]

        print("🔷 Cabecera:", tabla_cab)
        sincronizar_tabla(cursor, mysql, tabla_cab, campos_cab)
        # =========================
        # 🔹 SINCRONIZAR DETALLES
        # =========================
        for det in detalles:
            tabla_det = det["tabla"]
            campos_det = det["campos"]

            print("🔷 Detalle:", tabla_det)
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
            FormCab = build_dynamic_form(campos_cab, empresa)
            form_cab = FormCab(request.POST)

            forms_detalle = []
            for det in modelos_det:
                FormDet = build_dynamic_form(det["campos"], empresa)
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

        FormCab = build_dynamic_form(campos_cab, empresa)

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

            FormDet = build_dynamic_form(det["campos"], empresa)
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
