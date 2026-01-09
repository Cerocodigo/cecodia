from django import forms

FIELD_TYPES = {
    "string": forms.CharField,
    "char": forms.CharField,
    "decimal": forms.DecimalField,
    "int": forms.IntegerField,
    "email": forms.EmailField,
    "boolean": forms.BooleanField,
}

def build_dynamic_form(campos):
    form_fields = {}

    for campo in campos:
        print("Campo >>>", campo)

        nombre = campo.get("nombre")
        tipo = campo.get("tipo")

        # ❌ No mostrar PK
        if tipo == "pk":
            continue

        requerido = campo.get("requerido", False)
        defecto = campo.get("defecto", None)

        # 🔽 ENUM
        if tipo == "enum":
            choices = [(v, v) for v in campo.get("valores", [])]
            form_fields[nombre] = forms.ChoiceField(
                label=nombre.capitalize(),
                choices=choices,
                required=requerido,
                initial=defecto
            )
            continue

        # 🔽 CAMPOS NORMALES
        field_class = FIELD_TYPES.get(tipo)
        if not field_class:
            print(f"⚠ Tipo no soportado: {tipo}")
            continue

        kwargs = {
            "label": nombre.capitalize(),
            "required": requerido,
        }

        if defecto is not None:
            kwargs["initial"] = defecto

        if tipo in ("string", "char"):
            kwargs["max_length"] = 255

        form_fields[nombre] = field_class(**kwargs)

    return type("DynamicForm", (forms.Form,), form_fields)
