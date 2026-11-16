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


# --------------------------------------------------------------- ce qui faisait tomber le serveur
# Quatre entrées trouvées par une session de Claude Code en attaquant notre propre API. Trois
# faisaient répondre 500. Une erreur 500 est exactement ce qu'un jury de cybersécurité cherche
# à provoquer : elle prouve qu'une entrée n'a pas été contrôlée.

SIGNALEMENT = {"latitude": 12.3714, "longitude": -1.5197, "taille": "grand", "source": "piege"}


def test_un_nombre_de_400_chiffres_ne_fait_pas_tomber_le_serveur(client):
    """float() lève OverflowError, et non ValueError, sur un entier trop grand."""
    reponse = client.post("/api/signalements",
                          json={**SIGNALEMENT, "volume_m3": int("9" * 400), "id_client": "a"})
    assert reponse.status_code < 500
    # Le volume démesuré est ignoré : le dépotoir prend le volume que sa taille suppose.
    assert reponse.get_json()["statut"] != "rejete"


def test_un_demi_caractere_unicode_ne_fait_pas_tomber_le_serveur(client):
    """\\ud800 traverse JSON mais ne peut pas s'écrire en UTF-8 : il tombait en base."""
    reponse = client.post(
        "/api/signalements",
        data='{"latitude":12.3714,"longitude":-1.5197,"taille":"grand",'
             '"commentaire":"\\ud800 bonjour","source":"piege","id_client":"b"}',
        content_type="application/json")
    assert reponse.status_code < 500


def test_une_limite_illisible_ne_fait_pas_tomber_le_serveur(agent):
    for adresse in ("/api/signalements?limite=abc", "/api/signalements?limite=-5",
                    "/api/signalements?limite=99999999999999999999",
                    "/api/depotoirs?limite=abc"):
        assert agent.get(adresse).status_code < 500, adresse


def test_un_json_profondement_emboite_ne_fait_pas_tomber_le_serveur(client):
    reponse = client.post("/api/signalements", data="[" * 2000 + "]" * 2000,
                          content_type="application/json")
    assert reponse.status_code < 500


def test_les_essais_de_mot_de_passe_sont_limites(client):
    """Toute la partie décision étant derrière un mot de passe, il ne faut pas pouvoir les
    essayer tous. Le compte reste utilisable : seul l'identifiant malmené est freiné."""
    for _ in range(12):
        client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": "faux"})
    refus = client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": "faux"})
    assert refus.status_code == 429
    assert "Réessayez" in refus.get_json()["erreur"]
    # Un identifiant inexistant est freiné de la même façon : on n'apprend pas lesquels existent.
    for _ in range(12):
        client.post("/api/connexion", json={"nom": "inconnu", "mot_de_passe": "x"})
    assert client.post("/api/connexion",
                       json={"nom": "inconnu", "mot_de_passe": "x"}).status_code == 429
