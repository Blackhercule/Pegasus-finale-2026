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
    source            TEXT NOT NULL,        -- pseudonyme de l'appareil ou nom du lot
    statut            TEXT NOT NULL,
    motifs            TEXT NOT NULL DEFAULT '',
    depotoir_id       INTEGER REFERENCES depotoirs(id),
    -- Dépôt : à même le sol, dans un bac, dans un caniveau… et dimensions estimées au sol.
    depot             TEXT,
    longueur_m        REAL,
    largeur_m         REAL,
    -- Identification FACULTATIVE du déclarant, s'il accepte d'être témoin dans une procédure.
    -- Ces champs ne sont jamais servis au public : seuls les agents connectés y accèdent.
    declarant_nom     TEXT,
    declarant_telephone TEXT,
    photo_cnib        TEXT,
    photo_visage      TEXT,
    message_vocal     TEXT
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
    etat            TEXT NOT NULL DEFAULT 'actif',  -- actif | nettoye
    -- Avancement du dossier, de la déclaration jusqu'au ramassage.
    etape           TEXT NOT NULL DEFAULT 'signale',
    surface_m2      REAL,
    depot           TEXT
);

-- Qui a fait quoi, et quand : la chaîne de responsabilité se relit entièrement.
CREATE TABLE IF NOT EXISTS journal_dossier (
    id          INTEGER PRIMARY KEY,
    depotoir_id INTEGER NOT NULL REFERENCES depotoirs(id) ON DELETE CASCADE,
    date        TEXT NOT NULL,
    poste       TEXT NOT NULL,          -- mairie | brigade | collecte
    auteur      TEXT NOT NULL,
    etape       TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS i_journal_depotoir ON journal_dossier(depotoir_id);
"""


def connexion(chemin: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(chemin)), exist_ok=True)
    co = sqlite3.connect(chemin, timeout=10)
    co.row_factory = sqlite3.Row
    co.execute("PRAGMA foreign_keys = ON")
    co.execute("PRAGMA journal_mode = WAL")      # lecture pendant l'écriture : l'interface reste fluide
    return co


# Colonnes ajoutées après coup : une base déjà installée doit continuer de fonctionner.
AJOUTS = {
    "signalements": [("depot", "TEXT"), ("longueur_m", "REAL"), ("largeur_m", "REAL"),
                     ("declarant_nom", "TEXT"), ("declarant_telephone", "TEXT"),
                     ("photo_cnib", "TEXT"), ("photo_visage", "TEXT"), ("message_vocal", "TEXT")],
    "depotoirs": [("etape", "TEXT NOT NULL DEFAULT 'signale'"), ("surface_m2", "REAL"),
                  ("depot", "TEXT")],
}


def creer(chemin: str) -> None:
    co = connexion(chemin)
    with co:
        co.executescript(SCHEMA)
        for table, colonnes in AJOUTS.items():
            existantes = {l["name"] for l in co.execute(f"PRAGMA table_info({table})")}
            for nom, genre in colonnes:
                if nom not in existantes:
                    co.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {genre}")
    co.close()
