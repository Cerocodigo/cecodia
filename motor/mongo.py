from pymongo import MongoClient


def get_mongo_empresa(empresa):
    """
    Retorna la base MongoDB asociada a una empresa
    """
    client = MongoClient(empresa.mongo_uri)
    return client[empresa.mongo_db]


def mongo_field_to_sql(campo):
    """
    Convierte un campo del modelo dinámico (Mongo / JSON)
    a definición SQL MySQL/MariaDB
    """

    # 🔹 Nombre de columna
    nombre = campo["nombre"]
    nombre_sql = f"`{nombre}`"

    # 🔹 Tipo base
    tipo_base = campo.get("tipo_base")

    # 🔹 Tipos especiales
    if tipo_base in ("fk", "select_sql"):
        tipo_base = campo.get("tipo_sql", "int")

    # 🔹 Mapeo SQL
    sql_type = SQL_TYPES.get(tipo_base)
    if not sql_type:
        raise ValueError(f"Tipo SQL no soportado: {tipo_base}")

    # 🔹 NULL / NOT NULL
    requerido = campo.get("requerido", False)
    null_sql = "NOT NULL" if requerido else "NULL"

    # 🔹 AUTO_INCREMENT / PK
    extra = []
    if campo.get("tipo_funcional") == "NumeroSecuencial":
        extra.append("AUTO_INCREMENT")
        extra.append("PRIMARY KEY")
        null_sql = "NOT NULL"

    # 🔹 Default automáticos
    if campo.get("tipo_funcional") == "FechaCreacion":
        extra.append("DEFAULT CURRENT_TIMESTAMP")

    if campo.get("tipo_funcional") == "FechaActualizacion":
        extra.append(
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )

    # 🔹 Resultado final
    return " ".join([
        nombre_sql,
        sql_type,
        null_sql,
        *extra
    ]).strip()




SQL_TYPES = {
    "pk": "INT AUTO_INCREMENT PRIMARY KEY",
    "string": "VARCHAR(255)",
    "char": "CHAR(1)",
    "text": "TEXT",
    "int": "INT",
    "integer": "INT",
    "decimal": "DECIMAL(10,2)",
    "boolean": "TINYINT(1)",
    "date": "DATE",
    "datetime": "DATETIME",
    "time": "TIME",
    "fk": "INT",

}