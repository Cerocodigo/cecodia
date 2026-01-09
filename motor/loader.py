from .mongo import get_mongo_empresa

def obtener_modulos_empresa(empresa):
    db = get_mongo_empresa(empresa)

    modulos = []
    for m in db.modulos.find({"activo": True}):
        modulos.append({
            "id": m["_id"],          # 👈 renombrado
            "nombre": m.get("nombre"),
            "descripcion": m.get("descripcion", "")
        })

    return modulos