"""Fuites d'eau : contrôles, regroupement, chaîne mairie → ONEA, bordereau.

Une fuite suit son propre chemin : elle ne devient jamais un dépotoir et n'entre jamais dans
les tournées des camions. Ces tests vérifient surtout cela, parce que c'est ce qui casserait
le plan de gestion si on se trompait.
"""

import io

from conftest import MOT_DE_PASSE

FUITE = {"nature": "fuite_eau", "latitude": 12.3714, "longitude": -1.5197,
         "ampleur": "jet", "quartier": "Tanghin", "source": "tel-a", "id_client": "f1"}


def signaler(client, **champs):
    return client.post("/api/signalements", json={**FUITE, **champs})


def connecter(client, nom, mot_de_passe):
    reponse = client.post("/api/connexion", json={"nom": nom, "mot_de_passe": mot_de_passe})
    if reponse.status_code == 200:
        client.environ_base["HTTP_X_JETON"] = reponse.get_json()["jeton"]
    return reponse


def test_une_fuite_s_enregistre_et_n_est_pas_un_depotoir(client):
    reponse = signaler(client)
    assert reponse.status_code == 201
    corps = reponse.get_json()
    assert corps["nature"] == "fuite_eau" and corps["fuite_id"] == 1
    # Le plan de gestion ne doit rien voir passer : une fuite n'est pas un tas à ramasser.
    assert client.get("/api/depotoirs").get_json()["features"] == []
    assert client.get("/api/comptes").get_json().get("depotoirs", 0) == 0


def test_deux_appareils_confirment_la_meme_fuite(client):
    signaler(client, source="tel-a", id_client="f1")
    deuxieme = signaler(client, latitude=12.37145, source="tel-b", id_client="f2",
                        ampleur="inondation")
    assert deuxieme.get_json()["fuite_id"] == 1          # moins de 40 m : c'est la même fuite
    assert deuxieme.get_json()["statut"] == "verifie"    # deux sources : confirmée
    fuite = client.get("/api/fuites").get_json()[0]
    # L'ampleur retenue est la plus grave signalée : c'est elle qui décide de l'urgence.
    assert fuite["ampleur"] == "inondation"
    assert fuite["nb_sources"] == 2


def test_une_fuite_loin_ouvre_un_autre_dossier(client):
    signaler(client, source="a", id_client="f1")
    signaler(client, latitude=12.40, longitude=-1.50, source="b", id_client="f2")
    assert len(client.get("/api/fuites").get_json()) == 2


def test_ampleur_absente_ou_inventee_est_rejetee(client):
    for mauvaise in (None, "catastrophe", 42, ""):
        reponse = signaler(client, ampleur=mauvaise, id_client="x%s" % mauvaise)
        corps = reponse.get_json()
        assert corps["statut"] == "rejete"
        assert "ampleur_invalide" in corps["motifs"]


def test_une_fuite_subit_les_memes_controles_de_position(client):
    """Les pièges du jury valent aussi pour les fuites : mêmes contrôles, mêmes motifs."""
    pieges = [
        ({"latitude": 0, "longitude": 0}, "coordonnees_invalides"),
        ({"latitude": "abc"}, "format_invalide"),
        ({"latitude": 48.85, "longitude": 2.35}, "hors_commune"),
        ({"latitude": -1.5197, "longitude": 12.3714}, "coordonnees_inversees"),
        ({"date_observation": "2030-01-01T00:00:00Z"}, "date_future"),
    ]
    for n, (champs, motif) in enumerate(pieges):
        corps = signaler(client, id_client="p%d" % n, **champs).get_json()
        assert motif in corps["motifs"], (champs, corps)
        assert corps["statut"] == "rejete"
    assert client.get("/api/fuites").get_json() == []


def test_la_chaine_va_de_la_mairie_a_l_onea(client):
    signaler(client)
    connecter(client, "agent", MOT_DE_PASSE)
    fuite = client.post("/api/fuites/1/avancer", json={"detail": "BORD-2026-11"}).get_json()
    assert fuite["etape"] == "transmis"
    assert fuite["reference_onea"] == "BORD-2026-11"

    # La mairie ne peut pas déclarer la réparation à la place de l'ONEA.
    assert client.post("/api/fuites/1/avancer", json={}).status_code == 400

    client.post("/api/deconnexion")
    connecter(client, "onea", "essai-onea")
    fuite = client.post("/api/fuites/1/avancer", json={"detail": "conduite remplacée"}).get_json()
    assert fuite["etape"] == "repare"
    assert fuite["etat"] == "reparee"
    # Tout le parcours est relisible : qui, quand, quoi.
    assert [e["poste"] for e in fuite["journal"]] == ["mairie", "onea"]
    # Une fois réparée, elle sort de la carte.
    assert client.get("/api/fuites/carte").get_json()["features"] == []


def test_l_onea_ne_peut_pas_agir_avant_la_mairie(client):
    signaler(client)
    connecter(client, "onea", "essai-onea")
    reponse = client.post("/api/fuites/1/avancer", json={})
    assert reponse.status_code == 400
    assert "mairie" in reponse.get_json()["erreur"]


def test_sans_connexion_on_ne_fait_rien_avancer(client):
    signaler(client)
    assert client.post("/api/fuites/1/avancer", json={}).status_code == 401
    assert client.post("/api/fuites/1/classer", json={"motif": "rien"}).status_code == 401


def test_seule_la_mairie_classe_sans_suite(client):
    signaler(client)
    connecter(client, "onea", "essai-onea")
    assert client.post("/api/fuites/1/classer", json={"motif": "bof"}).status_code == 403
    client.post("/api/deconnexion")
    connecter(client, "agent", MOT_DE_PASSE)
    fuite = client.post("/api/fuites/1/classer", json={"motif": "pas de fuite sur place"}).get_json()
    assert fuite["etape"] == "classe"


def test_le_bordereau_onea_est_un_csv_lisible(client):
    signaler(client, source="a", id_client="f1")
    signaler(client, latitude=12.40, longitude=-1.50, source="b", id_client="f2",
             ampleur="inondation", quartier="Nioko II")
    reponse = client.get("/api/export/onea")
    assert reponse.status_code == 200
    assert reponse.headers["X-Fuites"] == "2"
    texte = reponse.get_data(as_text=True)
    assert texte.startswith("﻿")                 # pour que Excel lise les accents
    lignes = texte.strip().splitlines()
    assert lignes[0].count(";") == 10
    assert "FUITE-00001" in texte and "Nioko II" in texte
    # Une fuite déjà transmise ne revient pas dans le bordereau des fuites à transmettre.
    connecter(client, "agent", MOT_DE_PASSE)
    client.post("/api/fuites/1/avancer", json={})
    assert client.get("/api/export/onea").headers["X-Fuites"] == "1"


def test_l_identite_du_declarant_reste_cachee_du_public(client):
    signaler(client, declarant_nom="Awa", declarant_telephone="70000000")
    public = client.get("/api/fuites/1").get_json()["signalements"][0]
    assert "declarant_nom" not in public
    connecter(client, "agent", MOT_DE_PASSE)
    prive = client.get("/api/fuites/1").get_json()["signalements"][0]
    assert prive["declarant_nom"] == "Awa"


def test_une_fuite_accepte_photo_et_message_vocal(client):
    image = b"\xff\xd8\xff" + b"0" * 300
    son = b"\x1aE\xdf\xa3" + b"0" * 300
    reponse = client.post("/api/signalements", data={
        "nature": "fuite_eau", "latitude": "12.3714", "longitude": "-1.5197",
        "ampleur": "jet", "quartier": "Tanghin", "source": "a", "id_client": "f1",
        "photo": (io.BytesIO(image), "fuite.jpg"),
        "message_vocal": (io.BytesIO(son), "voix.webm"),
    }, content_type="multipart/form-data")
    assert reponse.status_code == 201
    connecter(client, "agent", MOT_DE_PASSE)
    s = client.get("/api/fuites/1").get_json()["signalements"][0]
    assert s["photo"].startswith("public/")
    assert s["message_vocal"].startswith("prive/")     # une voix reste une donnée sensible


def test_le_meme_envoi_deux_fois_ne_compte_qu_une_fois(client):
    assert signaler(client).status_code == 201
    repete = signaler(client)
    assert repete.status_code == 200
    assert repete.get_json()["nouveau"] is False
    assert len(client.get("/api/fuites").get_json()) == 1


def test_un_signalement_d_ordures_n_apparait_pas_dans_les_fuites(client):
    client.post("/api/signalements", json={
        "latitude": 12.3714, "longitude": -1.5197, "taille": "grand",
        "source": "a", "id_client": "o1"})
    assert client.get("/api/fuites").get_json() == []
    assert len(client.get("/api/depotoirs").get_json()["features"]) == 1


def test_une_base_deja_installee_accepte_les_fuites(tmp_path):
    """Sur le PC, la base existe déjà avec des signalements : l'ajout des fuites ne doit ni
    la refuser ni perdre ce qu'elle contient."""
    import sqlite3

    from application.base import creer

    chemin = str(tmp_path / "ancienne.sqlite")
    ancienne = sqlite3.connect(chemin)
    # Le schéma tel qu'il était avant les fuites : ni nature, ni fuite_id.
    ancienne.executescript("""
        CREATE TABLE signalements (id INTEGER PRIMARY KEY, id_client TEXT UNIQUE,
            latitude REAL, longitude REAL, date_reception TEXT NOT NULL,
            source TEXT NOT NULL, statut TEXT NOT NULL, motifs TEXT NOT NULL DEFAULT '',
            depotoir_id INTEGER);
        CREATE TABLE depotoirs (id INTEGER PRIMARY KEY, latitude REAL NOT NULL,
            longitude REAL NOT NULL);
        INSERT INTO signalements (id_client, latitude, longitude, date_reception, source, statut)
            VALUES ('ancien', 12.37, -1.52, '2026-11-01T08:00:00+00:00', 'tel', 'verifie');
    """)
    ancienne.commit()
    ancienne.close()

    creer(chemin)                                   # la mise à niveau ne doit pas lever

    co = sqlite3.connect(chemin)
    colonnes = {l[1] for l in co.execute("PRAGMA table_info(signalements)")}
    assert {"nature", "fuite_id", "ampleur", "quartier"} <= colonnes
    (reste,) = co.execute("SELECT COUNT(*) FROM signalements").fetchone()
    assert reste == 1                               # le signalement d'avant est toujours là
    (nature,) = co.execute("SELECT nature FROM signalements").fetchone()
    assert nature == "ordures"                      # les anciens sont des tas d'ordures
    co.close()
