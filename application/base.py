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
    -- Ce qui est signalé : un tas d'ordures, ou une fuite sur une conduite d'eau (ONEA).
    nature            TEXT NOT NULL DEFAULT 'ordures',
    fuite_id          INTEGER REFERENCES fuites(id),
    ampleur           TEXT,                 -- fuites : suintement | jet | inondation
    quartier          TEXT,                 -- quartier donné par le déclarant
    nuisance_id       INTEGER REFERENCES nuisances(id),
    gravite           TEXT,                 -- nuisances : leger | moyen | grave
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

-- Fuites sur le réseau d'eau potable. Elles ne vont pas dans les tournées des camions : elles
-- sont transmises à l'ONEA, qui seul intervient sur ses conduites. Une fuite qui coule des
-- jours fait une mare, et une mare dans un quartier, ce sont des moustiques et une chaussée
-- qui se creuse : c'est pourquoi l'assainissement s'en occupe.
CREATE TABLE IF NOT EXISTS fuites (
    id              INTEGER PRIMARY KEY,
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    quartier        TEXT,
    ampleur         TEXT,                           -- suintement | jet | inondation
    nb_signalements INTEGER NOT NULL DEFAULT 0,
    nb_sources      INTEGER NOT NULL DEFAULT 0,
    premier_vu      TEXT,
    dernier_vu      TEXT,
    etat            TEXT NOT NULL DEFAULT 'active', -- active | reparee
    etape           TEXT NOT NULL DEFAULT 'signale',
    reference_onea  TEXT                            -- numéro rendu par l'ONEA à la transmission
);
CREATE TABLE IF NOT EXISTS journal_fuite (
    id        INTEGER PRIMARY KEY,
    fuite_id  INTEGER NOT NULL REFERENCES fuites(id) ON DELETE CASCADE,
    date      TEXT NOT NULL,
    poste     TEXT NOT NULL,                        -- mairie | onea
    auteur    TEXT NOT NULL,
    etape     TEXT NOT NULL,
    detail    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS i_journal_fuite ON journal_fuite(fuite_id);

-- Les autres atteintes à la salubrité : caniveau bouché, abattoir clandestin, déversement de
-- toilettes en plein air, eaux usées de poisson et de poulet. Elles ne se ramassent pas comme
-- un tas et ne se réparent pas comme une conduite : chacune appelle un service, et c'est la
-- nature du signalement qui désigne lequel (voir application/nuisances.py).
CREATE TABLE IF NOT EXISTS nuisances (
    id              INTEGER PRIMARY KEY,
    nature          TEXT NOT NULL,
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    quartier        TEXT,
    gravite         TEXT,                           -- leger | moyen | grave
    nb_signalements INTEGER NOT NULL DEFAULT 0,
    nb_sources      INTEGER NOT NULL DEFAULT 0,
    premier_vu      TEXT,
    dernier_vu      TEXT,
    etat            TEXT NOT NULL DEFAULT 'active', -- active | traitee
    etape           TEXT NOT NULL DEFAULT 'signale'
);

CREATE TABLE IF NOT EXISTS journal_nuisance (
    id          INTEGER PRIMARY KEY,
    nuisance_id INTEGER NOT NULL REFERENCES nuisances(id) ON DELETE CASCADE,
    date        TEXT NOT NULL,
    poste       TEXT NOT NULL,
    auteur      TEXT NOT NULL,
    etape       TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS i_journal_nuisance ON journal_nuisance(nuisance_id);
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
                     ("photo_cnib", "TEXT"), ("photo_visage", "TEXT"), ("message_vocal", "TEXT"),
                     ("nature", "TEXT NOT NULL DEFAULT 'ordures'"), ("fuite_id", "INTEGER"),
                     ("ampleur", "TEXT"), ("quartier", "TEXT"),
                     ("nuisance_id", "INTEGER"), ("gravite", "TEXT")],
    "depotoirs": [("etape", "TEXT NOT NULL DEFAULT 'signale'"), ("surface_m2", "REAL"),
                  ("depot", "TEXT")],
}


INDEX_APRES_AJOUTS = (
    "CREATE INDEX IF NOT EXISTS i_signalements_fuite ON signalements(fuite_id)",
    "CREATE INDEX IF NOT EXISTS i_signalements_nuisance ON signalements(nuisance_id)",
)


def creer(chemin: str) -> None:
    co = connexion(chemin)
    with co:
        co.executescript(SCHEMA)
        for table, colonnes in AJOUTS.items():
            existantes = {l["name"] for l in co.execute(f"PRAGMA table_info({table})")}
            for nom, genre in colonnes:
                if nom not in existantes:
                    co.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {genre}")
        # Ces index portent sur des colonnes ajoutées après coup : ils se créent une fois les
        # colonnes en place, sinon une base déjà installée refuserait de s'ouvrir.
        for index in INDEX_APRES_AJOUTS:
            co.execute(index)
    co.close()
