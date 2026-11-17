"""Le jeu ouvert des dépotoirs vérifiés de Ouagadougou, en GeoJSON (T19, E21).

C'est notre « bien commun » : la carte ouverte des dépotoirs, que n'importe qui peut
réutiliser sous licence ODbL (la même qu'OpenStreetMap, pour que le versement reste possible).

**Aucune donnée personnelle n'en sort.** Les propriétés publiées sont choisies une à une dans
CHAMPS_PUBLIES (liste blanche) : une colonne qu'on ajoutera plus tard à la base n'apparaîtra pas
ici par accident. Ni nom, ni téléphone, ni photo, ni message vocal, ni pseudonyme de l'appareil
(la « source »), ni commentaire libre (il pourrait contenir un nom).
"""

import datetime

LICENCE = "ODbL-1.0"
ATTRIBUTION = "© équipe PEGASUS (Université Joseph Ki-Zerbo) et contributeurs, ODbL 1.0"

# Ce qui est publié pour chaque dépotoir, et rien d'autre.
CHAMPS_PUBLIES = ("volume_m3", "surface_m2", "depot", "nb_signalements", "nb_sources",
                  "premier_vu", "dernier_vu", "etape")


def type_de_dechets(co, id_depotoir: int) -> str:
    """Le type de déchets le plus souvent indiqué par les signalements de ce dépotoir."""
    ligne = co.execute(
        "SELECT type, COUNT(*) n FROM signalements WHERE depotoir_id = ? AND type IS NOT NULL"
        " GROUP BY type ORDER BY n DESC, type LIMIT 1", (id_depotoir,)).fetchone()
    return ligne["type"] if ligne else None


def en_geojson(depotoirs: list, co) -> dict:
    """Une FeatureCollection : un point par dépotoir vérifié, propriétés en liste blanche.

    Chaque entité porte une date (`date_observation`, la dernière fois qu'il a été vu) : sans
    date, un dépotoir ne dit pas s'il existe encore."""
    entites = []
    for d in depotoirs:
        date = (d.get("dernier_vu") or d.get("premier_vu") or "")[:10]
        if d.get("latitude") is None or d.get("longitude") is None or not date:
            continue                     # sans position ou sans date, l'entité n'est pas publiée
        proprietes = {"id": "ouaga-depotoir-%d" % d["id"], "date_observation": date,
                      "type_dechets": type_de_dechets(co, d["id"])}
        proprietes.update({champ: d.get(champ) for champ in CHAMPS_PUBLIES})
        entites.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [round(float(d["longitude"]), 6), round(float(d["latitude"]), 6)]},
            "properties": proprietes,
        })
    return {
        "type": "FeatureCollection",
        "name": "Dépotoirs sauvages vérifiés de Ouagadougou",
        "licence": LICENCE,
        "attribution": ATTRIBUTION,
        "genere_le": datetime.date.today().isoformat(),
        "description": ("Dépotoirs signalés par des habitants et vérifiés (par un agent de la "
                        "mairie, ou par au moins deux appareils différents). Aucune donnée "
                        "personnelle. Voir signalements-ouaga.LICENCE.md."),
        "features": entites,
    }
