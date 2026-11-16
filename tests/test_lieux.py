"""T16 : signaler depuis un lieu connu quand la position du téléphone ne marche pas."""

import sqlite3

from application.lieux import sans_accents
from conftest import MOT_DE_PASSE

UJKZ = "Université Joseph Ki-Zerbo de Ouagadougou"


def lieu(client, nom):
    return next(l for l in client.get("/api/lieux").get_json() if l["nom"] == nom)


def chercher(lieux, texte):
    """La même recherche que la page : chaque mot doit se trouver dans le nom ou le genre."""
    mots = sans_accents(texte).split()
    return [l["nom"] for l in lieux if all(m in sans_accents(l["nom"] + " " + l["genre"]) for m in mots)]


def test_la_liste_des_lieux_est_publique_et_ne_contient_que_des_lieux(client):
    reponse = client.get("/api/lieux")
    assert reponse.status_code == 200                       # sans connexion
    lieux = reponse.get_json()
    assert len(lieux) > 1000
    assert all(set(l) == {"id", "nom", "genre", "longitude", "latitude"} for l in lieux)
    genres = {l["genre"] for l in lieux}
    assert {"Marché", "Université", "Collège", "École", "Santé"} <= genres


def test_la_recherche_ignore_accents_et_majuscules(client):
    lieux = client.get("/api/lieux").get_json()
    assert "Marché de Gounghin" in chercher(lieux, "marche gounghin")
    assert "Marché de Gounghin" in chercher(lieux, "MARCHÉ   Gounghin")
    assert UJKZ in chercher(lieux, "universite ki-zerbo")
    assert chercher(lieux, "xyzzy introuvable") == []


def test_un_signalement_depuis_un_lieu_est_marque_comme_tel(client, application):
    ujkz = lieu(client, UJKZ)
    reponse = client.post("/api/signalements", json={
        "source_position": "lieu", "lieu_id": ujkz["id"],
        # Position envoyée fausse et précision « parfaite » : le serveur ne les croit pas.
        "latitude": 12.30, "longitude": -1.60, "precision_m": 0,
        "taille": "grand", "source": "tel-sans-gps", "id_client": "lieu-1",
        "commentaire": "Repère : derrière l'amphi, côté nord."})
    assert reponse.status_code == 201
    co = sqlite3.connect(application.extensions["reglages"].base)
    ligne = co.execute("SELECT source_position, lieu_nom, latitude, longitude, precision_m, statut,"
                       " motifs FROM signalements").fetchone()
    assert ligne[:5] == ("lieu", UJKZ, ujkz["latitude"], ujkz["longitude"], 150)
    # 150 m dépasse le seuil de précision : un agent regarde avant que le tas entre au plan.
    assert ligne[5] == "a_verifier" and "precision_insuffisante" in ligne[6]


def test_un_signalement_gps_est_marque_gps(client, application):
    client.post("/api/signalements", json={"latitude": 12.3714, "longitude": -1.5197,
                                           "taille": "grand", "source": "tel", "id_client": "g"})
    co = sqlite3.connect(application.extensions["reglages"].base)
    assert co.execute("SELECT source_position, lieu_nom FROM signalements").fetchone() == ("gps", None)


def test_un_lieu_inconnu_est_rejete(client):
    reponse = client.post("/api/signalements", json={
        "source_position": "lieu", "lieu_id": "node/0", "latitude": 12.37, "longitude": -1.52,
        "taille": "grand", "source": "tel", "id_client": "faux"})
    assert reponse.get_json()["statut"] == "rejete"


def test_fuites_et_nuisances_gardent_aussi_la_provenance(client, application):
    ujkz = lieu(client, UJKZ)
    commun = {"source_position": "lieu", "lieu_id": ujkz["id"], "latitude": 1, "longitude": 1,
              "source": "tel"}
    client.post("/api/signalements", json={**commun, "nature": "fuite_eau", "ampleur": "jet",
                                           "id_client": "f"})
    client.post("/api/signalements", json={**commun, "nature": "caniveau_bouche",
                                           "gravite": "moyen", "id_client": "n"})
    co = sqlite3.connect(application.extensions["reglages"].base)
    lignes = co.execute("SELECT nature, source_position, lieu_nom FROM signalements").fetchall()
    assert len(lignes) == 2 and all(l[1:] == ("lieu", UJKZ) for l in lignes), lignes


def test_la_mairie_voit_la_provenance_dans_le_dossier(client):
    ujkz = lieu(client, UJKZ)
    client.post("/api/signalements", json={"source_position": "lieu", "lieu_id": ujkz["id"],
                                           "latitude": 1, "longitude": 1, "taille": "grand",
                                           "source": "tel", "id_client": "d"})
    client.post("/api/connexion", json={"nom": "agent", "mot_de_passe": MOT_DE_PASSE})
    s = client.get("/api/signalements").get_json()[0]
    assert (s["source_position"], s["lieu_nom"]) == ("lieu", UJKZ)
    if s["depotoir_id"]:
        detail = client.get(f"/api/dossiers/{s['depotoir_id']}").get_json()
        assert detail["signalements"][0]["source_position"] == "lieu"


def test_une_base_deja_installee_recoit_les_deux_colonnes(tmp_path):
    from application.base import SCHEMA, creer
    # Une base comme celle d'une installation d'avant T16 : le schéma de départ, sans les ajouts.
    chemin = str(tmp_path / "ancienne.sqlite")
    co = sqlite3.connect(chemin)
    co.executescript(SCHEMA)
    co.execute("INSERT INTO signalements (latitude, longitude, date_reception, source, statut)"
               " VALUES (12.3, -1.5, '2026-11-16', 'tel', 'recevable')")
    co.commit(); co.close()
    creer(chemin)
    co = sqlite3.connect(chemin)
    colonnes = {l[1] for l in co.execute("PRAGMA table_info(signalements)")}
    assert {"source_position", "lieu_nom"} <= colonnes
    assert co.execute("SELECT source_position FROM signalements").fetchone() == ("gps",)
