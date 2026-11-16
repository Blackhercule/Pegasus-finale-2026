"""Base de données : un seul fichier SQLite, créé au premier démarrage.

SQLite suffit largement ici : un poste, quelques milliers de signalements. Aucun service à
démarrer, donc une panne de moins le jour de la démonstration.
"""

import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS signalements (
    id                INTEGER PRIMARY KEY,
    id_client         TEXT UNIQUE,          -- identifiant donné par le téléphone : évite les doublons d'envoi
    latitude          REAL,
    longitude         REAL,
    precision_m       REAL,
    date_observation  TEXT,
    date_reception    TEXT NOT NULL,
    taille            TEXT,
    volume_m3         REAL,
    type              TEXT,
    commentaire       TEXT,
    photo             TEXT,
    source            TEXT NOT NULL,        -- pseudonyme de l'appareil ou nom du lot ; aucune donnée personnelle
    statut            TEXT NOT NULL,
    motifs            TEXT NOT NULL DEFAULT '',
    depotoir_id       INTEGER REFERENCES depotoirs(id)
);
CREATE INDEX IF NOT EXISTS i_signalements_statut ON signalements(statut);
CREATE INDEX IF NOT EXISTS i_signalements_source ON signalements(source, date_reception);
CREATE INDEX IF NOT EXISTS i_signalements_depotoir ON signalements(depotoir_id);

CREATE TABLE IF NOT EXISTS depotoirs (
    id              INTEGER PRIMARY KEY,
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    volume_m3       REAL NOT NULL DEFAULT 0,
    nb_signalements INTEGER NOT NULL DEFAULT 0,
    nb_sources      INTEGER NOT NULL DEFAULT 0,
    premier_vu      TEXT,
    dernier_vu      TEXT,
    etat            TEXT NOT NULL DEFAULT 'actif'   -- actif | nettoye
);
"""


def connexion(chemin: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(chemin)), exist_ok=True)
    co = sqlite3.connect(chemin, timeout=10)
    co.row_factory = sqlite3.Row
    co.execute("PRAGMA foreign_keys = ON")
    co.execute("PRAGMA journal_mode = WAL")      # lecture pendant l'écriture : l'interface reste fluide
    return co


def creer(chemin: str) -> None:
    co = connexion(chemin)
    with co:
        co.executescript(SCHEMA)
    co.close()
