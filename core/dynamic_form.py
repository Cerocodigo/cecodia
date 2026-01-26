from django import forms
from django.forms import widgets

BASE_FIELD_TYPES  = {
    "string": forms.CharField,
    "char": forms.CharField,
    "decimal": forms.DecimalField,
    "int": forms.IntegerField,
    "email": forms.EmailField,
    "boolean": forms.BooleanField,
    "date": forms.DateField,
    "datetime": forms.DateTimeField,
    "fecha": forms.DateField,
    
}


FIELD_TYPES = {
    "string": forms.CharField,
    "char": forms.CharField,
    "decimal": forms.DecimalField,
    "int": forms.IntegerField,
    "email": forms.EmailField,
    "boolean": forms.BooleanField,
    "date": forms.DateField,
    "datetime": forms.DateTimeField,
    "fecha": forms.DateField,
    
}

UI_FIELD_TYPES = {
    "image": forms.ImageField,
    "file": forms.FileField,
}
FK_FIELD_TYPES = {
    "fk": forms.ModelChoiceField
}

def build_dynamic_form(campos, empresa):
    form_fields = {}
    campos = sorted(campos, key=lambda c: c.get("orden", 1000))

    for campo in campos:
        nombre = campo.get("nombre")
        etiqueta = campo.get("etiqueta", nombre)
        tipo_base = campo.get("tipo_base")
        tipo_funcional = campo.get("tipo_funcional")
        requerido = campo.get("requerido", False)
        configuracion = campo.get("configuracion", {})
        validacion = campo.get("validacion", {})

        # layout metadata
        col = campo.get("col", 3)
        gap = campo.get("gap", 0)
        gap_top = campo.get("gap_top", 0)
        break_line = campo.get("break", False)
        area = campo.get("area", "main")

        # campos que no se renderizan
        if tipo_funcional in (
            "NumeroSecuencial",
            "SistemaFecha",
            "SistemaUsuario",
            "Operacion",
            "FormulaDetalle",
            "ReferenciaAdjunto",
        ):
            continue

        # 🔽 OPCIÓN MÚLTIPLE
        if tipo_funcional == "OpcionMultiple":
            opciones = configuracion.get("opciones", [])
            labels = configuracion.get("labels", {})
            choices = [(op, labels.get(op, op)) for op in opciones]
            print("opciones>> ",opciones)
            print("labels>> ",labels)

            print("choices>> ",choices)
            

            form_fields[nombre] = forms.ChoiceField(
                label=etiqueta,
                choices=choices,
                required=requerido,
                initial=configuracion.get("valor_predeterminado"),
                widget=forms.Select(attrs={
                    "class": "form-select form-control-erp",   # 👈 AQUÍ
                    "data-col": col,
                    "data-gap": gap,
                    "data-gap-top": gap_top,
                    "data-break": "1" if break_line else "0",
                    "data_area": area,
                    "style": 'width: 100%',
                })
            )
            continue

        # 🔽 REFERENCIA
        if tipo_funcional == "Referencia":
            opciones = obtener_opciones_sql(empresa, campo)

            form_fields[nombre] = forms.ChoiceField(
                label=etiqueta,
                choices=opciones,
                required=requerido,
                widget=forms.Select(attrs={
                    "class": "form-select",
                    "data-col": col,
                    "data-gap": gap,
                    "data-gap-top": gap_top,
                    "data-break": "1" if break_line else "0",
                    "data_area": area,
                })
            )
            continue

        # 🔽 CAMPOS NORMALES
        field_class = BASE_FIELD_TYPES.get(tipo_base)
        if not field_class:
            continue

        widget_attrs = {
            "class": "form-control",
            "data-col": col,
            "data-gap": gap,
            "data-gap-top": gap_top,
            "data-break": "1" if break_line else "0",
            "data_area": area,
        }

        kwargs = {
            "label": etiqueta,
            "required": requerido,
            "widget": field_class.widget(attrs=widget_attrs)
        }

        # decimal
        if tipo_base == "decimal":
            kwargs["decimal_places"] = validacion.get("decimales", 2)
            kwargs["max_digits"] = 18
            kwargs["min_value"] = validacion.get("min")
            kwargs["max_value"] = validacion.get("max")

        # int
        if tipo_base == "int":
            kwargs["min_value"] = validacion.get("min")
            kwargs["max_value"] = validacion.get("max")

        # date
        if tipo_base == "date":
            kwargs["widget"] = widgets.DateInput(
                attrs={**widget_attrs, "type": "date"}
            )

        # datetime
        if tipo_base == "datetime":
            kwargs["widget"] = widgets.DateTimeInput(
                attrs={**widget_attrs, "type": "datetime-local"}
            )

        # string
        if tipo_base == "string":
            kwargs["max_length"] = 255

        form_fields[nombre] = field_class(**kwargs)

    return type("DynamicForm", (forms.Form,), form_fields)


import pymysql


def obtener_opciones_sql(empresa, campo):

    
    mysql = pymysql.connect(
        host=empresa.sql_url,
        user=empresa.sql_user,
        password=empresa.sql_clave,
        database=empresa.sql_db,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor  # 🔑 CLAVE

    )

    sql = campo.get("sql")
    value_field = campo.get("value_field")
    label_field = campo.get("label_field")

    with mysql.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall() 

    mysql.close()

    return [
        (row[value_field], row[label_field])
        for row in rows
    ]