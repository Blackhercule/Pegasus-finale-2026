"""Une base déjà installée doit devenir identique à une base neuve.

Pourquoi ce test existe : le 17/11, l'envoi de signalements est tombé sur le PC de l'équipe
avec « table signalements has no column named lot ». Trois colonnes (lot, visages_masques,
plaques_masquees) avaient été ajoutées au schéma d'une base NEUVE, mais jamais à la liste
AJOUTS qui met à niveau une base EXISTANTE. Tous les tests passaient, parce qu'ils partent tous
d'une base neuve. Seule une vraie installation, qui garde sa base d'un jour à l'autre, voyait
la panne — c'est-à-dire exactement la machine de la démonstration.

Ce test ne vérifie pas une colonne en particulier : il compare TOUTES les colonnes. Le jour où
quelqu'un ajoute une colonne au schéma et oublie AJOUTS, il échoue, quelle que soit la colonne.
"""

import sqlite3

from application.base import creer

# Le tout premier schéma, celui du commit e0dea95 : c'est de là que part toute base installée.
SCHEMA_D_ORIGINE = """
CREATE TABLE signalements (
    id INTEGER PRIMARY KEY, id_client TEXT UNIQUE, latitude REAL, longitude REAL,
    precision_m REAL, date_observation TEXT, date_reception TEXT NOT NULL, taille TEXT,
    volume_m3 REAL, type TEXT, commentaire TEXT, photo TEXT, source TEXT NOT NULL,
    statut TEXT NOT NULL, motifs TEXT NOT NULL DEFAULT '',
    depotoir_id INTEGER REFERENCES depotoirs(id));
CREATE TABLE depotoirs (
    id INTEGER PRIMARY KEY, latitude REAL NOT NULL, longitude REAL NOT NULL,
    volume_m3 REAL NOT NULL DEFAULT 0, nb_signalements INTEGER NOT NULL DEFAULT 0,
    nb_sources INTEGER NOT NULL DEFAULT 0, premier_vu TEXT, dernier_vu TEXT,
    etat TEXT NOT NULL DEFAULT 'actif');
INSERT INTO signalements (id_client, latitude, longitude, date_reception, source, statut)
    VALUES ('d-avant', 12.3714, -1.5197, '2026-11-15T08:00:00+00:00', 'tel', 'verifie');
"""


def colonnes(chemin: str) -> dict:
    co = sqlite3.connect(chemin)
    tables = [t for (t,) in co.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    resultat = {t: {ligne[1] for ligne in co.execute(f"PRAGMA table_info({t})")} for t in tables}
    co.close()
    return resultat


def test_une_base_ancienne_mise_a_niveau_a_toutes_les_colonnes_d_une_neuve(tmp_path):
    neuve = str(tmp_path / "neuve.sqlite")
    creer(neuve)

    ancienne = str(tmp_path / "ancienne.sqlite")
    co = sqlite3.connect(ancienne)
    co.executescript(SCHEMA_D_ORIGINE)
    co.commit()
    co.close()
    creer(ancienne)

    attendu, obtenu = colonnes(neuve), colonnes(ancienne)
    for table, cols in attendu.items():
        manquantes = cols - obtenu.get(table, set())
        assert not manquantes, (
            f"Une base déjà installée n'aura jamais les colonnes {sorted(manquantes)} de la "
            f"table « {table} » : ajoutez-les à AJOUTS dans application/base.py.")


def test_une_base_ancienne_mise_a_niveau_garde_ses_donnees(tmp_path):
    ancienne = str(tmp_path / "ancienne.sqlite")
    co = sqlite3.connect(ancienne)
    co.executescript(SCHEMA_D_ORIGINE)
    co.commit()
    co.close()
    creer(ancienne)
    creer(ancienne)                    # une seconde fois : le démarrage suivant ne doit rien casser
    co = sqlite3.connect(ancienne)
    (combien,) = co.execute("SELECT COUNT(*) FROM signalements").fetchone()
    co.close()
    assert combien == 1


def test_on_peut_signaler_sur_une_base_mise_a_niveau(tmp_path, monkeypatch):
    """Le parcours exact qui est tombé sur le PC : une base d'hier, et un signalement de chaque
    nature, avec photo, envoyé seul puis en lot."""
    import io

    import numpy as np

    from application import creer_application
    from application.reglages import Reglages

    chemin = str(tmp_path / "ancienne.sqlite")
    co = sqlite3.connect(chemin)
    co.executescript(SCHEMA_D_ORIGINE)
    co.commit()
    co.close()

    monkeypatch.setenv("AGENT_MOT_DE_PASSE", "essai")
    monkeypatch.setenv("SECRET_SESSION", "essai")
    client = creer_application(Reglages(base=chemin)).test_client()

    base = {"latitude": 12.3714, "longitude": -1.5197, "source": "tel"}
    envois = [
        {**base, "taille": "grand", "id_client": "o"},
        {**base, "nature": "fuite_eau", "ampleur": "jet", "id_client": "f"},
        {**base, "nature": "caniveau_bouche", "gravite": "moyen", "id_client": "n"},
    ]
    for envoi in envois:
        r = client.post("/api/signalements", json=envoi)
        assert r.status_code in (200, 201), (envoi["id_client"], r.get_data(as_text=True)[-300:])

    try:
        import cv2
        image = cv2.imencode(".jpg", np.zeros((200, 200, 3), np.uint8))[1].tobytes()
    except ImportError:
        image = b"\xff\xd8\xff" + b"0" * 300
    r = client.post("/api/signalements", data={
        **{k: str(v) for k, v in base.items()}, "taille": "moyen", "id_client": "p",
        "photo": (io.BytesIO(image), "tas.jpg")}, content_type="multipart/form-data")
    assert r.status_code in (200, 201), r.get_data(as_text=True)[-300:]

    r = client.post("/api/signalements/lot", json=[{**base, "taille": "petit", "id_client": "l"}])
    assert r.status_code == 200, r.get_data(as_text=True)[-300:]
