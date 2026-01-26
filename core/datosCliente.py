import pymysql


def viewbasemodulo(modelo_cab, modulo, empresa):
    mysql = pymysql.connect(
        host=empresa.sql_url,
        user=empresa.sql_user,
        password=empresa.sql_clave,
        database=empresa.sql_db,
        autocommit=False
    )

    try:
        cursor = mysql.cursor()

        # 🔹 columnas dinámicas
        columnas = ", ".join(
            m["nombre"] for m in modelo_cab["campos"]
        )

        tabla = modelo_cab["tabla"]
        pk = modelo_cab["pk"]

        sentencia = f"""
            SELECT {columnas}
            FROM {tabla}
            ORDER BY {pk} DESC
        """

        cursor.execute(sentencia)

        datos = cursor.fetchall()

        return datos

    finally:
        cursor.close()
        mysql.close()


