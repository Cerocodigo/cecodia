from django import forms

FIELD_TYPES = {
    "string": forms.CharField,
    "char": forms.CharField,
    "decimal": forms.DecimalField,
    "int": forms.IntegerField,
    "email": forms.EmailField,
    "boolean": forms.BooleanField,
}

UI_FIELD_TYPES = {
    "image": forms.ImageField,
    "file": forms.FileField,
}
FK_FIELD_TYPES = {
    "fk": forms.ModelChoiceField
}
def build_dynamic_form(campos):
    form_fields = {}

    for campo in campos:
        print("Campo >>>", campo)

        nombre = campo.get("nombre")
        tipo = campo.get("tipo")
        ui = campo.get("ui")
        ui_widget = None

        if isinstance(ui, dict):
            ui_widget = ui.get("widget")
        else:
            ui_widget = ui


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

        # 🔽 UI FIELDS (PRIORIDAD)
        if ui_widget in UI_FIELD_TYPES:
            kwargs = {
                "label": nombre.capitalize(),
                "required": requerido,
            }

            if isinstance(ui, dict):
                if "accept" in ui:
                    kwargs["widget"] = forms.ClearableFileInput(
                        attrs={"accept": ui["accept"]}
                    )

            form_fields[nombre] = UI_FIELD_TYPES[ui_widget](**kwargs)
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