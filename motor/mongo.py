from pymongo import MongoClient


def get_mongo_empresa(empresa):
    """
    Retorna la base MongoDB asociada a una empresa
    """
    client = MongoClient(empresa.mongo_uri)
    return client[empresa.mongo_db]


def mongo_field_to_sql(campo):
    tipo = campo["tipo"]
    nombre = campo["nombre"]

    sql = SQL_TYPES.get(tipo)
    if not sql:
        raise Exception(f"Tipo no soportado: {tipo}")

    nullable = "" if campo.get("requerido") else "NULL"
    return f"{nombre} {sql} {nullable}".strip()

SQL_TYPES = {
    "pk": "INT AUTO_INCREMENT PRIMARY KEY",
    "string": "VARCHAR(255)",
    "char": "VARCHAR(100)",
    "decimal": "DECIMAL(12,2)",
    "int": "INT",
    "boolean": "TINYINT(1)",
    "fk": "INT",
    "enum": "VARCHAR(255)",
}

