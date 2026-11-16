"""Géographie de la commune : « ce point est-il dans la commune ? dans l'eau ? ».

Les fichiers sont lus une seule fois au démarrage. Shapely prépare les polygones (`prep`), ce
qui rend chaque test quasi instantané : il en faut un par signalement reçu, y compris quand le
jury en envoie mille d'un coup.
"""

import json
import math

from shapely.geometry import Point, shape
from shapely.prepared import prep
from shapely.strtree import STRtree

RAYON_TERRE_M = 6371008.8


def distance_m(lon1, lat1, lon2, lat2) -> float:
    """Distance à vol d'oiseau entre deux points, en mètres (formule de haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * RAYON_TERRE_M * math.asin(math.sqrt(a))


def lire_geojson(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)["features"]


class Geographie:
    def __init__(self, fichier_commune: str, fichier_eau: str = None):
        entites = lire_geojson(fichier_commune)
        self.commune = shape(entites[0]["geometry"])
        for e in entites[1:]:
            self.commune = self.commune.union(shape(e["geometry"]))
        self._commune_prete = prep(self.commune)
        self.bbox = self.commune.bounds                      # (ouest, sud, est, nord)
        eaux = lire_geojson(fichier_eau) if fichier_eau else []
        self.eaux = [shape(e["geometry"]) for e in eaux]
        self._arbre_eaux = STRtree(self.eaux) if self.eaux else None

    def dans_la_commune(self, lon: float, lat: float) -> bool:
        return self._commune_prete.contains(Point(lon, lat))

    def dans_l_eau(self, lon: float, lat: float) -> bool:
        """Vrai si le point tombe dans un plan d'eau (barrage, retenue) : un dépotoir n'y est pas."""
        if self._arbre_eaux is None:
            return False
        point = Point(lon, lat)
        # L'arbre donne les quelques polygones dont le rectangle englobant contient le point ;
        # on ne teste vraiment que ceux-là.
        return any(self.eaux[i].contains(point) for i in self._arbre_eaux.query(point))


def origines(lignes) -> set:
    """Qui a confirmé, en comptant un envoi groupé pour UN SEUL témoin.

    Deux appareils différents qui voient le même tas valent vérification : c'est notre meilleure
    protection contre un signalement inventé. Mais un fichier envoyé en lot peut contenir autant
    de « sources » différentes que son auteur veut écrire — il se confirmerait donc tout seul, et
    entrerait dans le plan puis dans l'export OpenStreetMap sans qu'aucun second témoin existe.

    D'où la règle : tout ce qui vient d'un même lot compte pour une origine unique, celle du lot.
    Un signalement envoyé depuis un téléphone garde la sienne.
    """
    return {(l["lot"] if l["lot"] else l["source"]) for l in lignes}
