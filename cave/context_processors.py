from .models import ParametresCave


def cave(request):
    """Rend le nom de la cave disponible dans toutes les pages."""
    return {"parametres_cave": ParametresCave.charger()}
