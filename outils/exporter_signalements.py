"""Écrit le jeu ouvert des dépotoirs vérifiés : donnees/signalements-ouaga.geojson (T19).

    python outils/exporter_signalements.py [base.sqlite] [sortie.geojson]

Lit directement la base de l'application (par défaut celle des réglages : BASE_DONNEES, ou
donnees/ouagadougou/signalements.sqlite) : pas besoin que le serveur tourne. Le fichier produit
est le même que celui de GET /api/export/geojson. À relancer après chaque campagne de terrain,
puis à relire avant de le verser dans le dépôt.
"""

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from application.base import connexion  # noqa: E402
from application.export_geojson import en_geojson  # noqa: E402
from application.reglages import Reglages  # noqa: E402
from application.signalements import Depotoirs  # noqa: E402


def principal():
    reglages = Reglages(base=sys.argv[1] if len(sys.argv) > 1 else None)
    sortie = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        RACINE, "donnees", "signalements-ouaga.geojson")
    if not os.path.exists(reglages.base):
        sys.exit(f"Base introuvable : {reglages.base}")
    co = connexion(reglages.base)
    collection = en_geojson(Depotoirs(co, reglages.parametres).retenus(mode_strict=True), co)
    co.close()
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{len(collection['features'])} dépotoir(s) vérifié(s) écrit(s) dans {sortie}")


if __name__ == "__main__":
    principal()
