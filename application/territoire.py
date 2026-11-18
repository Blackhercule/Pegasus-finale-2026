"""Lire la ville par quartier : où ça se dégrade, où ça revient, où curer avant les pluies (C14).

Quatre questions de la mairie, quatre méthodes de la classe Territoire :

- points()      la carte thermique : chaque signalement retenu, avec son poids ;
- quartiers()   les quartiers les plus touchés, classés par un indice qu'on explique en une phrase ;
- historique()  tout ce qui s'est passé dans un quartier, du plus récent au plus ancien ;
- recurrents()  les dépôts sauvages qui reviennent au même endroit ;
- curage()      les caniveaux à curer AVANT la saison des pluies, au lieu d'attendre l'inondation.

Le quartier d'un signalement est celui dont le nom (OpenStreetMap) est le plus proche : voir
outils/extraire_quartiers.py. Rien ici n'est servi au public, sauf quartiers_propres(), qui ne
donne que des comptes par quartier — jamais une position, jamais une date précise.
"""

import datetime
import json
import math
import os

from .dossiers import CHAINE
from .geo import distance_m

# Un signalement vérifié compte pour 1 sur la carte thermique ; un signalement encore à vérifier
# pour un demi : il pèse, mais moins qu'un fait établi. Les signalements écartés n'y sont pas.
POIDS = {"verifie": 1.0, "recevable": 0.5, "a_verifier": 0.5}

NATURES = {
    "ordures": "Tas d'ordures", "fuite_eau": "Fuite d'eau", "caniveau_bouche": "Caniveau bouché",
    "toilettes_plein_air": "Toilettes vidées dehors", "abattoir_clandestin": "Abattoir clandestin",
    "eaux_usees_animales": "Eaux de poisson ou de poulet",
}

# Deux dossiers à moins de 60 m l'un de l'autre sont le même endroit : si un tas y revient après
# avoir été ramassé, ou s'il est signalé sur plusieurs semaines, c'est un dépôt récurrent.
RAYON_MEME_ENDROIT_M = 60
SEMAINES_POUR_RECURRENT = 2

GRAVITE = {"grave": 3, "moyen": 2, "leger": 1}
# Début habituel de la saison des pluies à Ouagadougou : juin. Les caniveaux doivent être curés avant.
MOIS_DEBUT_PLUIES = 6


def charger_quartiers(chemin: str) -> list:
    """[(nom, latitude, longitude), …] ; une liste vide si le fichier manque."""
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        return [(e["properties"]["nom"], e["geometry"]["coordinates"][1], e["geometry"]["coordinates"][0])
                for e in json.load(f)["features"]]


def quartier_de(quartiers: list, latitude, longitude) -> str:
    """Le nom de quartier le plus proche. Calcul à plat : à l'échelle d'une ville, l'erreur
    est négligeable, et chacun peut le refaire à la main."""
    if latitude is None or longitude is None or not quartiers:
        return "Non localisé"
    cos_lat = math.cos(math.radians(latitude))
    return min(quartiers, key=lambda q: (q[1] - latitude) ** 2 + ((q[2] - longitude) * cos_lat) ** 2)[0]


def jours_avant_les_pluies(aujourd_hui: datetime.date = None) -> int:
    aujourd_hui = aujourd_hui or datetime.date.today()
    debut = datetime.date(aujourd_hui.year, MOIS_DEBUT_PLUIES, 1)
    if aujourd_hui >= datetime.date(aujourd_hui.year, 10, 1):
        debut = datetime.date(aujourd_hui.year + 1, MOIS_DEBUT_PLUIES, 1)
    return max(0, (debut - aujourd_hui).days)


def _semaine(date: str):
    try:
        d = datetime.date.fromisoformat((date or "")[:10])
    except ValueError:
        return None
    return d.isocalendar()[:2]


class Territoire:
    def __init__(self, co, quartiers: list, cours_eau: list = None):
        self.co = co
        self.liste_quartiers = quartiers
        self.cours_eau = cours_eau or []          # [(lat, lon), …] points des cours d'eau

    def quartier(self, latitude, longitude) -> str:
        return quartier_de(self.liste_quartiers, latitude, longitude)

    # ------------------------------------------------------------------ carte thermique
    def points(self, nature: str = None, quartier: str = None, jours: int = None) -> list:
        """Les signalements retenus (non écartés), avec leur poids pour la carte thermique."""
        sql = ("SELECT id, latitude, longitude, nature, statut, date_reception FROM signalements"
               " WHERE statut != 'rejete' AND latitude IS NOT NULL")
        valeurs = []
        if nature:
            sql += " AND nature = ?"
            valeurs.append(nature)
        if jours:
            depuis = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=jours))
            sql += " AND date_reception >= ?"
            valeurs.append(depuis.isoformat(timespec="seconds"))
        sortie = []
        for l in self.co.execute(sql, valeurs):
            q = self.quartier(l["latitude"], l["longitude"])
            if quartier and q != quartier:
                continue
            sortie.append({"id": l["id"], "latitude": l["latitude"], "longitude": l["longitude"],
                           "nature": l["nature"], "statut": l["statut"], "quartier": q,
                           "date": l["date_reception"], "poids": POIDS.get(l["statut"], 0.5)})
        return sortie

    # ------------------------------------------------------------------ quartiers les plus touchés
    def quartiers(self, nature: str = None, jours: int = None) -> list:
        """Un indice par quartier, qu'on explique au jury en une phrase :
        indice = signalements retenus + 3 × dossiers encore ouverts + 5 × dépôts récurrents."""
        bilan = {}

        def ligne(nom):
            return bilan.setdefault(nom, {"quartier": nom, "signalements": 0, "verifies": 0,
                                          "ouverts": 0, "recurrents": 0, "volume_m3": 0.0})
        for p in self.points(nature=nature, jours=jours):
            b = ligne(p["quartier"])
            b["signalements"] += 1
            b["verifies"] += p["statut"] == "verifie"
        if nature in (None, "ordures"):
            for d in self.co.execute("SELECT latitude, longitude, volume_m3 FROM depotoirs"
                                     " WHERE etape NOT IN ('collecte', 'classe')"):
                b = ligne(self.quartier(d["latitude"], d["longitude"]))
                b["ouverts"] += 1
                b["volume_m3"] += d["volume_m3"] or 0
            for r in self.recurrents():
                ligne(r["quartier"])["recurrents"] += 1
        for table in ("fuites", "nuisances"):
            if nature and not (table == "fuites" and nature == "fuite_eau"
                               or table == "nuisances" and nature not in ("ordures", "fuite_eau")):
                continue
            filtre = " AND nature = ?" if table == "nuisances" and nature else ""
            for d in self.co.execute(f"SELECT latitude, longitude FROM {table}"
                                     f" WHERE etape NOT IN ('repare', 'traite', 'classe'){filtre}",
                                     [nature] if filtre else []):
                ligne(self.quartier(d["latitude"], d["longitude"]))["ouverts"] += 1
        for b in bilan.values():
            b["indice"] = b["signalements"] + 3 * b["ouverts"] + 5 * b["recurrents"]
            b["volume_m3"] = round(b["volume_m3"], 1)
        return sorted(bilan.values(), key=lambda b: (-b["indice"], b["quartier"]))

    def quartiers_propres(self) -> list:
        """Pour le public : du plus propre au plus touché, des comptes et rien d'autre."""
        touches = {b["quartier"]: b for b in self.quartiers()}
        sortie = []
        for nom, _, _ in self.liste_quartiers:
            b = touches.get(nom, {})
            sortie.append({"quartier": nom, "ouverts": b.get("ouverts", 0),
                           "signalements": b.get("signalements", 0)})
        return sorted(sortie, key=lambda b: (b["ouverts"], b["signalements"], b["quartier"]))

    # ------------------------------------------------------------------ historique d'une zone
    def historique(self, quartier: str, limite: int = 200) -> list:
        """Signalements et étapes des dossiers du quartier, du plus récent au plus ancien."""
        evenements = []
        for p in self.points(quartier=quartier):
            evenements.append({"date": p["date"], "quoi": "Signalement n° %d — %s" % (
                p["id"], NATURES.get(p["nature"], p["nature"])), "statut": p["statut"]})
        for d in self.co.execute("SELECT id, latitude, longitude FROM depotoirs"):
            if self.quartier(d["latitude"], d["longitude"]) != quartier:
                continue
            for j in self.co.execute("SELECT date, poste, etape, detail FROM journal_dossier"
                                     " WHERE depotoir_id = ?", (d["id"],)):
                etape = CHAINE.get(j["etape"], {}).get("nom", j["etape"])
                evenements.append({"date": j["date"], "quoi": "Dossier %d — %s (%s)" % (
                    d["id"], etape, j["poste"]), "statut": "", "detail": j["detail"]})
        evenements.sort(key=lambda e: e["date"] or "", reverse=True)
        return evenements[:limite]

    # ------------------------------------------------------------------ dépôts récurrents
    def recurrents(self) -> list:
        """Les endroits où les ordures reviennent : plusieurs dossiers au même endroit (le tas
        est revenu après un ramassage), ou des signalements sur au moins deux semaines."""
        dossiers = [dict(d) for d in self.co.execute(
            "SELECT id, latitude, longitude, etape, volume_m3 FROM depotoirs")]
        semaines = {}
        for s in self.co.execute("SELECT depotoir_id, date_observation, date_reception FROM signalements"
                                 " WHERE depotoir_id IS NOT NULL AND statut != 'rejete'"):
            semaine = _semaine(s["date_observation"]) or _semaine(s["date_reception"])
            if semaine:
                semaines.setdefault(s["depotoir_id"], set()).add(semaine)
        # Regroupe les dossiers proches : un endroit = un groupe.
        groupes, vus = [], set()
        for d in dossiers:
            if d["id"] in vus:
                continue
            groupe = [e for e in dossiers if e["id"] not in vus and distance_m(
                d["longitude"], d["latitude"], e["longitude"], e["latitude"]) <= RAYON_MEME_ENDROIT_M]
            vus.update(e["id"] for e in groupe)
            groupes.append(groupe)
        sortie = []
        for groupe in groupes:
            toutes = set().union(*(semaines.get(e["id"], set()) for e in groupe))
            if len(groupe) < 2 and len(toutes) < SEMAINES_POUR_RECURRENT:
                continue
            centre = groupe[0]
            sortie.append({"latitude": centre["latitude"], "longitude": centre["longitude"],
                           "quartier": self.quartier(centre["latitude"], centre["longitude"]),
                           "dossiers": [e["id"] for e in groupe], "semaines": len(toutes),
                           "volume_m3": round(sum(e["volume_m3"] or 0 for e in groupe), 1)})
        return sorted(sortie, key=lambda r: (-len(r["dossiers"]), -r["semaines"]))

    # ------------------------------------------------------------------ prévention : curage
    def curage(self) -> dict:
        """Les caniveaux à curer avant la saison des pluies, du plus urgent au moins urgent.

        Entrent dans la liste : les caniveaux bouchés signalés et pas encore traités, et les
        tas d'ordures déposés DANS un caniveau. Points d'urgence, expliqués à l'agent :
        gravité (1 à 3) + 1 par témoin + 2 si un cours d'eau passe à moins de 300 m
        (l'eau bloquée y déborde d'abord) + 1 par m³ d'ordures dans le caniveau (plafonné à 5)."""
        lignes = []
        for n in self.co.execute("SELECT id, latitude, longitude, gravite, nb_sources FROM nuisances"
                                 " WHERE nature = 'caniveau_bouche' AND etape NOT IN ('traite', 'classe')"):
            lignes.append({"genre": "Caniveau bouché", "reference": "Nuisance %d" % n["id"],
                           "lien": "/decision/nuisances.html", "latitude": n["latitude"],
                           "longitude": n["longitude"], "points": GRAVITE.get(n["gravite"], 2)
                           + (n["nb_sources"] or 1), "raisons": ["gravité " + (n["gravite"] or "moyen")]})
        for d in self.co.execute("SELECT id, latitude, longitude, volume_m3, nb_sources FROM depotoirs"
                                 " WHERE depot = 'caniveau' AND etape NOT IN ('collecte', 'classe')"):
            volume = d["volume_m3"] or 0
            lignes.append({"genre": "Ordures dans un caniveau", "reference": "Dossier %d" % d["id"],
                           "lien": "/decision/dossiers.html", "latitude": d["latitude"],
                           "longitude": d["longitude"], "points": 2 + (d["nb_sources"] or 1)
                           + min(5, int(volume)), "raisons": [("%.1f m³ d'ordures" % volume).replace(".", ",")]})
        for l in lignes:
            if self._pres_d_un_cours_d_eau(l["latitude"], l["longitude"]):
                l["points"] += 2
                l["raisons"].append("cours d'eau à moins de 300 m")
            l["quartier"] = self.quartier(l["latitude"], l["longitude"])
        lignes.sort(key=lambda l: -l["points"])
        return {"jours_avant_les_pluies": jours_avant_les_pluies(), "a_curer": lignes}

    def _pres_d_un_cours_d_eau(self, latitude, longitude, rayon_m: float = 300) -> bool:
        # Un premier tri grossier (0,005° ≈ 550 m) évite de calculer des milliers de distances.
        proches = [(la, lo) for la, lo in self.cours_eau
                   if abs(la - latitude) < 0.005 and abs(lo - longitude) < 0.005]
        return any(distance_m(longitude, latitude, lo, la) <= rayon_m for la, lo in proches)


def charger_cours_eau(chemin: str, pas: int = 4) -> list:
    """Des points le long des cours d'eau (un sommet sur `pas`, assez pour un rayon de 300 m)."""
    if not os.path.exists(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        donnees = json.load(f)
    points = []
    for e in donnees["features"]:
        geo = e.get("geometry") or {}
        lignes = geo.get("coordinates", [])
        if geo.get("type") == "LineString":
            lignes = [lignes]
        elif geo.get("type") != "MultiLineString":
            continue
        for ligne in lignes:
            points.extend((lat, lon) for lon, lat in ligne[::pas])
    return points
