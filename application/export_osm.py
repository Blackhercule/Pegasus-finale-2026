"""Export des dépotoirs vérifiés au format d'OpenStreetMap, pour en faire un bien commun (E12).

Le fichier produit s'ouvre dans JOSM : un membre de l'équipe le relit, corrige ce qu'il faut,
puis le verse lui-même. **Le code ne publie jamais rien tout seul** : OpenStreetMap est une
carte utilisée par tout le monde, et un signalement de test ou piégé qui s'y glisserait
l'abîmerait durablement.

Étiquettes retenues : `amenity=waste_dump_site`, employée sur OpenStreetMap pour un lieu de
dépôt sauvage. Elle est accompagnée de `waste=*` et de la date de dernière observation. Le
volume estimé et le nombre de signalements ne sont pas versés : ce sont nos chiffres à nous,
pas des faits vérifiables sur le terrain par un autre contributeur.
"""

import datetime
from xml.sax.saxutils import quoteattr

DECHETS = {"menager": "household", "gravats": "construction", "mixte": "mixed", "autre": "waste"}


def en_osm(depotoirs: list, note: str = "") -> str:
    """Un fichier .osm (XML) : un nœud par dépotoir, avec un identifiant négatif (= à créer)."""
    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<osm version="0.6" generator="assainissement-ouaga">']
    if note:
        lignes.insert(1, "<!-- %s -->" % note.replace("--", "—"))
    for numero, d in enumerate(depotoirs, start=1):
        etiquettes = {
            "amenity": "waste_dump_site",
            "waste": DECHETS.get(d.get("type"), "waste"),
            "source": "relevé de terrain, équipe PEGASUS, Hackathon des Universités 2026",
        }
        vu = (d.get("dernier_vu") or "")[:10]
        if vu:
            etiquettes["survey:date"] = vu
        balises = "".join("\n    <tag k=%s v=%s/>" % (quoteattr(c), quoteattr(v))
                          for c, v in etiquettes.items())
        lignes.append('  <node id="-%d" lat="%.7f" lon="%.7f" version="0">%s\n  </node>'
                      % (numero, float(d["latitude"]), float(d["longitude"]), balises))
    lignes.append("</osm>")
    return "\n".join(lignes)


def note_d_export(nombre: int) -> str:
    return ("%d dépotoirs vérifiés, exportés le %s. À RELIRE dans JOSM avant tout versement : "
            "vérifier que chaque point existe bien sur le terrain et qu'il n'est pas déjà "
            "cartographié." % (nombre, datetime.date.today().strftime("%d/%m/%Y")))
