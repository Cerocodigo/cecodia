from django.db import models
from django.contrib.auth.models import User


class Empresa(models.Model):
    nombre = models.CharField(max_length=200)

    # Configuración Mongo (modelos declarativos)
    mongo_uri = models.CharField(
        max_length=500,
        help_text="URI de MongoDB para los modelos declarativos"
    )
    mongo_db = models.CharField(
        max_length=100,
        default="cerocodigo_modelos"
    )


    sql_url = models.CharField(
        max_length=500,
        help_text="URI de sql para los datos del empresa"
    )    
    sql_user = models.CharField(
        max_length=500,
        help_text="URI de sql para los datos del empresa"
    )
    sql_clave = models.CharField(
        max_length=500,
        help_text="URI de sql para los datos del empresa"
    )
    sql_db = models.CharField(
        max_length=100,
        default="base de datos"
    )

    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class UsuarioEmpresa(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    es_admin = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "empresa")

    def __str__(self):
        return f"{self.user.username} - {self.empresa.nombre}"
