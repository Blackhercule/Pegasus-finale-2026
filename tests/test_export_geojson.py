"""T19 : le jeu ouvert des dépotoirs vérifiés en GeoJSON, sans aucune donnée personnelle."""

import json
import os
import subprocess
import sys

from conftest import RACINE

BON = {"latitude": 12.3714, "longitude": -1.5197, "taille": "grand", "type": "gravats"}
TEMOIN = {"declarant_nom": "Témoin Fictif", "declarant_telephone": "+226 70 00 00 00",
          "commentaire": "Je suis Awa, j'habite la cour d'à côté"}
INTERDITS = {"declarant_nom", "declarant_telephone", "photo", "photo_cnib", "photo_visage",
             "message_vocal", "source", "commentaire", "id_client", "precision_m"}


def remplir(client):
    """Un dépotoir vérifié (deux appareils, l'un avec un témoin identifié) et un non vérifié."""
    client.post("/api/signalements", json={**BON, **TEMOIN, "source": "tel-awa", "id_client": "a"})
    client.post("/api/signalements", json={**BON, "latitude": 12.37145, "source": "tel-b", "id_client": "b"})
    client.post("/api/signalements", json={**BON, "latitude": 12.3800, "source": "tel-c", "id_client": "c"})


def test_l_export_demande_une_connexion(client):
    assert client.get("/api/export/geojson").status_code == 401


def test_l_export_ne_contient_que_les_verifies_sans_donnee_personnelle(agent):
    remplir(agent)
    reponse = agent.get("/api/export/geojson")
    assert reponse.status_code == 200 and reponse.headers["X-Depotoirs"] == "1"
    collection = reponse.get_json()
    assert collection["type"] == "FeatureCollection" and collection["licence"] == "ODbL-1.0"
    assert len(collection["features"]) == 1                     # le non vérifié n'y est pas
    for entite in collection["features"]:
        assert not INTERDITS & set(entite["properties"]), entite["properties"]
        lon, lat = entite["geometry"]["coordinates"]
        assert entite["geometry"]["type"] == "Point" and 12 < lat < 13 and -2 < lon < -1
        assert len(entite["properties"]["date_observation"]) == 10   # AAAA-MM-JJ
        assert entite["properties"]["type_dechets"] == "gravats"
    # Ceinture et bretelles : aucune trace du témoin, où que ce soit dans le fichier.
    texte = reponse.get_data(as_text=True)
    for valeur in ("Témoin Fictif", "70 00 00 00", "Awa", "tel-awa", "tel-b"):
        assert valeur not in texte


def test_le_fichier_verse_dans_le_depot_est_valide_et_sans_donnee_personnelle():
    with open(os.path.join(RACINE, "donnees", "signalements-ouaga.geojson"), encoding="utf-8") as f:
        collection = json.load(f)
    assert collection["type"] == "FeatureCollection" and collection["licence"] == "ODbL-1.0"
    for entite in collection["features"]:
        assert not INTERDITS & set(entite["properties"])
        assert entite["geometry"]["type"] == "Point" and entite["properties"]["date_observation"]
    assert os.path.exists(os.path.join(RACINE, "donnees", "signalements-ouaga.LICENCE.md"))


def test_l_outil_en_ligne_de_commande_ecrit_le_meme_fichier(application, agent, tmp_path):
    remplir(agent)
    sortie = tmp_path / "jeu.geojson"
    subprocess.run([sys.executable, os.path.join(RACINE, "outils", "exporter_signalements.py"),
                    application.extensions["reglages"].base, str(sortie)], check=True,
                   capture_output=True)
    ecrit = json.loads(sortie.read_text(encoding="utf-8"))
    assert ecrit["features"] == agent.get("/api/export/geojson").get_json()["features"]
