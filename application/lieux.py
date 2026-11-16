"""Les lieux connus de la commune, pour signaler quand la position du téléphone ne marche pas (T16).

Ils viennent de `donnees/<commune>/lieux.geojson` (tiré d'OpenStreetMap par preparer.py) : on
ne garde que ceux qui ont un nom et qui servent de repère à un habitant — marchés, écoles,
collèges, universités, lieux de santé. La liste est lue une fois, au démarrage.
"""

import json
import os
import unicodedata

# (type, sous-type d'OpenStreetMap) → ce qu'on affiche. Les sous-types absents d'ici sont
# rangés sous le nom de leur type.
GENRES = {
    ("marche", "marketplace"): "Marché",
    ("ecole", "university"): "Université",
    ("ecole", "college"): "Collège",
    ("ecole", "kindergarten"): "École maternelle",
    ("ecole", None): "École",
    ("sante", None): "Santé",
}


def sans_accents(texte: str) -> str:
    """« Marché de Gounghin » → « marche de gounghin » : pour chercher sans se soucier des
    accents ni des majuscules."""
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower()


def charger_lieux(chemin: str) -> list:
    """La liste des lieux nommés : identifiant, nom, genre, longitude, latitude."""
    if not os.path.isfile(chemin):
        return []                       # une commune sans ce fichier marche quand même
    with open(chemin, encoding="utf-8") as f:
        entites = json.load(f).get("features", [])
    lieux = []
    for entite in entites:
        p = entite.get("properties") or {}
        geometrie = entite.get("geometry") or {}
        if not p.get("nom") or geometrie.get("type") != "Point":
            continue
        genre = GENRES.get((p.get("type"), p.get("sous_type"))) or GENRES.get((p.get("type"), None))
        if genre is None:
            continue                    # décharges, centres de tri : pas des repères d'habitant
        lon, lat = geometrie["coordinates"][:2]
        lieux.append({"id": p.get("osm") or f"lieu-{len(lieux)}", "nom": p["nom"], "genre": genre,
                      "longitude": round(lon, 6), "latitude": round(lat, 6)})
    lieux.sort(key=lambda l: sans_accents(l["nom"]))
    return lieux
