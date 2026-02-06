from django import forms
from django.forms import widgets, Select


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
        ):
            continue

        # attrs base
        widget_attrs = {
            "id": f"id_{nombre}",
            "class": "form-control",
            "data-col": col,
            "data-gap": gap,
            "data-gap-top": gap_top,
            "data-break": "1" if break_line else "0",
            "data_area": area,
        }


        # 🔽 OPCIÓN MÚLTIPLE
        if tipo_funcional == "OpcionMultiple":
            opciones = configuracion.get("opciones", [])
            labels = configuracion.get("labels", {})
            choices = [(op, labels.get(op, op)) for op in opciones]
            

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
            opciones = obtener_opciones_sql(empresa, configuracion)

            choices = opciones[0]
            extra_data = opciones[1]

            widget_attrs.update({
                "class": "form-select form-control-erp",
                "style": "width: 100%",
                "data-ref-source": nombre,
            })

            print("DEBUG opciones:", opciones)
            print("DEBUG tipo primer elemento:", type(opciones[0]))

            form_fields[nombre] = forms.ChoiceField(
                label=etiqueta,
                required=requerido,
                choices=choices,
                widget=SelectWithData(
                    attrs=widget_attrs,
                    extra_data=extra_data
                )
            )

            continue

        # ====================================================
        # 📎 REFERENCIA ADJUNTO (INPUT AUTO)
        # ====================================================
        if tipo_funcional == "ReferenciaAdjunto":

            ref = configuracion.get("referencia")          # TarifaIva
            campo_origen = configuracion.get("campo_origen")  # Porcentaje


            widget_attrs.update({
                "readonly": "readonly",
                "data-ref-from": f"id_{ref}",               # 🔑
                "data-ref-key": campo_origen.lower(),        # 🔑
            })

            form_fields[nombre] = forms.CharField(
                label=etiqueta,
                required=False,
                widget=forms.TextInput(attrs=widget_attrs)
            )


            field_class = BASE_FIELD_TYPES.get(tipo_base, forms.CharField)

            kwargs = {
                "label": etiqueta,
                "required": False,
                "widget": field_class.widget(attrs=widget_attrs)
            }

            if tipo_base == "decimal":
                kwargs["decimal_places"] = validacion.get("decimales", 2)
                kwargs["max_digits"] = 18

            if tipo_base == "int":
                kwargs["min_value"] = validacion.get("min")
                kwargs["max_value"] = validacion.get("max")

            if tipo_base == "string":
                kwargs["max_length"] = 255

            form_fields[nombre] = field_class(**kwargs)
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
        print("nombre >>>" , nombre)
        print("form_fields >>>" , form_fields[nombre])

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
        cursorclass=pymysql.cursors.DictCursor
    )

    sql = campo.get("sql")
    value_field = campo.get("value_field")
    label_field = campo.get("label_field")

    with mysql.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()

    mysql.close()

    choices = []
    data_map = {}

    for row in rows:
        value = row[value_field]
        label = row[label_field]

        choices.append((value, label))

        extra = {}
        for k, v in row.items():
            if k in (value_field, label_field):
                continue
            extra[k] = v

        data_map[value] = extra

    return choices, data_map


class SelectWithData(Select):
    def __init__(self, *args, extra_data=None, **kwargs):
        self.extra_data = extra_data or {}
        super().__init__(*args, **kwargs)

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )

        if value in self.extra_data:
            for k, v in self.extra_data[value].items():
                option["attrs"][f"data-{k.lower()}"] = v

        return option