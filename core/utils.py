from .models import UsuarioEmpresa


def empresa_activa(request):
    """
    Devuelve la empresa activa del usuario logueado.
    Por ahora: la primera activa.
    Luego se puede mejorar con selector.
    """
    relacion = UsuarioEmpresa.objects.filter(
        user=request.user,
        activa=True,
        empresa__activa=True
    ).select_related("empresa").first()

    return relacion.empresa if relacion else None

