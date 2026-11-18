"""Extrait les noms de quartiers de notre fond de carte (une seule fois, à la préparation).

    pip install pmtiles mapbox-vector-tile
    python outils/extraire_quartiers.py   → donnees/ouagadougou/quartiers.geojson

Le fond de carte (fond.pmtiles, OpenStreetMap) contient les noms de lieux de la commune :
quartiers, secteurs, villages rattachés. On en garde le nom et la position. Un signalement est
ensuite rangé dans le quartier dont le nom est le PLUS PROCHE (application/territoire.py).
C'est une approximation honnête : OpenStreetMap n'a pas encore les limites officielles des
quartiers ni des 12 arrondissements de Ouagadougou ; quand la mairie les fournira, on les
mettra à la place de ce fichier.
Licence des noms : ODbL 1.0 — © les contributeurs d'OpenStreetMap.
"""

import gzip
import json
import math
import os

import mapbox_vector_tile
from pmtiles.reader import MmapSource, Reader

RACINE = os.path.join(os.path.dirname(__file__), "..", "donnees", "ouagadougou")
GARDES = {"suburb", "quarter", "neighbourhood", "village", "hamlet", "town"}


def tuile(lon, lat, z):
    la = math.radians(lat)
    return (int((lon + 180) / 360 * 2 ** z),
            int((1 - math.log(math.tan(la) + 1 / math.cos(la)) / math.pi) / 2 * 2 ** z))


def vers_lonlat(z, x, y, px, py, etendue=4096):
    # Les coordonnées des tuiles décodées ont l'axe vertical vers le haut.
    X, Y = (x + px / etendue) / 2 ** z, (y + 1 - py / etendue) / 2 ** z
    return X * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * Y))))


def principal():
    with open(os.path.join(RACINE, "commune.json"), encoding="utf-8") as f:
        ouest, sud, est, nord = json.load(f)["bbox"]
    lecteur = Reader(MmapSource(open(os.path.join(RACINE, "fond.pmtiles"), "rb")))
    lieux = {}
    for z in (12, 13, 14):
        x0, y0 = tuile(ouest, nord, z)
        x1, y1 = tuile(est, sud, z)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                donnees = lecteur.get(z, x, y)
                if not donnees:
                    continue
                for entite in mapbox_vector_tile.decode(gzip.decompress(donnees)).get("places", {}).get("features", []):
                    p = entite["properties"]
                    if p.get("kind_detail") not in GARDES or not p.get("name"):
                        continue
                    lon, lat = vers_lonlat(z, x, y, *entite["geometry"]["coordinates"])
                    if ouest <= lon <= est and sud <= lat <= nord:
                        lieux.setdefault(p["name"].strip(), (round(lon, 5), round(lat, 5), p["kind_detail"]))
    entites = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"nom": nom[0].upper() + nom[1:], "genre": genre}}
               for nom, (lon, lat, genre) in sorted(lieux.items())]
    with open(os.path.join(RACINE, "quartiers.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection",
                   "licence": "ODbL 1.0 — © les contributeurs d'OpenStreetMap",
                   "features": entites}, f, ensure_ascii=False, indent=1)
    print(len(entites), "quartiers")


if __name__ == "__main__":
    principal()
