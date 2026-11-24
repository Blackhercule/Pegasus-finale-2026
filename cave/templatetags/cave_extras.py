from django import template

from ..formats import fcfa as _fcfa
from ..formats import texte_stock

register = template.Library()


@register.filter
def fcfa(montant):
    """{{ 25500|fcfa }} -> 25 500 F"""
    return _fcfa(montant)


@register.filter
def stock(bouteilles, bouteilles_par_caisse):
    """{{ 130|stock:12 }} -> 10 caisses + 10 bt"""
    return texte_stock(bouteilles, bouteilles_par_caisse)


@register.filter
def pourcentage(valeur, maximum):
    """
    Taille d'une barre de graphique, en % du maximum (0 à 100).
    Renvoie un texte avec un point (« 45.3 ») : en français Django écrirait
    « 45,3 », que le CSS ne comprend pas.
    """
    try:
        pct = 100 * float(valeur) / float(maximum) if maximum else 0
    except (TypeError, ValueError):
        pct = 0
    return f"{max(0.0, min(100.0, pct)):.1f}"


@register.filter
def compact(montant):
    """Graduation courte d'un graphique : 1500000 -> « 1,5 M », 750000 -> « 750 k »."""
    montant = int(montant or 0)
    if montant >= 1_000_000:
        return f"{montant / 1_000_000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " M"
    if montant >= 1_000:
        return f"{montant / 1_000:.0f} k"
    return str(montant)
