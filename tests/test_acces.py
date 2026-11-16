"""T13 : la partie décision demande une connexion ; le signalement reste ouvert à tous.

Le filtre est une LISTE BLANCHE (application/__init__.py, OUVERT_A_TOUS) : tout est fermé sauf
ce qui est explicitement ouvert. Le dernier test parcourt toutes les routes de Flask et échoue
si l'une d'elles répond sans connexion alors qu'elle n'est pas dans la liste blanche : c'est lui
qui empêchera d'oublier la prochaine adresse qu'on ajoutera.
"""

import io
import os
import re

import pytest

from application import OUVERT_A_TOUS, PAGE_DE_CONNEXION
from conftest import MOT_DE_PASSE, RACINE

BON = {"latitude": 12.3714, "longitude": -1.5197, "taille": "grand", "source": "essai"}

# Adresses que la tâche T13 cite comme devant être protégées : (méthode, adresse).
PROTEGEES = [
    ("GET", "/"),
    ("GET", "/decision/"),
    ("GET", "/decision/index.html"),
    ("GET", "/decision/carte.js"),
    ("GET", "/decision/scenarios.html"),
    ("GET", "/decision/verifier.html"),
    ("GET", "/decision/dossiers.html"),
    ("GET", "/donnees/commune.geojson"),
    ("GET", "/api/signalements"),
    ("GET", "/api/depotoirs"),
    ("GET", "/api/plan"),
    ("POST", "/api/plan"),
    ("POST", "/api/scenario"),
    ("POST", "/api/comparer"),
    ("GET", "/api/parametres"),
    ("GET", "/api/comptes"),
    ("GET", "/api/chaine"),
    ("GET", "/api/dossiers"),
    ("GET", "/api/dossiers/1"),
    ("GET", "/api/fuites"),
    ("GET", "/api/fuites/carte"),
    ("GET", "/api/fuites/chaine"),
    ("GET", "/api/fuites/1"),
    ("GET", "/api/nuisances"),
    ("GET", "/api/nuisances/carte"),
    ("GET", "/api/nuisances/chaine"),
    ("GET", "/api/nuisances/1"),
    ("GET", "/api/export/osm"),
    ("GET", "/api/export/onea"),
    ("GET", "/api/export/nuisances"),
]


@pytest.mark.parametrize("methode,adresse", PROTEGEES)
def test_sans_connexion_la_partie_decision_est_fermee(client, methode, adresse):
    reponse = client.open(adresse, method=methode, json={} if methode == "POST" else None)
    assert reponse.status_code == 401, adresse
    if adresse.startswith("/api/"):
        assert reponse.get_json() == {"erreur": "Connexion requise."}
    else:
        # Une page : c'est la page de connexion qui s'affiche, à la même adresse.
        assert b'id="formulaire"' in reponse.data and b"/decision/connexion.js" in reponse.data
        assert reponse.headers["Cache-Control"] == "no-store"
        # Rien de la page protégée ne fuit dans la réponse.
        assert b"carte.js" not in reponse.data or adresse == "/decision/carte.js"


def test_apres_connexion_la_carte_s_affiche(client):
    assert client.get("/decision/").status_code == 401
    client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": MOT_DE_PASSE})
    reponse = client.get("/decision/")
    assert reponse.status_code == 200 and b'id="formulaire"' not in reponse.data
    assert client.get("/api/depotoirs").status_code == 200
    assert client.get("/donnees/commune.geojson").status_code == 200
    client.post("/api/deconnexion")
    assert client.get("/api/depotoirs").status_code == 401


@pytest.mark.parametrize("compte,mot_de_passe", [
    ("agent", MOT_DE_PASSE), ("brigade", "essai-brigade"), ("collecte", "essai-collecte")])
def test_chaque_poste_entre_dans_la_partie_decision(client, compte, mot_de_passe):
    assert client.post("/api/connexion", json={"nom": compte, "mot_de_passe": mot_de_passe}).status_code == 200
    assert client.get("/decision/").status_code == 200
    assert client.get("/api/dossiers").status_code == 200


def test_un_mauvais_mot_de_passe_n_ouvre_rien(client):
    assert client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": "faux"}).status_code == 401
    assert client.get("/decision/").status_code == 401
    assert client.get("/api/plan").status_code == 401


@pytest.mark.parametrize("fichier", sorted(PAGE_DE_CONNEXION))
def test_la_page_de_connexion_se_charge_sans_connexion(client, fichier):
    assert client.get("/decision/" + fichier).status_code == 200


def fichiers_de(dossier):
    """Tous les fichiers d'un dossier de l'interface, en adresses relatives."""
    racine = os.path.join(RACINE, "interface", dossier)
    for base, _, noms in os.walk(racine):
        for nom in noms:
            yield os.path.relpath(os.path.join(base, nom), racine).replace(os.sep, "/")


@pytest.mark.parametrize("fichier", sorted(fichiers_de("signaler")))
def test_la_page_de_signalement_reste_ouverte(client, fichier):
    """La page de l'habitant et tout ce qu'elle charge : script, style, service worker, sons…"""
    adresse = "/signaler/" + ("" if fichier == "index.html" else fichier)
    assert client.get(adresse).status_code == 200, adresse


def test_les_bibliotheques_restent_ouvertes(client):
    # La page de signalement charge sa police depuis /vendor/.
    assert client.get("/vendor/polices/lato/lato.css").status_code == 200


def test_on_signale_sans_connexion(client):
    reponse = client.post("/api/signalements", json={**BON, "id_client": "public-1"})
    assert reponse.status_code == 201 and reponse.get_json()["statut"] == "recevable"
    lot = client.post("/api/signalements/lot", json=[{**BON, "id_client": "public-2", "latitude": 12.39}])
    assert lot.status_code == 200 and lot.get_json()["recus"] == 1


def test_les_photos_publiques_restent_ouvertes_et_les_privees_fermees(client):
    image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    client.post("/api/signalements", data={**BON, "id_client": "photo-1",
                                           "photo": (io.BytesIO(image), "tas.png")},
                content_type="multipart/form-data")
    client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": MOT_DE_PASSE})
    chemin = client.get("/api/signalements").get_json()[0]["photo"]
    client.post("/api/deconnexion")
    assert chemin.startswith("public/")
    assert client.get("/api/fichiers/" + chemin).status_code == 200
    assert client.get("/api/fichiers/prive/" + chemin.split("/")[1]).status_code == 401


# ------------------------------------------------------------------ toutes les routes de Flask
def adresse_d_essai(regle):
    """Une adresse concrète pour une route : chaque paramètre reçoit une valeur simple."""
    valeurs = {nom: 1 if type(conv).__name__ == "IntegerConverter" else "essai"
               for nom, conv in regle._converters.items()}
    return re.sub(r"<(?:[a-z]+:)?([a-z_]+)>", lambda m: str(valeurs[m.group(1)]), regle.rule)


def test_aucune_route_n_est_ouverte_par_oubli(application):
    """Échoue si une route répond sans connexion alors qu'elle n'est pas dans la liste blanche."""
    client = application.test_client()
    oubliees = []
    for regle in application.url_map.iter_rules():
        if regle.endpoint in OUVERT_A_TOUS:
            continue
        for methode in sorted(regle.methods - {"HEAD", "OPTIONS"}):
            adresse = adresse_d_essai(regle)
            reponse = client.open(adresse, method=methode, json={} if methode != "GET" else None)
            if reponse.status_code != 401:
                oubliees.append(f"{methode} {regle.rule} → {reponse.status_code}")
    assert oubliees == [], "Routes ouvertes sans être dans la liste blanche : " + ", ".join(oubliees)


def test_la_liste_blanche_ne_nomme_que_des_routes_qui_existent(application):
    """Un nom mal orthographié dans la liste blanche ne protégerait ni n'ouvrirait rien."""
    existantes = {regle.endpoint for regle in application.url_map.iter_rules()}
    assert OUVERT_A_TOUS <= existantes
