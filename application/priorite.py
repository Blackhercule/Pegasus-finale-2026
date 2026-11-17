"""Classer les signalements par urgence réelle, et non par ordre d'arrivée.

Le problème qu'on résout : un agent de la mairie traite une file. Tant qu'il y a vingt
signalements, l'ordre d'arrivée suffit. À cinq mille, il devient absurde — un tas d'ordures
devant une école attend derrière un tas dans un terrain vague, simplement parce qu'il a été
signalé plus tard. Augmenter le nombre d'agents coûte cher ; mieux ordonner la file ne coûte
rien.

**Pourquoi un score écrit à la main et non un modèle appris.** Un jury désigne lui-même qui
explique une fonction, et « le modèle l'a décidé » n'est pas une explication. Ici, chaque
dossier porte ses raisons en clair : « 180 m d'une école », « trois témoins », « en attente
depuis 6 jours ». Un agent peut contredire le classement et comprendre pourquoi il s'est
trompé ; une mairie peut changer un poids dans `parametres.json` sans toucher au code. C'est
aussi ce qui permet de défendre le résultat devant un habitant qui demande pourquoi sa rue
passe après celle d'à côté.

Les données viennent toutes du dépôt, rien n'est téléchargé : les 1 187 lieux publics nommés
(`lieux.geojson`), les plans d'eau (`eau.geojson`) et la densité de bâti (`zones.geojson`).
"""

import datetime
import json
import math

import numpy as np

# Les lieux où un dépôt sauvage fait le plus de dégâts : on y croise des enfants, on y vend à
# manger, on y soigne. Le poids dit combien de points vaut la proximité immédiate.
LIEUX_SENSIBLES = {
    "ecole": 30,
    "sante": 30,
    "marche": 25,
    "eau_potable": 25,
}
# Au-delà de cette distance, un lieu sensible ne compte plus. En deçà, le poids décroît
# linéairement : 50 m d'une école vaut presque le plein, 400 m ne vaut presque rien.
PORTEE_M = 400

POIDS = {
    "gravite": 25,        # un gros tas, une inondation : ce qu'on voit
    "temoins": 15,        # plusieurs appareils indépendants : ce dont on est sûr
    "attente": 20,        # le temps déjà passé en file : personne ne doit être oublié
    "densite": 15,        # combien de gens vivent autour
}
# Au-delà de ce délai, l'attente ne rapporte plus : un dossier de trois semaines et un de deux
# mois sont tous deux en souffrance, inutile de les départager là-dessus.
ATTENTE_MAX_JOURS = 21

# Les niveaux de gravité des trois familles de signalements, ramenés à une même échelle 0–1.
GRAVITES = {
    "petit": 0.3, "moyen": 0.6, "grand": 1.0,                    # tas d'ordures
    "suintement": 0.3, "jet": 0.65, "inondation": 1.0,           # fuites d'eau
    "leger": 0.3, "moyen_nuisance": 0.6, "grave": 1.0,           # nuisances
}


def _degres_par_metre(latitude: float) -> tuple:
    """Combien de degrés valent un mètre ici. À Ouagadougou, un degré de longitude est plus
    court qu'un degré de latitude : sans cette correction, les distances est-ouest seraient
    surestimées d'environ 2 %."""
    lat = math.radians(latitude)
    return 1.0 / 111320.0, 1.0 / (111320.0 * max(0.1, math.cos(lat)))


class Priorite:
    """Calcule la note d'urgence d'un signalement, et dit pourquoi.

    Les lieux et les carreaux sont chargés une fois et rangés dans des tableaux NumPy : le
    classement d'une file de plusieurs milliers de dossiers reste instantané."""

    def __init__(self, fichier_lieux: str = None, fichier_zones: str = None,
                 geo=None, poids: dict = None):
        self.geo = geo
        self.poids = {**POIDS, **(poids or {})}
        self.lieux = {}
        self.carreaux = None
        self.habitants = None
        if fichier_lieux:
            self._charger_lieux(fichier_lieux)
        if fichier_zones:
            self._charger_zones(fichier_zones)

    def _charger_lieux(self, fichier: str) -> None:
        """Un tableau de positions par genre de lieu sensible."""
        familles = {genre: [] for genre in LIEUX_SENSIBLES}
        with open(fichier, encoding="utf-8") as f:
            for entite in json.load(f).get("features", []):
                p = entite.get("properties", {})
                genre = self._famille(p)
                if genre is None:
                    continue
                g = entite.get("geometry") or {}
                if g.get("type") != "Point":
                    continue
                lon, lat = g["coordinates"][:2]
                familles[genre].append((lon, lat))
        self.lieux = {genre: np.array(points, dtype=float)
                      for genre, points in familles.items() if points}

    @staticmethod
    def _famille(proprietes: dict):
        """À quelle famille sensible ce lieu appartient-il ? None s'il n'en est pas."""
        genre = proprietes.get("type")
        sous = proprietes.get("sous_type")
        if genre == "marche":
            return "marche"
        if genre == "sante":
            return "sante"
        if genre == "ecole":
            # Les écoles au sens large : maternelles, primaires, collèges, universités.
            return "ecole"
        if genre == "eau" or sous in ("drinking_water", "water_well"):
            return "eau_potable"
        return None

    def _charger_zones(self, fichier: str) -> None:
        """Le centre de chaque carreau et le nombre de bâtiments qu'il porte.

        On n'a pas la population au carreau : la surface bâtie en est l'approximation que tout
        le projet utilise déjà. C'est une approximation, et elle est dite comme telle dans le
        rapport : un quartier d'entrepôts est compté comme un quartier d'habitation."""
        centres, poids = [], []
        with open(fichier, encoding="utf-8") as f:
            for entite in json.load(f).get("features", []):
                g = entite.get("geometry") or {}
                if g.get("type") != "Polygon":
                    continue
                anneau = g["coordinates"][0]
                lon = sum(p[0] for p in anneau[:-1]) / max(1, len(anneau) - 1)
                lat = sum(p[1] for p in anneau[:-1]) / max(1, len(anneau) - 1)
                centres.append((lon, lat))
                poids.append(float(entite.get("properties", {}).get("nb_batiments") or 0))
        if centres:
            self.carreaux = np.array(centres, dtype=float)
            maxi = max(poids) or 1.0
            self.habitants = np.array(poids, dtype=float) / maxi      # ramené entre 0 et 1

    # ------------------------------------------------------------------ calcul
    def _plus_proche_m(self, points, lon: float, lat: float) -> float:
        """Distance au point le plus proche du tableau, en mètres."""
        if points is None or not len(points):
            return float("inf")
        par_lat, par_lon = _degres_par_metre(lat)
        dx = (points[:, 0] - lon) / par_lon
        dy = (points[:, 1] - lat) / par_lat
        return float(np.sqrt(dx * dx + dy * dy).min())

    def _densite(self, lon: float, lat: float) -> float:
        if self.carreaux is None:
            return 0.0
        par_lat, par_lon = _degres_par_metre(lat)
        dx = (self.carreaux[:, 0] - lon) / par_lon
        dy = (self.carreaux[:, 1] - lat) / par_lat
        rang = int(np.argmin(dx * dx + dy * dy))
        return float(self.habitants[rang])

    def noter(self, latitude, longitude, gravite=None, nb_sources: int = 1,
              premier_vu: str = None) -> dict:
        """La note d'urgence (0 à 100 environ) et les raisons, en clair.

        Les raisons ne sont pas décoratives : ce sont elles qui permettent à un agent de
        contester le classement, et à l'équipe de l'expliquer au jury."""
        note, raisons = 0.0, []
        if latitude is None or longitude is None:
            return {"note": 0, "raisons": ["position inconnue"]}
        lat, lon = float(latitude), float(longitude)

        # 1. La proximité d'un lieu où le dépôt fait le plus de mal.
        for genre, poids in LIEUX_SENSIBLES.items():
            distance = self._plus_proche_m(self.lieux.get(genre), lon, lat)
            if distance >= PORTEE_M:
                continue
            part = 1.0 - distance / PORTEE_M
            note += poids * part
            if part > 0.25:                       # on ne raconte que ce qui pèse vraiment
                raisons.append("%d m d'%s" % (round(distance), {
                    "ecole": "un établissement scolaire", "sante": "un lieu de soins",
                    "marche": "un marché", "eau_potable": "un point d'eau"}[genre]))

        # 2. Un plan d'eau à côté : le jus des ordures y finit à la première pluie.
        if self.geo is not None and getattr(self.geo, "eaux", None):
            from shapely.geometry import Point
            point = Point(lon, lat)
            distance_deg = min(e.distance(point) for e in self.geo.eaux)
            par_lat, _ = _degres_par_metre(lat)
            distance = distance_deg / par_lat
            if distance < PORTEE_M:
                note += 20 * (1.0 - distance / PORTEE_M)
                raisons.append("%d m d'un plan d'eau" % round(distance))

        # 3. Ce qu'on voit : la gravité déclarée.
        niveau = GRAVITES.get(gravite, 0.5 if gravite else 0.3)
        note += self.poids["gravite"] * niveau

        # 4. Ce dont on est sûr : plusieurs appareils indépendants.
        if nb_sources and nb_sources > 1:
            # Deux témoins valent beaucoup plus qu'un ; le dixième n'ajoute presque rien.
            part = min(1.0, math.log(nb_sources, 5))
            note += self.poids["temoins"] * part
            raisons.append("%d témoins indépendants" % nb_sources)

        # 5. Le temps déjà passé en file : sans cela, un dossier peu grave n'est jamais traité.
        jours = self._jours_depuis(premier_vu)
        if jours is not None and jours >= 1:
            part = min(1.0, jours / ATTENTE_MAX_JOURS)
            note += self.poids["attente"] * part
            raisons.append("en attente depuis %d jour(s)" % round(jours))

        # 6. Combien de gens vivent autour.
        densite = self._densite(lon, lat)
        note += self.poids["densite"] * densite
        if densite > 0.5:
            raisons.append("quartier dense")

        return {"note": round(note, 1), "raisons": raisons}

    @staticmethod
    def _jours_depuis(iso: str):
        if not iso:
            return None
        try:
            date = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        except ValueError:
            return None
        if date.tzinfo is None:
            date = date.replace(tzinfo=datetime.timezone.utc)
        return (datetime.datetime.now(datetime.timezone.utc) - date).total_seconds() / 86400

    def classer(self, dossiers: list, position=None, gravite=None) -> list:
        """Note chaque dossier et rend la liste triée, la plus urgente en tête.

        `position` et `gravite` disent où lire ces valeurs dans un dossier, parce que les trois
        familles de signalements ne les nomment pas pareil (taille, ampleur, gravité)."""
        position = position or (lambda d: (d.get("latitude"), d.get("longitude")))
        gravite = gravite or (lambda d: None)
        for dossier in dossiers:
            lat, lon = position(dossier)
            dossier["priorite"] = self.noter(
                lat, lon, gravite(dossier),
                dossier.get("nb_sources") or 1, dossier.get("premier_vu"))
        return sorted(dossiers, key=lambda d: d["priorite"]["note"], reverse=True)
