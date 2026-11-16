"""Regroupement des signalements en dépotoirs, et enregistrement en base.

Deux personnes qui signalent le même tas de déchets ne créent pas deux dépotoirs : le second
signalement CONFIRME le premier. Et un dépotoir confirmé par deux appareils différents passe à
« vérifié » sans qu'un agent ait à trancher.
"""

import datetime
import json
import sqlite3

from ..geo import distance_m
from .controles import REJET


class Depotoirs:
    def __init__(self, connexion, parametres: dict):
        self.co = connexion
        self.rayon_m = parametres["controles"]["rayon_regroupement_m"]
        self.rafale_max = parametres["controles"]["rafale_max"]
        self.rafale_min = parametres["controles"]["rafale_fenetre_min"]

    # ------------------------------------------------------------------ écriture
    def enregistrer(self, examine: dict, verifier_rafale: bool = True) -> dict:
        """Range un signalement déjà contrôlé. Renvoie ce qu'il faut répondre à l'appareil.

        `verifier_rafale` protège l'adresse publique : un téléphone qui envoie des dizaines de
        signalements en quelques minutes est suspect. Un lot chargé par un agent est au
        contraire volumineux par nature : chaque ligne y est jugée sur ses propres contrôles."""
        deja = self.deja_recu(examine.get("id_client"))
        if deja:                           # même envoi reçu deux fois : on ne compte pas deux fois
            return deja

        motifs = list(examine["motifs"])
        statut = examine["statut"]
        if verifier_rafale and statut != REJET and self.rafale(examine["source"]):
            motifs.append("rafale_meme_source")
            statut = "a_verifier"

        recu = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        try:
            curseur = self.co.execute(
                "INSERT INTO signalements (id_client, latitude, longitude, precision_m, date_observation,"
                " date_reception, taille, volume_m3, type, commentaire, photo, source, statut, motifs)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (examine.get("id_client"), examine.get("latitude"), examine.get("longitude"),
                 examine.get("precision_m"), examine.get("date_observation"), recu,
                 examine.get("taille"), examine.get("volume_m3"), examine.get("type"),
                 examine.get("commentaire", ""), examine.get("photo"), examine.get("source", "inconnue"),
                 statut, json.dumps(motifs, ensure_ascii=False)))
        except sqlite3.IntegrityError:
            # Le même envoi est arrivé deux fois en même temps (réseau qui revient, double appui) :
            # le premier a gagné, on renvoie simplement son résultat.
            self.co.rollback()
            return self.deja_recu(examine.get("id_client")) or {
                "id": None, "statut": "rejete", "nouveau": False, "motifs": ["format_invalide"]}
        identifiant = curseur.lastrowid
        depotoir = self.rattacher(identifiant) if statut != REJET else None
        self.co.commit()
        return {"id": identifiant, "statut": self.statut_actuel(identifiant), "nouveau": True,
                "motifs": motifs, "depotoir_id": depotoir}

    def deja_recu(self, id_client):
        """Ce signalement est-il déjà en base ? (même identifiant d'envoi)"""
        if not id_client:
            return None
        deja = self.co.execute("SELECT id, statut, motifs, depotoir_id FROM signalements"
                               " WHERE id_client = ?", (id_client,)).fetchone()
        if deja is None:
            return None
        return {"id": deja["id"], "statut": deja["statut"], "nouveau": False,
                "motifs": json.loads(deja["motifs"] or "[]"), "depotoir_id": deja["depotoir_id"]}

    def rafale(self, source: str) -> bool:
        """Beaucoup d'envois d'un même appareil en quelques minutes : un humain regarde."""
        depuis = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(minutes=self.rafale_min)).isoformat(timespec="seconds")
        (nombre,) = self.co.execute("SELECT COUNT(*) FROM signalements WHERE source = ? AND date_reception > ?",
                                    (source, depuis)).fetchone()
        return nombre >= self.rafale_max

    def rattacher(self, id_signalement: int):
        """Rattache le signalement au dépotoir proche, ou en crée un. Renvoie l'identifiant du dépotoir."""
        s = self.co.execute("SELECT * FROM signalements WHERE id = ?", (id_signalement,)).fetchone()
        if s["latitude"] is None or s["longitude"] is None:
            return None
        proche, distance_proche = None, None
        # Les dépotoirs tiennent dans un rectangle d'un demi-degré : on ne compare qu'aux voisins.
        degre = self.rayon_m / 111000 * 1.5
        for d in self.co.execute(
                "SELECT * FROM depotoirs WHERE etat = 'actif' AND latitude BETWEEN ? AND ?"
                " AND longitude BETWEEN ? AND ?",
                (s["latitude"] - degre, s["latitude"] + degre, s["longitude"] - degre, s["longitude"] + degre)):
            distance = distance_m(s["longitude"], s["latitude"], d["longitude"], d["latitude"])
            if distance <= self.rayon_m and (distance_proche is None or distance < distance_proche):
                proche, distance_proche = d, distance
        if proche is None:
            curseur = self.co.execute(
                "INSERT INTO depotoirs (latitude, longitude, premier_vu, dernier_vu) VALUES (?,?,?,?)",
                (s["latitude"], s["longitude"], s["date_observation"], s["date_observation"]))
            identifiant = curseur.lastrowid
        else:
            identifiant = proche["id"]
        self.co.execute("UPDATE signalements SET depotoir_id = ? WHERE id = ?", (identifiant, id_signalement))
        self.recalculer(identifiant)
        return identifiant

    def recalculer(self, id_depotoir: int) -> None:
        """Position, volume et dates d'un dépotoir, à partir de ses signalements retenus.

        Position et volume sont pris au milieu (médiane) : un signalement très décalé ou un
        volume exagéré ne déplace pas le dépotoir ni ne gonfle le total."""
        lignes = self.co.execute(
            "SELECT latitude, longitude, volume_m3, source, date_observation FROM signalements"
            " WHERE depotoir_id = ? AND statut <> 'rejete'", (id_depotoir,)).fetchall()
        if not lignes:
            self.co.execute("DELETE FROM depotoirs WHERE id = ?", (id_depotoir,))
            return
        milieu = lambda valeurs: sorted(valeurs)[len(valeurs) // 2]
        volumes = [l["volume_m3"] for l in lignes if l["volume_m3"] is not None]
        sources = {l["source"] for l in lignes}
        dates = [l["date_observation"] for l in lignes if l["date_observation"]]
        self.co.execute(
            "UPDATE depotoirs SET latitude = ?, longitude = ?, volume_m3 = ?, nb_signalements = ?,"
            " nb_sources = ?, premier_vu = ?, dernier_vu = ? WHERE id = ?",
            (milieu([l["latitude"] for l in lignes]), milieu([l["longitude"] for l in lignes]),
             milieu(volumes) if volumes else 0, len(lignes), len(sources),
             min(dates) if dates else None, max(dates) if dates else None, id_depotoir))
        # Deux appareils différents qui voient le même tas : la confirmation vaut vérification.
        if len(sources) >= 2:
            self.co.execute("UPDATE signalements SET statut = 'verifie'"
                            " WHERE depotoir_id = ? AND statut = 'recevable'", (id_depotoir,))

    def decider(self, id_signalement: int, verifie: bool) -> bool:
        """Décision d'un agent : « vérifié » ou « rejeté »."""
        s = self.co.execute("SELECT depotoir_id FROM signalements WHERE id = ?", (id_signalement,)).fetchone()
        if s is None:
            return False
        if verifie:
            self.co.execute("UPDATE signalements SET statut = 'verifie' WHERE id = ?", (id_signalement,))
            if s["depotoir_id"] is None:
                self.rattacher(id_signalement)
        else:
            motifs = json.dumps(["decision_agent"], ensure_ascii=False)
            self.co.execute("UPDATE signalements SET statut = 'rejete', motifs = ?, depotoir_id = NULL"
                            " WHERE id = ?", (motifs, id_signalement))
        if s["depotoir_id"] is not None:
            self.recalculer(s["depotoir_id"])
        self.co.commit()
        return True

    def statut_actuel(self, id_signalement: int) -> str:
        return self.co.execute("SELECT statut FROM signalements WHERE id = ?",
                               (id_signalement,)).fetchone()["statut"]

    # ------------------------------------------------------------------ lecture
    def liste(self, statut: str = None, limite: int = 500) -> list:
        requete = "SELECT * FROM signalements"
        valeurs = []
        if statut:
            requete += " WHERE statut = ?"
            valeurs.append(statut)
        requete += " ORDER BY id DESC LIMIT ?"
        valeurs.append(limite)
        lignes = [dict(l) for l in self.co.execute(requete, valeurs)]
        for l in lignes:
            l["motifs"] = json.loads(l["motifs"] or "[]")
        return lignes

    def retenus(self, mode_strict: bool) -> list:
        """Les dépotoirs qui entrent dans le plan de gestion."""
        statuts = ("verifie",) if mode_strict else ("verifie", "recevable")
        trous = ",".join("?" * len(statuts))
        return [dict(l) for l in self.co.execute(
            f"SELECT d.* FROM depotoirs d WHERE d.etat = 'actif' AND EXISTS ("
            f"  SELECT 1 FROM signalements s WHERE s.depotoir_id = d.id AND s.statut IN ({trous}))"
            " ORDER BY d.volume_m3 DESC", statuts)]

    def comptes(self) -> dict:
        lignes = self.co.execute("SELECT statut, COUNT(*) n FROM signalements GROUP BY statut").fetchall()
        comptes = {l["statut"]: l["n"] for l in lignes}
        (comptes["depotoirs"],) = self.co.execute("SELECT COUNT(*) FROM depotoirs WHERE etat = 'actif'").fetchone()
        return comptes
