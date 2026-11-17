"""Les autres atteintes à la salubrité : caniveaux, abattoirs clandestins, eaux usées.

Un dépotoir se ramasse, une fuite d'eau se répare. Ces quatre-là ne font ni l'un ni l'autre :
elles appellent chacune un service différent, et c'est tout l'intérêt de les distinguer. Un
caniveau bouché se cure, un abattoir clandestin se verbalise, un déversement de toilettes
relève de l'assainissement, des eaux usées de poissonnerie relèvent de l'hygiène.

La chaîne est donc toujours la même — la mairie reçoit et oriente, le service compétent
intervient — et c'est la **nature** du signalement qui désigne le service :

    signalé   ──►  confirmé et orienté  ──►  traité
    (habitant)     (agent de la mairie)      (le service que la nature désigne)

Ajouter une cinquième nuisance demain, c'est ajouter une entrée dans NATURES ci-dessous :
rien d'autre dans ce fichier ne connaît la liste.

Note pour la relecture : les fuites d'eau (application/fuites.py) suivent une chaîne de même
forme. Les deux modules pourraient n'en faire qu'un. Ils sont restés séparés parce que les
fuites étaient déjà en service et testées quand ces nuisances ont été ajoutées, et qu'on ne
réécrit pas du code qui tourne à deux jours d'une démonstration.
"""

import datetime
import json
import sqlite3

from .geo import distance_m, origines
from .signalements.controles import REJET

# Pour chaque nature : ce qu'on en dit, et surtout QUI intervient après la mairie.
# Cette répartition est une hypothèse de l'équipe, à confirmer avec la mairie de Ouagadougou ;
# la changer ne demande que de modifier la ligne « poste ».
NATURES = {
    "caniveau_bouche": {
        "nom": "Caniveau bouché",
        "poste": "collecte",
        "action": "Déclarer le curage fait",
        "explication": "L'équipe de collecte cure le caniveau et enlève ce qui l'obstrue.",
        "pourquoi": "Un caniveau bouché renvoie l'eau dans la rue et dans les cours dès la "
                    "première pluie, et l'eau stagnante élève les moustiques.",
    },
    "abattoir_clandestin": {
        "nom": "Abattoir clandestin d'animaux",
        "poste": "brigade",
        "action": "Déclarer le constat fait",
        "explication": "La brigade Laabal se rend sur place, constate, sensibilise et "
                       "verbalise. Elle en réfère au service vétérinaire.",
        "pourquoi": "Une bête abattue hors d'un abattoir n'est pas inspectée, et le sang et "
                    "les viscères sont abandonnés sur place.",
    },
    "toilettes_plein_air": {
        "nom": "Déversement de toilettes en plein air",
        "poste": "onea",
        "action": "Déclarer l'intervention faite",
        "explication": "L'ONEA intervient : c'est l'Office national de l'eau ET de "
                       "l'assainissement, la vidange des fosses relève de lui.",
        "pourquoi": "Des matières de vidange répandues dans la rue, c'est le choléra et la "
                    "fièvre typhoïde à portée de pied nu.",
    },
    "eaux_usees_animales": {
        "nom": "Eaux usées de poisson et de poulet",
        "poste": "brigade",
        "action": "Déclarer le constat fait",
        "explication": "La brigade Laabal constate, sensibilise le commerçant et verbalise "
                       "en cas de récidive.",
        "pourquoi": "Les eaux de lavage des poissonneries et des poulaillers attirent les "
                    "mouches et empestent tout un quartier.",
    },
}

# Trois niveaux, les mêmes pour toutes les natures : c'est au téléphone qu'ils sont formulés
# dans les mots de chacune (« un peu bouché » pour un caniveau, « un seau » pour des eaux usées).
GRAVITES = ("leger", "moyen", "grave")
URGENCE = {"grave": 3, "moyen": 2, "leger": 1}
GRAVITE_NOMS = {"leger": "Léger", "moyen": "Installé", "grave": "Grave"}

# La chaîne. Le poste de l'étape « confirme » n'est pas écrit ici : il dépend de la nature,
# et c'est _enrichir qui le pose sur chaque dossier.
CHAINE_NUISANCE = {
    "signale": {
        "nom": "Signalé", "poste": "mairie", "suivante": "confirme",
        "action": "Confirmer et orienter vers le service",
        "explication": "Un agent de la mairie vérifie le signalement et l'oriente vers le "
                       "service compétent.",
    },
    "confirme": {
        "nom": "Orienté vers le service", "poste": None, "suivante": "traite",
        "action": None, "explication": None,         # posés selon la nature
    },
    "traite": {
        "nom": "Traité", "poste": None, "suivante": None,
        "action": None, "explication": "Le service est intervenu. Le dossier est clos.",
    },
    "classe": {
        "nom": "Classé sans suite", "poste": None, "suivante": None,
        "action": None, "explication": "La mairie a classé le dossier : rien à constater sur "
                                       "place, ou signalement infondé.",
    },
}


class ErreurNuisance(Exception):
    pass


def maintenant() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def postes_concernes(poste: str) -> list:
    """Les natures dont ce poste a la charge une fois la mairie passée."""
    return [cle for cle, n in NATURES.items() if n["poste"] == poste]


class Nuisances:
    """Enregistrement, regroupement et suivi des nuisances.

    Même règle de regroupement que les dépotoirs et les fuites : deux personnes qui signalent
    la même chose ne créent pas deux dossiers. Mais le regroupement ne vaut qu'**à nature
    égale** — un caniveau bouché et un abattoir clandestin au même carrefour sont deux
    problèmes, deux services, deux dossiers."""

    RAYON_M = 60

    def __init__(self, connexion, parametres: dict):
        self.co = connexion
        self.rafale_max = parametres["controles"]["rafale_max"]
        self.rafale_min = parametres["controles"]["rafale_fenetre_min"]

    # ------------------------------------------------------------------ écriture
    def enregistrer(self, examine: dict, verifier_rafale: bool = True) -> dict:
        deja = self.deja_recu(examine.get("id_client"))
        if deja:
            return deja

        motifs = list(examine["motifs"])
        statut = examine["statut"]
        if verifier_rafale and statut != REJET and self.rafale(examine.get("source", "")):
            motifs.append("rafale_meme_source")
            statut = "a_verifier"

        try:
            curseur = self.co.execute(
                "INSERT INTO signalements (id_client, nature, latitude, longitude, precision_m,"
                " date_observation, date_reception, gravite, quartier, commentaire, photo,"
                " source, statut, motifs, declarant_nom, declarant_telephone, photo_cnib,"
                " photo_visage, message_vocal, source_position, lieu_nom, lot,"
                " visages_masques, plaques_masquees)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (examine.get("id_client"), examine.get("nature"), examine.get("latitude"),
                 examine.get("longitude"), examine.get("precision_m"),
                 examine.get("date_observation"), maintenant(), examine.get("gravite"),
                 examine.get("quartier"), examine.get("commentaire", ""), examine.get("photo"),
                 examine.get("source", "inconnue"), statut,
                 json.dumps(motifs, ensure_ascii=False),
                 examine.get("declarant_nom"), examine.get("declarant_telephone"),
                 examine.get("photo_cnib"), examine.get("photo_visage"),
                 examine.get("message_vocal"),
                 examine.get("source_position") or "gps", examine.get("lieu_nom"),
                 examine.get("lot"), examine.get("visages_masques"),
                 examine.get("plaques_masquees")))
        except sqlite3.IntegrityError:
            self.co.rollback()
            return self.deja_recu(examine.get("id_client")) or {
                "id": None, "statut": "rejete", "nouveau": False, "motifs": ["format_invalide"]}

        identifiant = curseur.lastrowid
        nuisance = self.rattacher(identifiant) if statut != REJET else None
        self.co.commit()
        statut_final = self.co.execute("SELECT statut FROM signalements WHERE id = ?",
                                       (identifiant,)).fetchone()["statut"]
        return {"id": identifiant, "nature": examine.get("nature"), "statut": statut_final,
                "nouveau": True, "motifs": motifs, "nuisance_id": nuisance}

    def deja_recu(self, id_client):
        if not id_client:
            return None
        deja = self.co.execute("SELECT id, nature, statut, motifs, nuisance_id FROM signalements"
                               " WHERE id_client = ?", (id_client,)).fetchone()
        if deja is None:
            return None
        return {"id": deja["id"], "nature": deja["nature"], "statut": deja["statut"],
                "nouveau": False, "motifs": json.loads(deja["motifs"] or "[]"),
                "nuisance_id": deja["nuisance_id"]}

    def rafale(self, source: str) -> bool:
        depuis = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(minutes=self.rafale_min)).isoformat(timespec="seconds")
        (nombre,) = self.co.execute(
            "SELECT COUNT(*) FROM signalements WHERE source = ? AND date_reception > ?",
            (source, depuis)).fetchone()
        return nombre >= self.rafale_max

    def rattacher(self, id_signalement: int):
        """Rattache le signalement à la nuisance proche DE MÊME NATURE, ou en ouvre une."""
        s = self.co.execute("SELECT * FROM signalements WHERE id = ?", (id_signalement,)).fetchone()
        if s["latitude"] is None or s["longitude"] is None:
            return None
        proche, distance_proche = None, None
        degre = self.RAYON_M / 111000 * 1.5
        for n in self.co.execute(
                "SELECT * FROM nuisances WHERE etat = 'active' AND nature = ?"
                " AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?",
                (s["nature"], s["latitude"] - degre, s["latitude"] + degre,
                 s["longitude"] - degre, s["longitude"] + degre)):
            distance = distance_m(s["longitude"], s["latitude"], n["longitude"], n["latitude"])
            if distance <= self.RAYON_M and (distance_proche is None or distance < distance_proche):
                proche, distance_proche = n, distance
        if proche is None:
            curseur = self.co.execute(
                "INSERT INTO nuisances (nature, latitude, longitude, premier_vu, dernier_vu)"
                " VALUES (?,?,?,?,?)",
                (s["nature"], s["latitude"], s["longitude"], s["date_observation"],
                 s["date_observation"]))
            identifiant = curseur.lastrowid
        else:
            identifiant = proche["id"]
        self.co.execute("UPDATE signalements SET nuisance_id = ? WHERE id = ?",
                        (identifiant, id_signalement))
        self.recalculer(identifiant)
        return identifiant

    def recalculer(self, id_nuisance: int) -> None:
        """Position, gravité et quartier, d'après les signalements retenus.

        Position au milieu (médiane) : un signalement décalé ne déplace pas le dossier. Gravité
        la PLUS forte signalée : c'est elle qui décide de l'ordre de passage du service."""
        lignes = self.co.execute(
            "SELECT latitude, longitude, source, lot, date_observation, gravite, quartier"
            " FROM signalements WHERE nuisance_id = ? AND statut <> 'rejete'",
            (id_nuisance,)).fetchall()
        if not lignes:
            self.co.execute("DELETE FROM nuisances WHERE id = ?", (id_nuisance,))
            return
        milieu = lambda valeurs: sorted(valeurs)[len(valeurs) // 2]
        sources = origines(lignes)
        dates = [l["date_observation"] for l in lignes if l["date_observation"]]
        gravites = [l["gravite"] for l in lignes if l["gravite"] in URGENCE]
        gravite = max(gravites, key=lambda g: URGENCE[g]) if gravites else None
        quartiers = [l["quartier"] for l in lignes if l["quartier"]]
        quartier = max(set(quartiers), key=quartiers.count) if quartiers else None
        self.co.execute(
            "UPDATE nuisances SET latitude = ?, longitude = ?, nb_signalements = ?,"
            " nb_sources = ?, premier_vu = ?, dernier_vu = ?, gravite = ?, quartier = ?"
            " WHERE id = ?",
            (milieu([l["latitude"] for l in lignes]), milieu([l["longitude"] for l in lignes]),
             len(lignes), len(sources), min(dates) if dates else None,
             max(dates) if dates else None, gravite, quartier, id_nuisance))
        if len(sources) >= 2:
            self.co.execute("UPDATE signalements SET statut = 'verifie'"
                            " WHERE nuisance_id = ? AND statut = 'recevable'", (id_nuisance,))

    # ------------------------------------------------------------------ lecture
    def liste(self, etape: str = None, poste: str = None, nature: str = None,
              limite: int = 300) -> list:
        requete = "SELECT * FROM nuisances"
        valeurs, conditions = [], []
        if nature:
            conditions.append("nature = ?")
            valeurs.append(nature)
        if etape:
            conditions.append("etape = ?")
            valeurs.append(etape)
        elif poste:
            # Ce qui attend ce poste : l'étape « signalé » est toujours à la mairie ; l'étape
            # « orienté » n'attend que le service dont la nature relève.
            morceaux = []
            if poste == "mairie":
                morceaux.append("etape = 'signale'")
            miennes = postes_concernes(poste)
            if miennes:
                morceaux.append("(etape = 'confirme' AND nature IN (%s))"
                                % ",".join("?" * len(miennes)))
                valeurs.extend(miennes)
            if not morceaux:
                return []
            conditions.append("(%s)" % " OR ".join(morceaux))
        if conditions:
            requete += " WHERE " + " AND ".join(conditions)
        requete += (" ORDER BY CASE gravite WHEN 'grave' THEN 3 WHEN 'moyen' THEN 2"
                    " WHEN 'leger' THEN 1 ELSE 0 END DESC, dernier_vu DESC LIMIT ?")
        valeurs.append(limite)
        return [self._enrichir(dict(l)) for l in self.co.execute(requete, valeurs)]

    def detail(self, id_nuisance: int, avec_declarants: bool = False) -> dict:
        ligne = self.co.execute("SELECT * FROM nuisances WHERE id = ?", (id_nuisance,)).fetchone()
        if ligne is None:
            raise ErreurNuisance("Signalement inconnu.")
        nuisance = self._enrichir(dict(ligne))
        nuisance["journal"] = [dict(l) for l in self.co.execute(
            "SELECT date, poste, auteur, etape, detail FROM journal_nuisance"
            " WHERE nuisance_id = ? ORDER BY id", (id_nuisance,))]
        colonnes = ("id, date_observation, date_reception, gravite, quartier, commentaire,"
                    " visages_masques, plaques_masquees,"
                    " photo, message_vocal, source, statut, motifs,"
                    " precision_m, source_position, lieu_nom")
        if avec_declarants:
            colonnes += ", declarant_nom, declarant_telephone, photo_cnib, photo_visage"
        signalements = [dict(l) for l in self.co.execute(
            f"SELECT {colonnes} FROM signalements WHERE nuisance_id = ? ORDER BY id",
            (id_nuisance,))]
        for s in signalements:
            s["motifs"] = json.loads(s.get("motifs") or "[]")
        nuisance["signalements"] = signalements
        return nuisance

    @staticmethod
    def _enrichir(nuisance: dict) -> dict:
        """Ajoute ce qui se déduit : le nom de la nature, et le service qui doit agir.

        Le poste de l'étape « orienté » ne peut pas être écrit dans CHAINE_NUISANCE, puisqu'il
        change avec la nature : c'est ici qu'il est posé, dossier par dossier."""
        description = NATURES.get(nuisance.get("nature"), {})
        etape = CHAINE_NUISANCE.get(nuisance.get("etape") or "signale",
                                    CHAINE_NUISANCE["signale"])
        nuisance["nature_nom"] = description.get("nom", "Nuisance")
        nuisance["pourquoi"] = description.get("pourquoi", "")
        nuisance["service"] = description.get("poste")
        nuisance["etape_nom"] = etape["nom"]
        if nuisance.get("etape") == "confirme":
            nuisance["poste_attendu"] = description.get("poste")
            nuisance["action_attendue"] = description.get("action")
            nuisance["explication_etape"] = description.get("explication")
        else:
            nuisance["poste_attendu"] = etape["poste"]
            nuisance["action_attendue"] = etape["action"]
            nuisance["explication_etape"] = etape["explication"]
        nuisance["gravite_nom"] = GRAVITE_NOMS.get(nuisance.get("gravite"), "Non précisée")
        return nuisance

    def comptes_par_etape(self) -> dict:
        comptes = {cle: 0 for cle in CHAINE_NUISANCE}
        for ligne in self.co.execute("SELECT etape, COUNT(*) n FROM nuisances GROUP BY etape"):
            comptes[ligne["etape"]] = ligne["n"]
        return comptes

    def comptes_par_nature(self) -> dict:
        comptes = {cle: 0 for cle in NATURES}
        for ligne in self.co.execute(
                "SELECT nature, COUNT(*) n FROM nuisances"
                " WHERE etat = 'active' AND etape <> 'classe' GROUP BY nature"):
            comptes[ligne["nature"]] = ligne["n"]
        return comptes

    def carte(self) -> list:
        """Les nuisances non traitées, pour la carte de décision."""
        return [self._enrichir(dict(l)) for l in self.co.execute(
            "SELECT * FROM nuisances WHERE etat = 'active' AND etape <> 'classe'")]

    # ------------------------------------------------------------------ chaîne
    def avancer(self, id_nuisance: int, poste: str, auteur: str, detail: str = "") -> dict:
        nuisance = self.detail(id_nuisance)
        etape_cle = nuisance["etape"]
        etape = CHAINE_NUISANCE.get(etape_cle, CHAINE_NUISANCE["signale"])
        if etape["suivante"] is None:
            raise ErreurNuisance("Ce dossier est déjà clos (%s)." % etape["nom"].lower())
        attendu = nuisance["poste_attendu"]
        if attendu != poste:
            raise ErreurNuisance(
                "C'est au poste « %s » d'agir à cette étape, pas à « %s »." % (attendu, poste))
        suivante = etape["suivante"]
        self.co.execute("UPDATE nuisances SET etape = ? WHERE id = ?", (suivante, id_nuisance))
        if suivante == "traite":
            self.co.execute("UPDATE nuisances SET etat = 'traitee' WHERE id = ?", (id_nuisance,))
        self._noter(id_nuisance, poste, auteur, suivante, detail)
        self.co.commit()
        return self.detail(id_nuisance)

    def classer(self, id_nuisance: int, poste: str, auteur: str, motif: str) -> dict:
        if poste != "mairie":
            raise ErreurNuisance("Seule la mairie peut classer un dossier sans suite.")
        nuisance = self.detail(id_nuisance)
        if nuisance["etape"] in ("traite", "classe"):
            raise ErreurNuisance("Ce dossier est déjà clos.")
        self.co.execute("UPDATE nuisances SET etape = 'classe', etat = 'traitee' WHERE id = ?",
                        (id_nuisance,))
        self._noter(id_nuisance, poste, auteur, "classe", motif or "sans motif précisé")
        self.co.commit()
        return self.detail(id_nuisance)

    def _noter(self, id_nuisance: int, poste: str, auteur: str, etape: str, detail: str) -> None:
        self.co.execute(
            "INSERT INTO journal_nuisance (nuisance_id, date, poste, auteur, etape, detail)"
            " VALUES (?,?,?,?,?,?)",
            (id_nuisance, maintenant(), poste, auteur, etape, (detail or "")[:500]))
